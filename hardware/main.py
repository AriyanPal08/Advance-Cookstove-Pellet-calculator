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
#   Tick Feedback:   10ms LED blink + 10ms 1kHz beep
#   Success Alarm:   Timer countdown finished (continuous 1kHz siren + LED)
#   Danger Alarm:    Continuous alternating 800/1200Hz siren + rapid LED toggle
#   Invalid Alarm:   3 rapid flashes + beeps for impossible combinations
# =============================================================================

import machine
import time
import math

from food_db    import FOOD_DB, get_dish_names, get_dish
from pellet_db  import PELLET_DB, get_pellet_names, get_pellet
from utensil_db import UTENSIL_DB, get_utensil_names, get_utensil
import main_logic

# =============================================================================
# HARDWARE PIN SETUP — WITH ERROR HANDLING
# =============================================================================

# I2C LCD with fallback
lcd = None
try:
    i2c = machine.I2C(0, sda=machine.Pin(21), scl=machine.Pin(22), freq=400000)
    time.sleep_ms(200)
    from esp8266_i2c_lcd import I2cLcd
    LCD_ADDR = 0x27
    LCD_ROWS = 4
    LCD_COLS = 20
    lcd = I2cLcd(i2c, LCD_ADDR, LCD_ROWS, LCD_COLS)
except Exception as e:
    # LCD initialization failed — use buzzer to alert user
    buzzer_pin = machine.PWM(machine.Pin(27), freq=1000, duty=0)
    for _ in range(5):
        buzzer_pin.duty(512)
        time.sleep_ms(200)
        buzzer_pin.duty(0)
        time.sleep_ms(200)
    # Crash with info
    raise Exception("LCD Init Failed: " + str(e))

# Encoder setup (should always work)
enc_clk = machine.Pin(32, machine.Pin.IN, machine.Pin.PULL_UP)
enc_dt  = machine.Pin(33, machine.Pin.IN, machine.Pin.PULL_UP)
enc_sw  = machine.Pin(25, machine.Pin.IN, machine.Pin.PULL_UP)

led = machine.Pin(26, machine.Pin.OUT)
led.value(0)

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
    global _enc_pressed, _last_btn_time
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_btn_time) < BTN_DEBOUNCE_MS:
        return
    _last_btn_time = now
    _enc_pressed = True

enc_clk.irq(trigger=machine.Pin.IRQ_FALLING, handler=_enc_isr)
enc_sw.irq(trigger=machine.Pin.IRQ_FALLING, handler=_btn_isr)

def get_encoder_pos():
    return _enc_pos

def set_encoder_pos(val):
    global _enc_pos
    _enc_pos = val

def was_pressed():
    global _enc_pressed
    if _enc_pressed:
        _enc_pressed = False
        return True
    return False


# =============================================================================
# LED & BUZZER ALARM SYSTEM
# =============================================================================

def tick_feedback():
    """Tactile feedback: 10ms LED blink + 10ms 1kHz beep."""
    led.value(1)
    buzzer.freq(1000)
    buzzer.duty(512)
    time.sleep_ms(10)
    buzzer.duty(0)
    led.value(0)

def warn_alarm():
    """Soft advisory warning: 2 medium beeps + LED. Less severe than invalid_combo_alarm."""
    global _enc_pressed
    _enc_pressed = False
    for _ in range(2):
        led.value(1)
        buzzer.freq(900)
        buzzer.duty(400)
        time.sleep_ms(180)
        buzzer.duty(0)
        led.value(0)
        time.sleep_ms(120)
    while not was_pressed():
        time.sleep_ms(50)
    tick_feedback()

def invalid_combo_alarm():
    """Invalid setup alarm: 3 rapid blinks + 1500Hz beeps. Hard block."""
    global _enc_pressed
    _enc_pressed = False
    for _ in range(3):
        led.value(1)
        buzzer.freq(1500)
        buzzer.duty(512)
        time.sleep_ms(100)
        buzzer.duty(0)
        led.value(0)
        time.sleep_ms(100)
    while not was_pressed():
        time.sleep_ms(50)
    tick_feedback()

