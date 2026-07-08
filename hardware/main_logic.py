# =============================================================================
# hardware/main.py — ESP32 MicroPython Master Boot Script
# IIT Delhi | 1Hz Transient Biomass Cookstove Simulator | Hardware Interface
#
# HARDWARE WIRING:
#   I2C LCD 20x4:  SDA=21, SCL=22
#   KY-040 Encoder: CLK=32, DT=33, SW=25 (all Pin.PULL_UP)
#   LED:           Pin 26
#   Buzzer:        Pin 27 (PWM)
#
# ALARM BEHAVIORS:
#   Tick Feedback:   10ms LED blink + 10ms 1kHz beep (every rotation / press)
#   Success Alarm:   3x (500ms 1kHz beep + 500ms off) with LED flash
#   Danger Alarm:    Continuous alternating 800/1200Hz siren + rapid LED toggle
#                    until button press acknowledgment
# =============================================================================

import machine
import time
import math

from food_db    import FOOD_DB, get_dish_names, get_dish
from pellet_db  import PELLET_DB, get_pellet_names, get_pellet
from utensil_db import UTENSIL_DB, get_utensil_names, get_utensil
import main_logic

# =============================================================================
# HARDWARE PIN SETUP
# =============================================================================

# I2C LCD (20x4)
i2c = machine.I2C(0, sda=machine.Pin(21), scl=machine.Pin(22), freq=400000)
time.sleep_ms(200)
from esp8266_i2c_lcd import I2cLcd
LCD_ADDR = 0x27
LCD_ROWS = 4
LCD_COLS = 20
lcd = I2cLcd(i2c, LCD_ADDR, LCD_ROWS, LCD_COLS)

# KY-040 Rotary Encoder
enc_clk = machine.Pin(32, machine.Pin.IN, machine.Pin.PULL_UP)
enc_dt  = machine.Pin(33, machine.Pin.IN, machine.Pin.PULL_UP)
enc_sw  = machine.Pin(25, machine.Pin.IN, machine.Pin.PULL_UP)

# LED
led = machine.Pin(26, machine.Pin.OUT)
led.value(0)

# Buzzer (PWM)
buzzer = machine.PWM(machine.Pin(27), freq=1000, duty=0)


# =============================================================================
# ENCODER STATE (volatile — modified by ISR)
# =============================================================================

_enc_pos = 0
_enc_pressed = False
_last_enc_time = 0
_last_btn_time = 0
DEBOUNCE_MS = 5
BTN_DEBOUNCE_MS = 200


def _enc_isr(pin):
    """Hardware IRQ for KY-040 CLK pin — reads DT for direction."""
    global _enc_pos, _last_enc_time
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_enc_time) < DEBOUNCE_MS:
        return
    _last_enc_time = now
    if enc_dt.value() != enc_clk.value():
        _enc_pos += 1
    else:
        _enc_pos -= 1


def _btn_isr(pin):
    """Debounced hardware IRQ for encoder button press."""
    global _enc_pressed, _last_btn_time
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_btn_time) < BTN_DEBOUNCE_MS:
        return
    _last_btn_time = now
    _enc_pressed = True


# Attach hardware interrupts
enc_clk.irq(trigger=machine.Pin.IRQ_FALLING, handler=_enc_isr)
enc_sw.irq(trigger=machine.Pin.IRQ_FALLING, handler=_btn_isr)


def get_encoder_pos():
    """Read current encoder position (atomic)."""
    return _enc_pos


def set_encoder_pos(val):
    """Reset encoder position."""
    global _enc_pos
    _enc_pos = val


def was_pressed():
    """Check and clear button press flag."""
    global _enc_pressed
    if _enc_pressed:
        _enc_pressed = False
        return True
    return False


# =============================================================================
# LED & BUZZER FEEDBACK SYSTEM
# =============================================================================

def tick_feedback():
    """Tactile feedback: 10ms LED blink + 10ms 1kHz beep."""
    led.value(1)
    buzzer.freq(1000)
    buzzer.duty(512)
    time.sleep_ms(10)
    buzzer.duty(0)
    led.value(0)


def success_alarm():
    """
    Time-over success alarm: 3 long beeps with LED flashing.
    3x (500ms 1kHz beep + 500ms off).
    """
    for _ in range(3):
        led.value(1)
        buzzer.freq(1000)
        buzzer.duty(512)
        time.sleep_ms(500)
        buzzer.duty(0)
        led.value(0)
        time.sleep_ms(500)


