"""
main.py
MicroPython ESP32 Script — Complete 16x2 LCD UI Menu System
IIT Delhi · 1Hz Transient Biomass Cookstove Dashboard
"""

from machine import Pin, I2C, PWM
from time import sleep_ms, ticks_ms
from esp8266_i2c_lcd import I2cLcd

# =============================================================================
# PHYSICS & DATABASE IMPORTS
# =============================================================================
from food_db import FOOD_DB, get_dish_names
from utensil_db import UTENSIL_DB, get_utensil_names
from pellet_db import PELLET_DB, get_pellet_names
from main_logic import (
    compute_vessel_geometry, 
    estimate_cook_time, 
    run_1hz_loop, 
    post_process, 
    zero_state,
    FAN_HIGH
)

# =============================================================================
# 1. HARDWARE INIT
# =============================================================================
# Standard I2C backpack configuration for the 16x2 LCD
i2c = I2C(1, scl=Pin(22), sda=Pin(21), freq=400000)
lcd = I2cLcd(i2c, 0x27, 2, 16)

# KY-040 Rotary Encoder Pins
pin_clk = Pin(32, Pin.IN, Pin.PULL_UP)
pin_dt  = Pin(33, Pin.IN, Pin.PULL_UP)
pin_sw  = Pin(25, Pin.IN, Pin.PULL_UP)

# LED and Buzzer
led = Pin(26, Pin.OUT)
buzzer = PWM(Pin(27), freq=1000, duty=0)

# Global State Variables
dial_pos = 0      
last_enc_time = 0
btn_pressed = False
last_btn_press_time = 0

# =============================================================================
# 2. HARDWARE INTERRUPTS & ALERTS
# =============================================================================
def beep(freq=1000, duration=100):
    """Triggers the buzzer for feedback."""
    buzzer.freq(freq)
    buzzer.duty(512) # 50% volume
    sleep_ms(duration)
    buzzer.duty(0)

def encoder_irq(pin):
    global dial_pos, last_enc_time
    now = ticks_ms()
    
    # 15ms Debounce: completely eliminates bouncy skipping
    if now - last_enc_time > 15:
        # Check DT pin to determine direction on the falling edge of CLK
        if pin_dt.value() == 0:
            dial_pos -= 1  # Decrease / Move Backward
        else:
            dial_pos += 1  # Increase / Move Ahead
        last_enc_time = now

def button_irq(pin):
    global btn_pressed, last_btn_press_time
    now = ticks_ms()
    if now - last_btn_press_time > 300: 
        if pin_sw.value() == 0:
            btn_pressed = True
            last_btn_press_time = now

# Trigger strictly on FALLING edge for perfect accuracy
pin_clk.irq(trigger=Pin.IRQ_FALLING, handler=encoder_irq)
pin_sw.irq(trigger=Pin.IRQ_FALLING, handler=button_irq)

# =============================================================================
# 3. MENU UI COMPONENTS
# =============================================================================
def trunc(text: str, length: int = 16) -> str:
    return text[:length]

def wait_for_click():
    global btn_pressed
    while not btn_pressed:
        sleep_ms(50)
    btn_pressed = False
    beep(1000, 50)  # Short beep confirming the user clicked!

def show_list_menu(title: str, options: list) -> str:
    global dial_pos
    dial_pos = 0
    last_idx = -1
    
    lcd.clear()
    lcd.putstr(trunc(title, 16))
    
    while not btn_pressed:
        idx = dial_pos % len(options)
        if idx != last_idx:
            lcd.move_to(0, 1)
            display_text = "> " + trunc(options[idx], 14)
            lcd.putstr(f"{display_text:<16}") 
            last_idx = idx
        sleep_ms(50)
        
    wait_for_click()
    return options[dial_pos % len(options)]