def timer_alarm():
    """
    Time-over cooking alarm: continuous 1kHz siren + rapid LED toggle.
    Runs until button press acknowledgment.
    """
    global _enc_pressed
    _enc_pressed = False
    while True:
        if was_pressed():
            buzzer.duty(0)
            led.value(0)
            return
        buzzer.freq(1000)
        buzzer.duty(512)
        led.value(1)
        time.sleep_ms(200)
        buzzer.duty(0)
        led.value(0)
        time.sleep_ms(200)

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


def boot_jingle():
    
    # Frequencies (Hz)
    A_S = 466; B = 494; D_S = 622
    F = 698; F_S = 740; G_S = 831
    R = 0 # Musical Rest

    # Timings (Sped up for a punchy ~10 second intro)
    T_LONG = 300
    T_SHORT = 175
    P_SHORT = 60   # Pause between notes
    P_LONG = 200   # Pause between phrases

    # Riff 1: A# B D# A# A#
    riff_main = [
        (A_S, T_LONG), (R, P_SHORT), (B, T_SHORT), (R, P_SHORT),
        (D_S, T_SHORT), (R, P_SHORT), (A_S, T_LONG), (R, P_SHORT),
        (A_S, T_LONG), (R, P_LONG)
    ]

    # Riff 2: A# B D# F F
    riff_alt1 = [
        (A_S, T_LONG), (R, P_SHORT), (B, T_SHORT), (R, P_SHORT),
        (D_S, T_SHORT), (R, P_SHORT), (F, T_LONG), (R, P_SHORT),
        (F, T_LONG), (R, P_LONG)
    ]

    # Riff 3: G# F# F D# D#
    riff_alt2 = [
        (G_S, T_LONG), (R, P_SHORT), (F_S, T_SHORT), (R, P_SHORT),
        (F, T_SHORT), (R, P_SHORT), (D_S, T_LONG), (R, P_SHORT),
        (D_S, T_LONG), (R, P_LONG)
    ]

    # Assemble the shortened tab sequence
    melody = []
    for _ in range(2): melody.extend(riff_main)  # A# B D# A# A# (x2)
    melody.extend(riff_alt1)                     # A# B D# F F
    for _ in range(2): melody.extend(riff_alt2)  # G# F# F D# D# (x2)
    for _ in range(2): melody.extend(riff_main)  # A# B D# A# A# (x2)

    # Playback loop with Encoder Button Skip Feature
    for freq, duration in melody:
        if was_pressed(): 
            break # Skip the rest of the song if knob is clicked
            
        if freq == 0:
            buzzer.duty(0)
            led.value(0)
        else:
            buzzer.freq(freq)
            buzzer.duty(512)
            led.value(1)
        time.sleep_ms(duration)

    buzzer.duty(0)
    led.value(0)


def boil_milestone_blip():
    """
    Single double-beep + LED flash when boiling point is first reached.
    Called once mid-simulation as a progress milestone.
    """
    for _ in range(2):
        led.value(1)
        buzzer.freq(880)
        buzzer.duty(350)
        time.sleep_ms(80)
        buzzer.duty(0)
        led.value(0)
        time.sleep_ms(60)


def heartbeat_tick():
    """
    Double-blink LED only (no buzzer). Called in the last 60 s of cooking
    to give a visible "almost done" pulse without waking people up.
    """
    for _ in range(2):
        led.value(1)
        time.sleep_ms(60)
        led.value(0)
        time.sleep_ms(80)


def pellet_load_flash(pellets_g):
    """
    Flash LED to indicate pellet load tier after results are shown:
      1 flash  = light  (< 200 g)
      2 flashes = medium (200–599 g)
      3 flashes = heavy  (≥ 600 g)
    """
    if pellets_g < 200:
        flashes = 1
    elif pellets_g < 600:
        flashes = 2
    else:
        flashes = 3
    time.sleep_ms(300)
    for _ in range(flashes):
        led.value(1)
        buzzer.freq(660)
        buzzer.duty(300)
        time.sleep_ms(150)
        buzzer.duty(0)
        led.value(0)
        time.sleep_ms(200)


# =============================================================================
# LCD HELPER FUNCTIONS
# =============================================================================