def danger_alarm():
    """
    Protection/Danger alarm: continuous alternating 800/1200Hz siren
    with rapid LED flashing. Runs until button press acknowledgment.
    """
    global _enc_pressed
    _enc_pressed = False
    freq_a = 800
    freq_b = 1200
    toggle = False
    while True:
        if was_pressed():
            buzzer.duty(0)
            led.value(0)
            return
        if toggle:
            buzzer.freq(freq_a)
        else:
            buzzer.freq(freq_b)
        buzzer.duty(512)
        led.value(1 if toggle else 0)
        toggle = not toggle
        time.sleep_ms(100)


# =============================================================================
# LCD HELPER FUNCTIONS
# =============================================================================

def lcd_clear():
    lcd.clear()
    time.sleep_ms(5)


def lcd_show(line0="", line1="", line2="", line3=""):
    """Write up to 4 lines to 20x4 LCD."""
    lcd_clear()
    lines = [line0, line1, line2, line3]
    for i, txt in enumerate(lines):
        if txt:
            lcd.move_to(0, i)
            lcd.putstr(txt[:LCD_COLS])


def lcd_write_line(row, text):
    """Overwrite a single line on the LCD."""
    lcd.move_to(0, row)
    lcd.putstr(("{:<" + str(LCD_COLS) + "}").format(text[:LCD_COLS]))


def fmt_trunc(text, width=20):
    """Truncate or pad text to width."""
    if len(text) > width:
        return text[:width - 1] + "."
    return text


# =============================================================================
# INTERACTIVE MENU FUNCTIONS
# =============================================================================

def menu_select(title, options):
    """
    Scroll through a list of options with the encoder.
    Button press confirms selection. Returns (index, selected_name).
    LED + buzzer tick on every scroll step.
    """
    idx = 0
    n = len(options)
    set_encoder_pos(0)
    last_pos = 0

    lcd_show(title, "> " + fmt_trunc(options[idx], 18),
             "",
             "Turn=Scroll Btn=OK")

    while True:
        pos = get_encoder_pos()
        if pos != last_pos:
            tick_feedback()
            diff = pos - last_pos
            last_pos = pos
            idx = (idx + diff) % n
            lcd_write_line(1, "> " + fmt_trunc(options[idx], 18))
            # Show next item as preview
            nxt = (idx + 1) % n
            lcd_write_line(2, "  " + fmt_trunc(options[nxt], 18))

        if was_pressed():
            tick_feedback()
            lcd_write_line(3, "OK: " + fmt_trunc(options[idx], 15))
            time.sleep_ms(300)
            return (idx, options[idx])

        time.sleep_ms(20)


def menu_adjust_float(title, unit, default, lo, hi, step=0.5):
    """
    Adjust a float value with the encoder.
    Returns the selected float value.
    """
    val = default
    set_encoder_pos(0)
    last_pos = 0

    lcd_show(title,
             "Value: {:.1f} {}".format(val, unit),
             "Range: {:.1f}-{:.1f}".format(lo, hi),
             "Turn=Adj  Btn=OK")

    while True:
        pos = get_encoder_pos()
        if pos != last_pos:
            tick_feedback()
            diff = pos - last_pos
            last_pos = pos
            val += diff * step
            if val < lo:
                val = lo
            if val > hi:
                val = hi
            lcd_write_line(1, "Value: {:.1f} {}".format(val, unit))

        if was_pressed():
            tick_feedback()
            lcd_write_line(3, "OK: {:.1f} {}".format(val, unit))
            time.sleep_ms(300)
            return val

        time.sleep_ms(20)


def menu_adjust_int(title, unit, default, lo, hi):
    """
    Adjust an integer value with the encoder.
    Returns the selected integer value.
    """
    val = default
    set_encoder_pos(0)
    last_pos = 0

    lcd_show(title,
             "Value: {} {}".format(val, unit),
             "Range: {}-{}".format(lo, hi),
             "Turn=Adj  Btn=OK")

    while True:
        pos = get_encoder_pos()
        if pos != last_pos:
            tick_feedback()
            diff = pos - last_pos
            last_pos = pos
            val += diff
            if val < lo:
                val = lo
            if val > hi:
                val = hi
            lcd_write_line(1, "Value: {} {}".format(val, unit))

        if was_pressed():
            tick_feedback()
            lcd_write_line(3, "OK: {} {}".format(val, unit))
            time.sleep_ms(300)
            return val

        time.sleep_ms(20)