def show_int_menu(title: str, default: int, min_v: int, max_v: int, unit: str) -> int:
    global dial_pos
    dial_pos = default
    last_val = -999
    
    lcd.clear()
    lcd.putstr(trunc(title, 16))
    
    while not btn_pressed:
        if dial_pos < min_v: dial_pos = min_v
        if dial_pos > max_v: dial_pos = max_v
        
        if dial_pos != last_val:
            lcd.move_to(0, 1)
            display_text = f"<{dial_pos}> {unit}"
            lcd.putstr(f"{display_text:<16}")
            last_val = dial_pos
        sleep_ms(50)
        
    wait_for_click()
    return dial_pos

def show_float_menu(title: str, default: float, min_v: float, max_v: float, unit: str) -> float:
    global dial_pos
    dial_pos = int(default * 10) 
    last_val = -999
    
    lcd.clear()
    lcd.putstr(trunc(title, 16))
    
    while not btn_pressed:
        if dial_pos < int(min_v*10): dial_pos = int(min_v*10)
        if dial_pos > int(max_v*10): dial_pos = int(max_v*10)
        
        if dial_pos != last_val:
            lcd.move_to(0, 1)
            display_val = dial_pos / 10.0
            display_text = f"<{display_val:.1f}> {unit}"
            lcd.putstr(f"{display_text:<16}")
            last_val = dial_pos
        sleep_ms(50)
        
    wait_for_click()
    return dial_pos / 10.0

def show_results(inp: dict):
    global dial_pos
    dial_pos = 0
    last_idx = -1
    
    screens = [
        ("Pellets (Safe):", f"{inp['pellets_required_g']:.1f} g"),
        ("Final Water:", f"{inp['m_water_current']*1000:.1f} g"),
        ("Sim Time:", f"{inp['t_elapsed_s']/60:.1f} min"),
        ("Overheat Alert:", "YES!" if inp["flag_overheat"] else "NO / Safe"),
        ("Dry Boil Alert:", "YES!" if inp["flag_dry_boil"] else "NO / Safe")
    ]
    
    lcd.clear()
    while not btn_pressed:
        idx = dial_pos % len(screens)
        if idx != last_idx:
            lcd.move_to(0, 0)
            lcd.putstr(f"{trunc(screens[idx][0], 16):<16}")
            lcd.move_to(0, 1)
            lcd.putstr(f"{trunc(screens[idx][1], 16):<16}")
            last_idx = idx
        sleep_ms(50)
        
    wait_for_click()
    led.value(0) # Ensure LED turns off when restarting