def lcd_clear():
    lcd.clear()
    time.sleep_ms(5)

def lcd_show(line0="", line1="", line2="", line3=""):
    lcd_clear()
    lines = [line0, line1, line2, line3]
    for i, txt in enumerate(lines):
        if txt:
            lcd.move_to(0, i)
            lcd.putstr(txt[:LCD_COLS])

def lcd_write_line(row, text):
    lcd.move_to(0, row)
    lcd.putstr(("{:<" + str(LCD_COLS) + "}").format(text[:LCD_COLS]))

def fmt_trunc(text, width=20):
    if len(text) > width:
        return text[:width - 1] + "."
    return text


# =============================================================================
# INTERACTIVE MENU FUNCTIONS
# =============================================================================

def menu_select(title, options):
    idx = 0
    n = len(options)
    set_encoder_pos(0)
    last_pos = 0
    lcd_show(title, "> " + fmt_trunc(options[idx], 18), "", "Turn=Scroll Btn=OK")

    while True:
        pos = get_encoder_pos()
        if pos != last_pos:
            tick_feedback()
            diff = pos - last_pos
            last_pos = pos
            idx = (idx + diff) % n
            lcd_write_line(1, "> " + fmt_trunc(options[idx], 18))
            nxt = (idx + 1) % n
            lcd_write_line(2, "  " + fmt_trunc(options[nxt], 18))

        if was_pressed():
            tick_feedback()
            lcd_write_line(3, "OK: " + fmt_trunc(options[idx], 15))
            time.sleep_ms(300)
            return (idx, options[idx])
        time.sleep_ms(20)

def menu_adjust_float(title, unit, default, lo, hi, step=0.5):
    val = default
    set_encoder_pos(0)
    last_pos = 0
    lcd_show(title, "Value: {:.1f} {}".format(val, unit),
             "Range: {:.1f}-{:.1f}".format(lo, hi), "Turn=Adj  Btn=OK")

    while True:
        pos = get_encoder_pos()
        if pos != last_pos:
            tick_feedback()
            diff = pos - last_pos
            last_pos = pos
            val += diff * step
            if val < lo: val = lo
            if val > hi: val = hi
            lcd_write_line(1, "Value: {:.1f} {}".format(val, unit))

        if was_pressed():
            tick_feedback()
            lcd_write_line(3, "OK: {:.1f} {}".format(val, unit))
            time.sleep_ms(300)
            return val
        time.sleep_ms(20)

def menu_adjust_int(title, unit, default, lo, hi):
    val = default
    set_encoder_pos(0)
    last_pos = 0
    lcd_show(title, "Value: {} {}".format(val, unit),
             "Range: {}-{}".format(lo, hi), "Turn=Adj  Btn=OK")

    while True:
        pos = get_encoder_pos()
        if pos != last_pos:
            tick_feedback()
            diff = pos - last_pos
            last_pos = pos
            val += diff
            if val < lo: val = lo
            if val > hi: val = hi
            lcd_write_line(1, "Value: {} {}".format(val, unit))

        if was_pressed():
            tick_feedback()
            lcd_write_line(3, "OK: {} {}".format(val, unit))
            time.sleep_ms(300)
            return val
        time.sleep_ms(20)


# =============================================================================
# SAFETY VALIDATION LOGIC
# =============================================================================

UTENSIL_CAPACITY_L = {
    "Aluminium Pot 2L": 2.0,
    "Aluminium Pot 3L": 3.0,
    "Aluminium Pot 5L": 5.0,
    "Aluminium Pot 8L": 8.0,
    "Pressure Cooker 2L": 2.0,
    "Pressure Cooker 3L": 3.0,
    "Pressure Cooker 5L": 5.0,
    "Pressure Cooker 7.5L": 7.5,
    "Kadhai / Wok 2.5L": 2.5,
    "Kadhai / Wok 4L": 4.0,
    "Kadhai / Wok 6L": 6.0,
    "Stainless Steel Pot 3L": 3.0,
    "Stainless Steel Pot 5L": 5.0,
    "Cast Iron Tawa": 0.5,
    "Cast Iron Frying Pan 26cm": 1.5,
}