# =============================================================================
# MAIN SIMULATION FLOW
# =============================================================================

def collect_inputs():
    """
    7-step interactive wizard using LCD + encoder.
    Mirrors the desktop main.py flow with Smart Unit dispatch.
    """
    inp = {}

    lcd_show("FDS  COOKSTOVE", "WELCOME", "    V10 / 1Hz", "Press btn to start")
    while not was_pressed():
        time.sleep_ms(50)
    tick_feedback()

    # ── Step 1: Dish Selection ────────────────────────────────────────────────
    dish_names = get_dish_names()
    idx, dish_name = menu_select("1/7 SELECT DISH", dish_names)
    inp["dish_name"] = dish_name
    dish = get_dish(dish_name)
    inp["dish"] = dish

    # ── Step 2: Quantity (Smart Unit dispatch) ────────────────────────────────
    if dish.qty_prompt:
        # Dish has custom Smart Unit (e.g. Roti, Boiling Milk)
        if dish.qty_is_float:
            qty = menu_adjust_float(
                "2/7 " + dish.qty_prompt[:14],
                dish.qty_unit,
                dish.qty_default,
                dish.qty_min,
                dish.qty_max,
                step=0.5,
            )
        else:
            qty = menu_adjust_int(
                "2/7 " + dish.qty_prompt[:14],
                dish.qty_unit,
                int(dish.qty_default),
                int(dish.qty_min),
                int(dish.qty_max),
            )
            qty = float(qty)
        inp["portions"] = qty
    elif dish.variable_water:
        # Variable-water dish (Plain Water Boiling)
        water_l = menu_adjust_float("2/7 WATER VOLUME", "L", 5.0, 0.5, 50.0, step=0.5)
        inp["water_liters"] = water_l
        inp["portions"] = 1
    else:
        # Standard per-person servings
        servings = menu_adjust_int("2/7 SERVINGS", "people", 4, 1, 20)
        inp["portions"] = servings

    n = inp["portions"]

    # ── Step 3: Ambient Temperature ──────────────────────────────────────────
    inp["t_ambient_c"] = menu_adjust_float("3/7 AMBIENT TEMP", "C", 25.0, 15.0, 45.0, step=1.0)

    # ── Step 4: Wind Factor ──────────────────────────────────────────────────
    wind_labels = list(main_logic.WIND_TIERS.keys())
    _, wind_choice = menu_select("4/7 WIND FACTOR", wind_labels)
    inp["wind_label"] = wind_choice
    inp["k_conv_current"] = main_logic.WIND_TIERS[wind_choice]

    # ── Step 5: Utensil Selection ────────────────────────────────────────────
    utensil_names = get_utensil_names()
    _, utensil_name = menu_select("5/7 UTENSIL", utensil_names)
    utensil = get_utensil(utensil_name)
    inp["utensil_name"] = utensil_name
    inp["utensil"] = utensil
    inp["cp_pot"] = utensil.cp_kj_kgk
    inp["is_pc"] = utensil.is_pressure
    inp["emissivity"] = main_logic._emissivity_for_utensil(utensil)

    # ── Step 6: Pot Mass Override ────────────────────────────────────────────
    inp["m_pot"] = menu_adjust_float(
        "6/7 POT MASS",
        "kg",
        utensil.mass_kg,
        0.1,
        10.0,
        step=0.05,
    )

    # ── Step 7: Lid State ────────────────────────────────────────────────────
    if utensil.is_pressure:
        inp["lid_factor"] = 0.0
        inp["lid_label"] = "Sealed (PC)"
        lcd_show("7/7 LID STATE", "Pressure Cooker", "Auto-sealed", "lid_factor = 0.0")
        time.sleep_ms(1000)
    else:
        lid_options = ["Lid ON (Covered)", "Lid OFF (Open)"]
        _, lid_choice = menu_select("7/7 LID STATE", lid_options)
        if "ON" in lid_choice:
            inp["lid_factor"] = main_logic.LID_FACTOR_ON
            inp["lid_label"] = "Lid ON"
        else:
            inp["lid_factor"] = main_logic.LID_FACTOR_OFF
            inp["lid_label"] = "Lid OFF"

    # ── Transfer physics variables from databases ────────────────────────────
    if dish.variable_water:
        inp["m_food"]           = dish.food_mass_per_serving_kg
        inp["cp_food"]          = dish.cp_food_kj_kgk
        inp["m_water_initial"]  = inp["water_liters"]
        inp["t_kinetic_base_s"] = 0.0
    else:
        inp["m_food"]           = dish.food_mass_per_serving_kg * n
        inp["cp_food"]          = dish.cp_food_kj_kgk
        inp["m_water_initial"]  = dish.added_water_per_serving_kg * n
        inp["t_kinetic_base_s"] = float(dish.phases.total_s)

    return inp