# =============================================================================
# 4. MASTER FLOW 
# =============================================================================
def main_ui_flow():
    # 1. Boot Screen
    lcd.clear()
    lcd.putstr(" WELCOME \nSYSTEM READY... ")
    led.value(1)
    beep(1500, 150)
    beep(2000, 150)
    led.value(0)
    sleep_ms(1200)
    
    inp = {}
    
    # 2. Select Dish
    dish_names = get_dish_names()
    inp["dish_name"] = show_list_menu("Select Dish:", dish_names)
    dish = FOOD_DB[inp["dish_name"]]
    
    # 3. Portions / Water Volume
    if dish.variable_water:
        inp["water_liters"] = show_float_menu("Water (Liters):", default=5.0, min_v=0.1, max_v=50.0, unit="L")
        inp["portions"] = 1
        inp["m_water_initial"] = inp["water_liters"]
        inp["t_kinetic_base_s"] = 0.0
    else:
        inp["portions"] = show_int_menu("Servings:", default=2, min_v=1, max_v=50, unit="Ppl")
        inp["m_water_initial"] = dish.added_water_per_serving_kg * inp["portions"]
        inp["t_kinetic_base_s"] = float(dish.phases.total_s)

    inp["m_food"] = dish.food_mass_per_serving_kg * inp["portions"]
    inp["cp_food"] = dish.cp_food_kj_kgk
    
    # 4. Ambient Temp
    inp["t_ambient_c"] = show_int_menu("Ambient Temp:", default=25.0, min_v=0.0, max_v=50.0, unit="C")
    
    # 5. Wind Factor
    winds = {"Indoors": 10.0, "Low Wind": 20.0, "Med Wind": 35.0, "High Wind": 50.0}
    wind_choice = show_list_menu("Environment:", list(winds.keys()))
    inp["wind_label"] = wind_choice
    inp["k_conv_current"] = winds[wind_choice]
    
    # 6. Pellet Selection
    pellet_names = get_pellet_names()
    inp["pellet_name"] = show_list_menu("Select Pellet:", pellet_names)
    pellet = PELLET_DB[inp["pellet_name"]]
    inp["gcv_kj_kg"] = pellet.conservative_gcv_kj
    
    # 7. Utensil & Mass
    utensil_names = get_utensil_names()
    inp["utensil_name"] = show_list_menu("Select Pot:", utensil_names)
    utensil = UTENSIL_DB[inp["utensil_name"]]
    inp["cp_pot"] = utensil.cp_kj_kgk
    inp["is_pc"] = utensil.is_pressure
    inp["emissivity"] = 0.35 if not utensil.is_pressure else 0.32 
    
    inp["m_pot"] = show_float_menu("Pot Mass:", default=utensil.mass_kg, min_v=0.1, max_v=20.0, unit="kg")
    
    # 8. Lid State
    if inp["is_pc"]:
        inp["lid_factor"] = 0.0
    else:
        lids = {"Lid ON": 0.15, "Lid OFF": 1.00}
        lid_choice = show_list_menu("Lid State:", list(lids.keys()))
        inp["lid_factor"] = lids[lid_choice]

    # --- EXECUTE PHYSICS ENGINE ---
    geom = compute_vessel_geometry(inp["m_water_initial"], inp["utensil_name"], inp["lid_factor"])
    inp.update(geom)
    P_in_kw = (FAN_HIGH / 3600.0) * inp["gcv_kj_kg"] * inp["eta_geom"]
    
    lcd.clear()
    lcd.putstr("Calculating...")
    
    preview = estimate_cook_time(
        m_food=inp["m_food"], cp_food=inp["cp_food"],
        m_water=inp["m_water_initial"], m_pot=inp["m_pot"], cp_pot=inp["cp_pot"],
        t_kinetic_s=inp["t_kinetic_base_s"], P_in_kw=P_in_kw,
        A_m2=inp["A_m2"], k_conv=inp["k_conv_current"],
        emissivity=inp["emissivity"], T_amb=inp["t_ambient_c"], lid_fac=inp["lid_factor"]
    )
    
    t_heat_s = preview["t_heat_s"] if preview["heat_cannot_rise"] < 0.5 else 0.0
    engine_suggestion_min = int((t_heat_s + inp["t_kinetic_base_s"] + 60.0) / 60.0)
    
    t_total_min = show_int_menu(f"Est: {engine_suggestion_min} min", default=engine_suggestion_min, min_v=1, max_v=300, unit="min")
    inp["t_total_s"] = t_total_min * 60.0

    # Run the 1Hz Simulation
    lcd.clear()
    lcd.putstr("Simulating...")
    lcd.move_to(0, 1)
    lcd.putstr("Please Wait...")
    
    inp = zero_state(inp)
    inp = run_1hz_loop(inp)
    inp = post_process(inp)
    
    # Check Safety and Trigger Alarms!
    if inp["flag_overheat"] or inp["flag_dry_boil"]:
        led.value(1) # Turn on RED warning light
        beep(3000, 800) # Long high pitch alarm
    else:
        beep(1500, 200) # Happy success beep
    
    # Output Results
    show_results(inp)

# =============================================================================
# MAIN EXECUTION
# =============================================================================
if __name__ == "__main__":
    btn_pressed = False 
    led.value(0)
    while True:
        main_ui_flow()