# Per-dish utensil type preference: what utensil category is needed
# Key: part of dish name, Value: required word in utensil name
DISH_UTENSIL_PREF = {
    "Roti":   "Tawa",          # Roti needs a Tawa, not a pot
    "Sambar": "Pot",           # Sambar needs a Pot, not a Tawa
}

# Dishes that are beverages (should NOT go in pressure cooker)
BEVERAGE_DISHES = {"Tea (Chai)", "Coffee", "Boiling Milk"}

# Realistic max servings per pot capacity bucket (L)
# Updated to cover ALL utensil sizes defined in UTENSIL_CAPACITY_L
CAP_MAX_SERVINGS = {
    0.5: 1,    # Cast Iron Tawa (dry cooking only, 1 roti)
    1.5: 2,    # Cast Iron Frying Pan (frying dish for 2 people)
    2.0: 3,    # Aluminium Pot 2L
    2.5: 4,    # Kadhai / Wok 2.5L
    3.0: 5,    # Pressure Cooker 3L, Aluminium Pot 3L
    4.0: 7,    # Kadhai / Wok 4L
    5.0: 10,   # Pressure Cooker 5L, Aluminium Pot 5L
    6.0: 12,   # Kadhai / Wok 6L
    7.5: 16,   # Pressure Cooker 7.5L
    8.0: 18,   # Aluminium Pot 8L
}