def run_simulation(inp):
    """
    Execute full simulation pipeline:
    geometry -> estimate -> zero_state -> 1Hz loop -> post_process.
    Shows live progress on LCD during the 1Hz loop.
    """
    # ── Geometry ──────────────────────────────────────────────────────────────
    geom = main_logic.compute_vessel_geometry(
        inp["m_water_initial"], inp["utensil_name"], inp["lid_factor"]
    )
    inp.update(geom)

    lcd_show("COMPUTING...", "Estimating cook", "time (1Hz preview)", "Please wait...")

    # ── Total Time Estimator ─────────────────────────────────────────────────
    eta_geom = inp["eta_geom"]
    P_in_kw = (main_logic.FAN_HIGH / 3600.0) * inp["gcv_kj_kg"] * eta_geom
    inp["P_in_kw"] = P_in_kw

    preview = main_logic.estimate_cook_time(
        m_food=inp["m_food"],
        cp_food=inp["cp_food"],
        m_water=inp["m_water_initial"],
        m_pot=inp["m_pot"],
        cp_pot=inp["cp_pot"],
        t_kinetic_s=inp["t_kinetic_base_s"],
        P_in_kw=P_in_kw,
        A_m2=inp["A_m2"],
        k_conv=inp["k_conv_current"],
        emissivity=inp["emissivity"],
        T_amb=inp["t_ambient_c"],
        lid_fac=inp["lid_factor"],
    )

    t_heat_s = preview["t_heat_s"]
    if preview["heat_cannot_rise"] > 0.5 or t_heat_s <= 0.0:
        t_heat_s = 0.0

    t_safety_buffer_s = main_logic.compute_safety_buffer_s(
        t_heat_s, inp["k_conv_current"], inp["m_water_initial"]
    )
    t_core_s = t_heat_s + inp["t_kinetic_base_s"]
    t_total_s = t_core_s + t_safety_buffer_s

    inp["t_heat_est_s"]      = t_heat_s
    inp["t_boil_est_s"]      = preview["t_boil_s"]
    inp["t_safety_buffer_s"] = t_safety_buffer_s
    inp["t_preview_s"]       = preview["t_preview_s"]
    inp["t_total_s"]         = t_total_s
    inp["t_total_min_user"]  = t_total_s / 60.0
    inp["Q_out_avg_kw"] = (
        preview["Q_out_accum_kj"] / preview["t_preview_s"]
        if preview["t_preview_s"] > 0.0 else 0.0
    )

    # Store pellet info
    pellet = get_pellet(inp["pellet_name"])
    inp["pellet"] = pellet
    inp["gcv_kj_kg"] = pellet.conservative_gcv_kj

    lcd_show("PREDICTED TIME:",
             "{:.1f} min total".format(t_total_s / 60.0),
             "Heat:{:.0f}s Kin:{:.0f}s".format(t_heat_s, inp["t_kinetic_base_s"]),
             "Starting sim...")
    time.sleep_ms(1500)

    # ── Zero State + 1Hz Loop ────────────────────────────────────────────────
    inp = main_logic.zero_state(inp)

    # Run the loop in chunks to update LCD periodically
    # We manually step through the 1Hz loop to show live telemetry
    lcd_show("SIMULATION RUNNING", "T_pot:  --- C", "Time:  0/{:.0f}s".format(t_total_s), "Water: --- g")

    m_food    = inp["m_food"]
    cp_food   = inp["cp_food"]
    m_pot     = inp["m_pot"]
    cp_pot    = inp["cp_pot"]
    A         = inp["A_m2"]
    eta_geom  = inp["eta_geom"]
    gcv       = inp["gcv_kj_kg"]
    lid_fac   = inp["lid_factor"]
    T_amb     = inp["t_ambient_c"]
    k_conv    = inp["k_conv_current"]
    emissivity = inp.get("emissivity", main_logic.EMISSIVITY_DEFAULT)

    P_in_kw_loop = (main_logic.FAN_HIGH / 3600.0) * gcv * eta_geom
    T_pot         = inp["T_pot_c"]
    m_water       = inp["m_water_current"]
    t_elapsed     = inp["t_elapsed_s"]
    flag_dry      = False
    flag_over     = False
    t_boil_reached = None

    Q_in_kj = 0.0
    Q_out_kj = 0.0
    Q_sensible_kj = 0.0
    Q_evap_kj = 0.0
    tick = 0
    tick_log = []
    lcd_update_interval = 30  # Update LCD every 30 ticks (seconds)

    while t_elapsed < t_total_s:
        T_before = T_pot
        m_w_before = m_water

        Q_in = P_in_kw_loop * main_logic.dt
        MCp_total = (m_food * cp_food) + (m_water * main_logic.CP_WATER) + (m_pot * cp_pot)
        Q_out = main_logic.heat_loss_kw(T_pot, T_amb, A, k_conv, emissivity, lid_fac) * main_logic.dt
        Q_avail = Q_in - Q_out

        if Q_avail <= 0.0:
            if MCp_total > 0:
                T_pot += Q_avail / MCp_total
        else:
            if T_pot < 100.0:
                Q_to_100 = MCp_total * (100.0 - T_pot)
                if Q_avail <= Q_to_100:
                    T_pot   += Q_avail / MCp_total
                    Q_avail  = 0.0
                else:
                    T_pot    = 100.0
                    Q_avail -= Q_to_100
                    if t_boil_reached is None:
                        t_boil_reached = t_elapsed + main_logic.dt

            if Q_avail > 0 and m_water > 0:
                m_evap_potential = (Q_avail / main_logic.L_V) * lid_fac
                if m_evap_potential <= m_water:
                    m_water -= m_evap_potential
                    Q_avail  = 0.0
                else:
                    Q_boil  = (m_water / lid_fac) * main_logic.L_V
                    m_water = 0.0
                    Q_avail -= Q_boil

            if Q_avail > 0 and m_water <= 0:
                MCp_dry = (m_food * cp_food) + (m_pot * cp_pot)
                if MCp_dry > 0:
                    T_pot += Q_avail / MCp_dry
                Q_avail = 0.0

        Q_in_kj  += Q_in
        Q_out_kj += Q_out
        dT = T_pot - T_before
        if dT != 0.0:
            if m_w_before > 0.0:
                MCp_track = (m_food * cp_food) + (m_w_before * main_logic.CP_WATER) + (m_pot * cp_pot)
            else:
                MCp_track = (m_food * cp_food) + (m_pot * cp_pot)
            Q_sensible_kj += MCp_track * dT
        dm_evap = m_w_before - m_water
        if dm_evap > 0.0 and lid_fac > 0.0:
            Q_evap_kj += (dm_evap / lid_fac) * main_logic.L_V

        t_elapsed += main_logic.dt

        if t_elapsed > main_logic.MAX_SIMULATION_TIME:
            break

        if m_water <= main_logic.M_WATER_DRY and not flag_dry:
            flag_dry = True
        if T_pot > main_logic.T_OVERHEAT_C and not flag_over:
            flag_over = True

        tick += 1
        if tick % 60 == 0 or t_elapsed >= t_total_s:
            tick_log.append({
                "t_s": t_elapsed, "T_c": T_pot,
                "m_w_kg": m_water, "t_remaining_s": max(0.0, t_total_s - t_elapsed),
            })

        # ── Live LCD telemetry update ─────────────────────────────────────────
        if tick % lcd_update_interval == 0:
            t_remain = max(0.0, t_total_s - t_elapsed)
            lcd_write_line(1, "T:{:.1f}C  W:{:.0f}g".format(T_pot, m_water * 1000))
            lcd_write_line(2, "t:{:.0f}/{:.0f}s".format(t_elapsed, t_total_s))
            pct = min(100.0, (t_elapsed / t_total_s) * 100.0)
            bar_len = 14
            filled = int(pct / 100.0 * bar_len)
            bar = "[" + "#" * filled + "-" * (bar_len - filled) + "]"
            lcd_write_line(3, bar + " {:.0f}%".format(pct))

        # ── Check for DANGER conditions during loop ──────────────────────────
        if flag_dry or flag_over:
            # Immediately store results and break for danger alarm
            break

    # Store results back into inp
    inp["t_elapsed_s"]      = t_elapsed
    inp["T_pot_c"]          = T_pot
    inp["m_water_current"]  = m_water
    inp["flag_dry_boil"]    = flag_dry
    inp["flag_overheat"]    = flag_over
    inp["t_boil_reached_s"] = t_boil_reached
    inp["tick_log"]         = tick_log
    inp["P_in_kw"]          = P_in_kw_loop
    inp["Q_in_kj"]          = Q_in_kj
    inp["Q_out_kj"]         = Q_out_kj
    inp["Q_sensible_kj"]    = Q_sensible_kj
    inp["Q_evap_kj"]        = Q_evap_kj

    # ── Post-process (dynamic margin + pellet calc) ──────────────────────────
    inp = main_logic.post_process(inp)

    return inp


