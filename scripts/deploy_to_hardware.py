import shutil
import re

# 1. Copy the DB files exactly
shutil.copyfile('food_db.py', 'hardware/food_db.py')
shutil.copyfile('pellet_db.py', 'hardware/pellet_db.py')
shutil.copyfile('utensil_db.py', 'hardware/utensil_db.py')

# 2. Extract physics from main_logic.py and write to hardware/main_logic.py
with open('main_logic.py', 'r', encoding='utf-8') as f:
    main_content = f.read()

# Find the start of the Terminal UI
match = re.search(r'# =+[\r\n]+_ANSI =', main_content)
if match:
    physics_content = main_content[:match.start()]
    
    # Add a custom header for the hardware port
    header = """# =============================================================================
# hardware/main_logic.py — MicroPython Port (ESP32)
# 1Hz Discrete Transient Biomass Cookstove Simulator
# IIT Delhi - Department of Energy Studies
#
# ALL PHYSICS FUNCTIONS AND CONSTANTS PRESERVED BYTE-FOR-BYTE.
# Terminal UI (ANSI codes, prompts, menus, print_receipt) REMOVED.
# Only pure computation functions remain for hardware/main.py to call.
# =============================================================================\n"""
    
    # Strip the original header from physics_content if needed, or just prepend
    # Actually, main_logic.py has its own header. Let's just overwrite the file entirely with physics_content since it's cleaner.
    with open('hardware/main_logic.py', 'w', encoding='utf-8') as f:
        f.write(physics_content)

# 3. Patch hardware/main.py
with open('hardware/main.py', 'r', encoding='utf-8') as f:
    h_main = f.read()

h_main = h_main.replace(
    'P_in_kw=P_in_kw, A_m2=inp["A_m2"], k_conv=inp["k_conv_current"],',
    'P_in_kw=P_in_kw, A_m2=inp["A_m2"], A_top=inp["A_top"], k_conv=inp["k_conv_current"],'
)
with open('hardware/main.py', 'w', encoding='utf-8') as f:
    f.write(h_main)

# 4. Patch software/hardware_adapter.py
with open('software/hardware_adapter.py', 'r', encoding='utf-8') as f:
    h_adapter = f.read()

h_adapter = h_adapter.replace(
    'P_in_kw=inp["P_in_kw"], A_m2=inp["A_m2"],\n        k_conv=inp["k_conv_current"]',
    'P_in_kw=inp["P_in_kw"], A_m2=inp["A_m2"], A_top=inp["A_top"],\n        k_conv=inp["k_conv_current"]'
)
with open('software/hardware_adapter.py', 'w', encoding='utf-8') as f:
    f.write(h_adapter)

print("Deployment complete.")