def validate_inputs(inp):
    """
    Check for physically impossible or illogical combinations.
    Returns (error_key, detail_line) tuple if invalid, or None if valid.
    Severity determines which alarm is triggered in main().
    """
    utensil_name = inp["utensil_name"]
    utensil      = inp["utensil"]
    dish         = inp["dish"]
    dish_name    = inp["dish_name"]
    max_cap      = UTENSIL_CAPACITY_L.get(utensil_name, 5.0)
    water_l      = inp["m_water_initial"]
    food_kg      = inp["m_food"]
    n            = inp["portions"]
    is_pc        = inp["is_pc"]
    k_conv       = inp["k_conv_current"]
    lid          = inp["lid_factor"]

    # ── 1. Physical overflow (HARD) ──────────────────────────────────────────
    # Total contents (water + food solid mass) exceed pot volume.
    if (water_l + food_kg) > max_cap:
        return ("overflow",
                "Tot {:.1f}L > {:.1f}L pot".format(water_l + food_kg, max_cap))

    # ── 2. Too many servings for the pot (HARD) ──────────────────────────────
    # Each serving for standard dishes needs ~0.3–0.5L. Cap is derived from
    # pot capacity. This catches "20 people in a 2L pot" scenarios.
    # Only applies to standard per-person dishes (not smart-unit or variable).
    if not dish.qty_prompt and not dish.variable_water:
        n_int = int(n)
        hard_max = CAP_MAX_SERVINGS.get(max_cap, int(max_cap * 2))
        if n_int > hard_max:
            return ("too_many_people",
                    "{} people in {}L pot".format(n_int, max_cap))

    # ── 3. Pressure Cooker with beverage (SOFT warning) ──────────────────────
    # Boiling milk/tea/coffee in a PC makes no practical sense and risks
    # boil-over fouling the pressure valve.
    if is_pc and dish_name in BEVERAGE_DISHES:
        return ("pc_beverage",
                "{} in pressure cooker".format(dish_name[:14]))

    # ── 4. Wrong utensil for Roti (SOFT warning) ─────────────────────────────
    # Roti is dry-cooked on a Tawa. Using a pot or kadhai gives wrong results.
    if "Roti" in dish_name and "Tawa" not in utensil_name and "Pan" not in utensil_name:
        return ("roti_wrong_utensil",
                "Roti needs a Tawa")

    # ── 5. Pressure Cooker with too little water (HARD) ──────────────────────
    # PCs need steam. < 0.2L means no steam can build — dangerous in reality.
    if is_pc and water_l < 0.2:
        return ("pc_dry",
                "PC needs >= 0.2L water")

    # ── 6. Open pot in high wind (SOFT warning) ───────────────────────────────
    # Extremely wasteful — heat blows away. Physics still runs but user
    # should know this setup wastes a lot of pellets.
    if k_conv >= 35.0 and lid == main_logic.LID_FACTOR_OFF:
        return ("wind_open",
                "Strong wind, lid off")

    # ── 7. Pot mass override is unrealistic (SOFT warning) ───────────────────
    base_mass = utensil.mass_kg
    if inp["m_pot"] > 3.0 * base_mass:
        return ("pot_heavy",
                "Pot mass seems high")
    if inp["m_pot"] < 0.3 * base_mass:
        return ("pot_light",
                "Pot mass seems low")

    # ── 8. Milk volume > utensil capacity (HARD) ─────────────────────────────
    # Smart-unit milk: qty is in litres. Check it fits the pot.
    if dish_name == "Boiling Milk" and dish.qty_is_float:
        milk_l = water_l + food_kg  # already scaled in collect_inputs
        if milk_l > max_cap:
            return ("milk_overflow",
                    "{:.1f}L milk > {:.1f}L pot".format(milk_l, max_cap))

    # ── 9. Liquid dish on a Tawa / Frying Pan (HARD) ───────────────────────
    # Tawas and flat pans have no side walls. Any dish with >0.15 kg of
    # water per serving will simply spill off a flat pan.
    _NEEDS_WALLS = {"Dal Tadka", "Sambar", "Chicken Curry", "Egg Curry",
                    "Mix Veg Curry", "Chola (Soaked Chickpea)",
                    "Rajma (Soaked Red Kidney Bean)", "Normal Rice",
                    "Plain Water Boiling", "Tea (Chai)", "Coffee",
                    "Boiling Milk", "Kadhai Paneer"}
    _FLAT_UTENSILS = {"Cast Iron Tawa", "Cast Iron Frying Pan 26cm"}
    if dish_name in _NEEDS_WALLS and utensil_name in _FLAT_UTENSILS:
        return ("liquid_on_tawa",
                "Flat pan for wet dish")

    # ── 10. Roti in a Pressure Cooker (HARD) ───────────────────────────────
    # Roti is a dry flatbread. A pressure cooker seals steam inside —
    # you cannot roast/dry-cook inside a sealed PC. The result would be
    # soggy uncooked dough, not roti.
    if "Roti" in dish_name and is_pc:
        return ("roti_in_pc",
                "Can't make roti in PC")

    # ── 11. Plain Water Boiling in a Kadhai / Wok (SOFT warning) ────────────
    # Kadhais are wide and shallow. Boiling large volumes of water in them
    # leads to extreme evaporation and very fast water loss. The physics
    # engine will still run, but the result is thermally inefficient.
    if dish_name == "Plain Water Boiling" and "Kadhai" in utensil_name:
        return ("water_in_kadhai",
                "Kadhai not for boiling")

    return None


_HARD_ERRORS = {"overflow", "too_many_people", "pc_dry", "milk_overflow",
                "liquid_on_tawa", "roti_in_pc"}

_FRIENDLY_MSG = {
    "overflow":          ("Pot is too small!",   "Too much water and",    "food for this pot.",    "Try a bigger pot."),
    "too_many_people":   ("Too many people!",     "This pot is too small", "for that many folks.",  "Use a bigger pot."),
    "pc_beverage":       ("Use a normal pot!",    "Tea, coffee & milk",    "don't need a pressure", "cooker. Press OK."),
    "roti_wrong_utensil":("Wrong pan for Roti!",  "Roti cooks best on",    "a flat Tawa or Pan.",   "Press to continue."),
    "pc_dry":            ("Not enough water!",    "Pressure cooker needs", "at least 0.2L water.",  "Add more water."),
    "wind_open":         ("Cover your pot!",      "Strong wind + open pot","wastes a lot of fuel.", "Press to continue."),
    "pot_heavy":         ("Pot mass too high!",   "Did you set the right", "pot size? Check it.",   "Press to continue."),
    "pot_light":         ("Pot mass too low!",    "Did you set the right", "pot size? Check it.",   "Press to continue."),
    "milk_overflow":     ("Too much milk!",        "That much milk won't",  "fit in this pot.",      "Use a bigger pot."),
    "liquid_on_tawa":    ("Wrong pan!",            "Curries and soups",     "need a deep pot,",      "not a flat tawa."),
    "roti_in_pc":        ("Roti needs open heat!", "You can't make roti",   "in a sealed pressure",  "cooker. Use Tawa."),
    "water_in_kadhai":   ("Use a deep pot!",       "Kadhais are shallow.",  "Water evaporates fast.","Try a pot instead."),
}