def display_results(inp):
    """
    Display final results on LCD + trigger appropriate alarm.
    """
    # ── Check DANGER flags FIRST ─────────────────────────────────────────────
    if inp["flag_dry_boil"] or inp["flag_overheat"]:
        # DANGER ALARM
        if inp["flag_dry_boil"]:
            lcd_show("!! DANGER !!", "DRY-BOIL DETECTED", "Water = 0g!", "PRESS BTN TO STOP")
        else:
            lcd_show("!! DANGER !!", "OVERHEAT >150C!", "T={:.1f}C".format(inp["T_pot_c"]), "PRESS BTN TO STOP")
        danger_alarm()

        # After acknowledgment, show details
        lcd_show("DANGER DETAILS:",
                 "T={:.1f}C W={:.0f}g".format(inp["T_pot_c"], inp["m_water_current"] * 1000),
                 "t={:.1f}min".format(inp["t_elapsed_s"] / 60.0),
                 "Btn=continue")
        while not was_pressed():
            time.sleep_ms(50)
        tick_feedback()
        return

    # ── SUCCESS — Normal completion ──────────────────────────────────────────
    success_alarm()

    pellets_g = inp["pellets_required_g"]
    margin_pct = inp["procurement_margin_pct"]
    t_min = inp["t_elapsed_s"] / 60.0

    # Screen 1: Pellet recommendation
    lcd_show("== COOK COMPLETE ==",
             "Pellets: {:.1f}g".format(pellets_g),
             "Margin: {:.0f}% ({})".format(margin_pct, inp["margin_reason"][:7]),
             "Time: {:.1f}min".format(t_min))

    # Wait for button to show more details
    while not was_pressed():
        time.sleep_ms(50)
    tick_feedback()

    # Screen 2: Energy summary
    lcd_show("ENERGY SUMMARY",
             "Q_in: {:.0f}kJ".format(inp.get("Q_in_kj", 0)),
             "Q_out:{:.0f} Q_s:{:.0f}".format(inp.get("Q_out_kj", 0), inp.get("Q_sensible_kj", 0)),
             "Q_evap: {:.0f}kJ".format(inp.get("Q_evap_kj", 0)))

    while not was_pressed():
        time.sleep_ms(50)
    tick_feedback()

    # Screen 3: Final vessel state
    lcd_show("VESSEL STATE",
             "T_pot: {:.1f}C".format(inp["T_pot_c"]),
             "Water: {:.0f}g left".format(inp["m_water_current"] * 1000),
             "Btn=new simulation")

    while not was_pressed():
        time.sleep_ms(50)
    tick_feedback()


# =============================================================================
# MAIN LOOP
# =============================================================================

def main():
    """Master boot loop — runs simulation wizard repeatedly."""
    while True:
        try:
            # Phase 1: Collect all inputs via LCD menus
            inp = collect_inputs()

            # Pellet selection (after all other inputs)
            pellet_names = get_pellet_names()
            _, pellet_name = menu_select("PELLET TYPE", pellet_names)
            inp["pellet_name"] = pellet_name
            pellet = get_pellet(pellet_name)
            inp["pellet"] = pellet
            inp["gcv_kj_kg"] = pellet.conservative_gcv_kj

            # Phase 2+3: Run simulation + post-process
            inp = run_simulation(inp)

            # Phase 4: Display results + alarms
            display_results(inp)

        except Exception as e:
            lcd_show("!! ERROR !!", str(e)[:20], str(e)[20:40] if len(str(e)) > 20 else "", "Btn=restart")
            while not was_pressed():
                time.sleep_ms(50)
            tick_feedback()


# =============================================================================
# BOOT ENTRY POINT
# =============================================================================

main()

