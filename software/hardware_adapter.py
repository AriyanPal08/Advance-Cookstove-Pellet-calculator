"""Hardware-matched desktop calculation adapter.

This module deliberately imports the files in ../hardware.  It does not copy
or modify them: their database values, factors and physics functions remain
the only source used by the website and desktop terminal.
"""

import sys
import types
from pathlib import Path


HARDWARE_DIR = Path(__file__).resolve().parent.parent / "hardware"


def _load_reference_module(module_name, filename):
    """Load a desktop Python module from the hardware source without editing it."""
    source_path = HARDWARE_DIR / filename
    source = source_path.read_text(encoding="utf-8")
    if filename == "utensil_db.py":
        # Line 219 is a broken category-list string, not a formula or data
        # value. The exact value is established by the corresponding
        # UTENSIL_DB key on line 154, so this only makes that source parsable.
        broken = '        "Kadhai 6L,\n'
        fixed = '        "Kadhai 6L",\n'
        if broken not in source:
            raise RuntimeError("The expected hardware reference line was not found.")
        source = source.replace(broken, fixed, 1)
    module = types.ModuleType(module_name)
    module.__file__ = str(source_path)
    sys.modules[module_name] = module
    exec(compile(source, str(source_path), "exec"), module.__dict__)
    return module


food_db = _load_reference_module("food_db", "food_db.py")
pellet_db = _load_reference_module("pellet_db", "pellet_db.py")
utensil_db = _load_reference_module("utensil_db", "utensil_db.py")
main_logic = _load_reference_module("main_logic", "main_logic.py")

FOOD_DB = food_db.FOOD_DB
get_dish_names = food_db.get_dish_names
PELLET_DB = pellet_db.PELLET_DB
get_pellet_names = pellet_db.get_pellet_names
get_utensil_names = utensil_db.get_utensil_names
get_utensil = utensil_db.get_utensil
WIND_TIERS = main_logic.WIND_TIERS
LID_FACTOR_ON = main_logic.LID_FACTOR_ON
LID_FACTOR_OFF = main_logic.LID_FACTOR_OFF
FAN_HIGH = main_logic.FAN_HIGH
CP_WATER = main_logic.CP_WATER
PRESSURE_POST_BOIL_FACTOR = main_logic.PRESSURE_POST_BOIL_FACTOR
compute_vessel_geometry = main_logic.compute_vessel_geometry
_emissivity_for_utensil = main_logic._emissivity_for_utensil
estimate_cook_time = main_logic.estimate_cook_time
compute_safety_buffer_s = main_logic.compute_safety_buffer_s
zero_state = main_logic.zero_state
run_1hz_loop = main_logic.run_1hz_loop
post_process = main_logic.post_process


def build_inputs(data):
    """Mirror hardware/main.py's collect_inputs() and run_simulation() setup."""
    inp = {}
    inp["dish_name"] = data["dish_name"]
    inp["dish"] = FOOD_DB[inp["dish_name"]]
    dish = inp["dish"]

    if dish.variable_water:
        inp["water_liters"] = float(data["qty"])
        inp["portions"] = 1
        inp["m_food"] = dish.food_mass_per_serving_kg
        inp["cp_food"] = dish.cp_food_kj_kgk
        inp["m_water_initial"] = inp["water_liters"]
        inp["t_kinetic_base_s"] = 0.0
    else:
        portions = float(data["qty"]) if dish.qty_is_float else int(data["qty"])
        inp["portions"] = portions
        inp["m_food"] = dish.food_mass_per_serving_kg * portions
        inp["cp_food"] = dish.cp_food_kj_kgk
        inp["m_water_initial"] = dish.added_water_per_serving_kg * portions
        inp["t_kinetic_base_s"] = 0.0

    inp["t_ambient_c"] = float(data["t_ambient_c"])
    inp["wind_label"] = data["wind_label"]
    inp["k_conv_current"] = WIND_TIERS[inp["wind_label"]]
    inp["pellet_name"] = data["pellet_name"]
    inp["pellet"] = PELLET_DB[inp["pellet_name"]]
    inp["gcv_kj_kg"] = inp["pellet"].conservative_gcv_kj
    inp["utensil_name"] = data["utensil_name"]
    utensil = get_utensil(inp["utensil_name"])
    inp["utensil"] = utensil
    inp["cp_pot"] = utensil.cp_kj_kgk
    inp["is_pc"] = utensil.is_pressure
    inp["emissivity"] = _emissivity_for_utensil(utensil)
    inp["m_pot"] = float(data.get("m_pot", utensil.mass_kg))

    if not dish.variable_water:
        for stage in dish.stages:
            if stage.stage_type == "kinetic":
                inp["t_kinetic_base_s"] += stage.duration_s * (
                    PRESSURE_POST_BOIL_FACTOR if inp["is_pc"] else 1.0
                )
            elif stage.stage_type == "frying":
                inp["t_kinetic_base_s"] += stage.duration_s

    if inp["is_pc"]:
        inp["lid_label"] = "Sealed (PC)"
        inp["lid_factor"] = 0.0
    elif data.get("lid_state") == "ON":
        inp["lid_label"] = "Lid ON"
        inp["lid_factor"] = LID_FACTOR_ON
    else:
        inp["lid_label"] = "Lid OFF"
        inp["lid_factor"] = LID_FACTOR_OFF

    inp.update(compute_vessel_geometry(
        inp["m_water_initial"], inp["utensil_name"], inp["lid_factor"]
    ))
    inp["P_in_kw"] = (FAN_HIGH / 3600.0) * inp["gcv_kj_kg"] * inp["eta_geom"]
    preview = estimate_cook_time(
        m_food=inp["m_food"], cp_food=inp["cp_food"],
        m_water=inp["m_water_initial"], m_pot=inp["m_pot"],
        cp_pot=inp["cp_pot"], t_kinetic_s=inp["t_kinetic_base_s"],
        P_in_kw=inp["P_in_kw"], A_m2=inp["A_m2"],
        k_conv=inp["k_conv_current"], emissivity=inp["emissivity"],
        T_amb=inp["t_ambient_c"], lid_fac=inp["lid_factor"],
    )
    t_heat_s = preview["t_heat_s"]
    if preview["heat_cannot_rise"] > 0.5 or t_heat_s <= 0.0:
        t_heat_s = 0.0
    inp["t_heat_est_s"] = t_heat_s
    inp["t_boil_est_s"] = preview["t_boil_s"]
    inp["t_safety_buffer_s"] = compute_safety_buffer_s(
        t_heat_s, inp["k_conv_current"], inp["m_water_initial"]
    )
    inp["t_preview_s"] = preview["t_preview_s"]
    inp["t_suggested_total_min"] = (
        t_heat_s + inp["t_kinetic_base_s"] + inp["t_safety_buffer_s"]
    ) / 60.0
    return inp


def simulate(data):
    """Run the same absolute-time calculation used by hardware/main.py."""
    inp = build_inputs(data)
    inp["t_total_min_user"] = inp["t_suggested_total_min"]
    inp["t_total_s"] = inp["t_total_min_user"] * 60.0
    return post_process(run_1hz_loop(zero_state(inp)))