# =============================================================================
# MAIN SIMULATION FLOW
# =============================================================================

def collect_inputs():
    inp = {}
    lcd_show("IIT DELHI COOKSTOVE", "  ESP32 Simulator", "    V10 / 1Hz", "Press btn to start")
    boot_jingle()
    while not was_pressed():
        time.sleep_ms(50)
    tick_feedback()

    dish_names = get_dish_names()
    _, dish_name = menu_select("1/7 SELECT DISH", dish_names)
    inp["dish_name"] = dish_name
    dish = get_dish(dish_name)
    inp["dish"] = dish

    if dish.qty_prompt:
        if dish.qty_is_float:
            qty = menu_adjust_float("2/7 " + dish.qty_prompt[:14], dish.qty_unit, dish.qty_default, dish.qty_min, dish.qty_max, step=0.5)
        else:
            qty = float(menu_adjust_int("2/7 " + dish.qty_prompt[:14], dish.qty_unit, int(dish.qty_default), int(dish.qty_min), int(dish.qty_max)))
        inp["portions"] = qty
    elif dish.variable_water:
        inp["water_liters"] = menu_adjust_float("2/7 WATER VOLUME", "L", 5.0, 0.5, 50.0, step=0.5)
        inp["portions"] = 1
    else:
        inp["portions"] = menu_adjust_int("2/7 SERVINGS", "people", 4, 1, 20)
    
    n = inp["portions"]
    inp["t_ambient_c"] = menu_adjust_float("3/7 AMBIENT TEMP", "C", 25.0, 15.0, 45.0, step=1.0)
    
    wind_labels = list(main_logic.WIND_TIERS.keys())
    _, wind_choice = menu_select("4/7 WIND FACTOR", wind_labels)
    inp["wind_label"] = wind_choice
    inp["k_conv_current"] = main_logic.WIND_TIERS[wind_choice]

    utensil_names = get_utensil_names()
    _, utensil_name = menu_select("5/7 UTENSIL", utensil_names)
    utensil = get_utensil(utensil_name)
    inp["utensil_name"] = utensil_name
    inp["utensil"] = utensil
    inp["cp_pot"] = utensil.cp_kj_kgk
    inp["is_pc"] = utensil.is_pressure
    inp["emissivity"] = main_logic._emissivity_for_utensil(utensil)

    inp["m_pot"] = menu_adjust_float("6/7 POT MASS", "kg", utensil.mass_kg, 0.1, 10.0, step=0.05)

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
    Pure silent calculator — runs the 1Hz physics loop as fast as the CPU
    allows to compute cook time and pellet load. Nothing is shown on LCD
    during the loop. The loop is a mathematical predictor, not a timer.
    """
    geom = main_logic.compute_vessel_geometry(
        inp["m_water_initial"], inp["utensil_name"], inp["lid_factor"]
    )
    inp.update(geom)

    lcd_show("CALCULATING...",
             "Finding your cook",
             "time and pellet load.",
             "Please wait...")

    eta_geom = inp["eta_geom"]
    P_in_kw = (main_logic.FAN_HIGH / 3600.0) * inp["gcv_kj_kg"] * eta_geom
    inp["P_in_kw"] = P_in_kw

    preview = main_logic.estimate_cook_time(
        m_food=inp["m_food"], cp_food=inp["cp_food"], m_water=inp["m_water_initial"],
        m_pot=inp["m_pot"], cp_pot=inp["cp_pot"], t_kinetic_s=inp["t_kinetic_base_s"],
        P_in_kw=P_in_kw, A_m2=inp["A_m2"], k_conv=inp["k_conv_current"],
        emissivity=inp["emissivity"], T_amb=inp["t_ambient_c"], lid_fac=inp["lid_factor"]
    )

    t_heat_s = preview["t_heat_s"]
    if preview["heat_cannot_rise"] > 0.5 or t_heat_s <= 0.0:
        t_heat_s = 0.0

    t_safety = main_logic.compute_safety_buffer_s(t_heat_s, inp["k_conv_current"], inp["m_water_initial"])
    t_total_s = t_heat_s + inp["t_kinetic_base_s"] + t_safety

    if t_total_s > 14400:  # > 4 hours
        inp["invalid_combo_msg"] = ("Time > 4 Hours!", "Physically absurd combo")
        return inp

    inp["t_heat_est_s"]      = t_heat_s
    inp["t_boil_est_s"]      = preview["t_boil_s"]
    inp["t_safety_buffer_s"] = t_safety
    inp["t_preview_s"]       = preview["t_preview_s"]
    inp["t_total_s"]         = t_total_s

    # ── FAST FORWARD (Skip Slow Loop) ────────────────────────────────────────
    # The ESP32 is too slow to run a 1Hz loop for hours. 
    # We already have the time and water from the estimate_cook_time preview!
    inp = main_logic.zero_state(inp)
    
    inp["t_elapsed_s"]     = t_total_s
    inp["T_pot_c"]         = 100.0 if t_heat_s > 0 else inp["t_ambient_c"]
    inp["m_water_current"] = preview.get("m_water_end_kg", 0.0)
    inp["flag_dry_boil"]   = (inp["m_water_current"] <= 0)
    inp["flag_overheat"]   = False
    inp["t_boil_reached_s"] = preview["t_boil_s"] if preview["t_boil_s"] > 0 else None
    
    # Dummy energy values so post_process() doesn't throw KeyError
    inp["P_in_kw"]       = P_in_kw
    inp["Q_in_kj"]       = 0.0
    inp["Q_sensible_kj"] = 0.0
    inp["Q_evap_kj"]     = 0.0
    inp["Q_out_kj"]      = preview.get("Q_out_accum_kj", 0.0)

    inp = main_logic.post_process(inp)

    if inp["pellets_required_g"] > 1300 or inp["pellets_required_g"] < 50:
        inp["invalid_combo_msg"] = ("Pellets Out of Bound", "Limit: 50g-1300g")

    return inp


def run_real_timer(t_total_s, t_boil_s):
    """
    Real hardware countdown using time.ticks_ms().
    This is the ACTUAL cooking timer — one real second = one real second.
    t_total_s  : total cook duration in seconds (from physics engine)
    t_boil_s   : simulated boil time (used to fire the boil blip milestone
                  at the proportionally correct real-time moment)
    """
    start_ms = time.ticks_ms()
    t_total_ms = int(t_total_s * 1000)

    # Pre-compute the real-time boil milestone (proportional)
    boil_ms = int((t_boil_s / t_total_s) * t_total_ms) if t_boil_s and t_total_s > 0 else -1
    _boil_blip_done = boil_ms <= 0  # skip if no boiling expected

    lcd_show("COOKING IN PROGRESS",
             "Starting timer...",
             "Alarm rings when done",
             "Do not remove pot")
    time.sleep_ms(500)

    last_lcd_s = -1

    while True:
        now_ms    = time.ticks_ms()
        elapsed_ms = time.ticks_diff(now_ms, start_ms)
        elapsed_s  = elapsed_ms / 1000.0
        remaining_s = max(0.0, t_total_s - elapsed_s)
        remaining_min = remaining_s / 60.0

        # ── Boil milestone blip at proportional real-time moment ──────────────
        if not _boil_blip_done and elapsed_ms >= boil_ms:
            boil_milestone_blip()
            _boil_blip_done = True

        # ── Countdown heartbeat LED in real final 60 seconds ──────────────────
        if remaining_s <= 60.0:
            heartbeat_tick()

        # ── Update LCD once per real second ───────────────────────────────────
        cur_s = int(elapsed_s)
        if cur_s != last_lcd_s:
            last_lcd_s = cur_s
            pct = min(100, int((elapsed_s / t_total_s) * 100))
            bar_len = 16
            filled = int(pct / 100.0 * bar_len)
            bar = "#" * filled + "-" * (bar_len - filled)
            if remaining_min >= 1.0:
                lcd_write_line(1, "{:.0f} min remaining".format(remaining_min))
            else:
                lcd_write_line(1, "Almost ready!       ")
            lcd_write_line(2, "[{}]".format(bar))
            lcd_write_line(3, "{}% done".format(pct))

        # ── Timer complete ─────────────────────────────────────────────────────
        if elapsed_ms >= t_total_ms:
            break

        time.sleep_ms(200)  # poll every 200ms for smooth heartbeat


def display_results(inp):
    # ── Step 1: Calculate Physics Suggestion ─────────────────────────────────
    t_min_suggested = int(inp["t_total_s"] / 60.0)
    
    # ── Step 2: User Inputs ACTUAL Time ──────────────────────────────────────
    lcd_show("PHYSICS SUGGESTION",
             "Time: ~{} min".format(t_min_suggested),
             "Press BTN to set",
             "your actual time")
    while not was_pressed(): time.sleep_ms(50)
    tick_feedback()

    user_min = menu_adjust_int("SET COOK TIME", "min", t_min_suggested, 1, 240)
    user_total_s = user_min * 60.0

    # ── Step 3: Recalculate Pellets for User's Time ──────────────────────────
    margin_factor = inp.get("procurement_margin_factor", 1.08)
    pellets_g = (user_total_s / 3600.0) * main_logic.FAN_HIGH * 1000.0 * margin_factor

    # Hard cap at 1300g per user rules
    if pellets_g > 1300:
        pellets_g = 1300

    # ── Step 4: Show Final Pellets & Start ───────────────────────────────────
    lcd_show("LOAD PELLETS",
             "Time   : {:.0f} min".format(user_min),
             "Pellets: {:.0f} g".format(pellets_g),
             "Press BTN to START")

    while not was_pressed(): time.sleep_ms(50)
    tick_feedback()

    # ── Step 5: Run the REAL hardware countdown timer ────────────────────────
    t_boil_s = inp.get("t_boil_reached_s") or 0
    run_real_timer(user_total_s, t_boil_s)

    # ── Step 6: Timer done — fire alarm until acknowledged ───────────────────
    lcd_show("FOOD IS READY!",
             "Your food is done.",
             "Turn off the stove.",
             "Press to confirm")
    timer_alarm()

    # ── Step 7: Summary screen ───────────────────────────────────────────────
    lcd_show("COOK COMPLETE",
             "Cook time: {:.0f} min".format(user_min),
             "Pellets used: {:.0f}g".format(pellets_g),
             "Press to cook again")
    while not was_pressed(): time.sleep_ms(50)
    tick_feedback()

    # Pellet load indicator: 1/2/3 LED flashes
    pellet_load_flash(pellets_g)


def main():
    while True:
        try:
            inp = collect_inputs()
            
            pellet_names = get_pellet_names()
            _, pellet_name = menu_select("PELLET TYPE", pellet_names)
            inp["pellet_name"] = pellet_name
            pellet = get_pellet(pellet_name)
            inp["pellet"] = pellet
            inp["gcv_kj_kg"] = pellet.conservative_gcv_kj

            # Run all validation checks
            err = validate_inputs(inp)
            if err:
                err_key, detail = err
                msg = _FRIENDLY_MSG.get(err_key, ("Invalid setup!", detail, "Please try again.", "Press to go back."))
                lcd_show(msg[0], msg[1], msg[2], msg[3])
                if err_key in _HARD_ERRORS:
                    invalid_combo_alarm()  # 3 rapid beeps — must fix before continuing
                    continue               # restart wizard
                else:
                    warn_alarm()           # 2 soft beeps — advisory, still runs
                    # fall through to run simulation anyway

            inp = run_simulation(inp)
            display_results(inp)

        except Exception as e:
            lcd_show("Something went wrong",
                     "Please restart the",
                     "device and try again.",
                     "Press to restart")
            while not was_pressed(): time.sleep_ms(50)
            tick_feedback()

main()
