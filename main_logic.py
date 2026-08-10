import math
"""
=============================================================================
SOURCES
=============================================================================
SOURCES
=============================================================================
[1] MacCarty et al. (2010). Energy Sustain. Dev., 14(3), 161-171.
[2] NIST WebBook — Aluminium thermophysical properties.
[3] Incropera et al. (2007). Fundamentals of Heat and Mass Transfer, 7th ed.
    [Table 7.x: representative convection coefficients used for the wind
    factor tiers — still air ≈10 W/m²K; low/medium/high forced convection
    ranges ≈20-50 W/m²K for cylinders in cross-flow.]
[4] WBT v4.2.3 (2014). Clean Cooking Alliance. [Lid factor reference]
[5] Choi & Okos (1986); ICMR-NIN (2017). [food_db.py Cp_food sourcing]
"""

import math
import sys
import datetime
from pathlib import Path

from food_db    import FOOD_DB, DishProfile, get_dish_names
from pellet_db  import PELLET_DB, PelletType, get_pellet_names
from utensil_db import UTENSIL_DB, Utensil, get_utensil_names, get_utensil, GeometryType

# There is no closed-loop or variable-rate pellet control in this stove.

SIGMA = 5.67e-8

CP_WATER = 4.184
L_V = 2257.0
BOILING_POINT_WATER = 100.0

WIND_TIERS: dict[str, float] = {
    "Indoors / Still Air":        10.0,
    "Outdoors (Low Wind)":        20.0,
    "Outdoors (Medium Wind)":     35.0,
    "Outdoors (High Wind)":       50.0,
}

EMISSIVITY_ALUMINUM_OXIDIZED = 0.35
EMISSIVITY_CAST_IRON = 0.65
EMISSIVITY_STAINLESS_STEEL = 0.25

STOVE_THERMAL_EFFICIENCY = 0.47

PRESSURE_POST_BOIL_FACTOR = 0.20

LID_ESCAPE_COEFFICIENT_ON = 0.15

LID_FACTOR_ON = LID_ESCAPE_COEFFICIENT_ON
LID_FACTOR_OFF = 1.0

FAN_HIGH = 0.78

EXPERIMENTAL_DATASETS = [
    {
        "test_name": "WBT 5L Pot - Lid Off",
        "dish_name": "Water",
        "utensil_name": "Aluminium Pot 8L",
        "mass_kg": 5.0,
        "wind_tier": "Indoors / Still Air",
        "ambient_temp_c": 25.0,
        "lid_factor_name": "Lid Off",
        "experimental_time_s": 1080.0,
        "experimental_pellets_g": 234.0, 
        "confidence": "High",
        "notes": "Standard 5L Water Boiling Test, ambient 25C."
    },
    {
        "test_name": "Rice 2L PC (4 pax) - Lid On",
        "dish_name": "White Rice (Boiled)",
        "utensil_name": "Pressure Cooker 2L",
        "mass_kg": 1.0,
        "wind_tier": "Indoors / Still Air",
        "ambient_temp_c": 25.0,
        "lid_factor_name": "Lid On",
        "experimental_time_s": 810.0,
        "experimental_pellets_g": None,
        "confidence": "Medium",
        "notes": "Experimental threshold < 14 min to prevent burning."
    },
]

dt = 1.0      # s      — simulation time step (1 Hz)
T_OVERHEAT_C = 150.0
M_WATER_DRY = 0.0

# Loop safety cap (prevents infinite loop on pathological inputs)
MAX_SIMULATION_TIME = 6 * 3600.0

PELLET_PROCUREMENT_MARGIN = 0.08

def _emissivity_for_utensil(utensil: Utensil) -> float:
    return utensil.emissivity

def compute_vessel_geometry(
    m_water_kg,
    utensil_name,
    lid_factor,
    m_food_kg = 0.0,
) :
    utensil = get_utensil(utensil_name)
    r_inner = utensil.get_inner_radius()
    h_total = utensil.get_total_height()

    V_m3 = m_water_kg / 1000.0

    if utensil.geometry_type in (GeometryType.CYLINDER, GeometryType.PRESSURE_COOKER):
        h_fill = V_m3 / (math.pi * (r_inner ** 2))
        A_bottom = math.pi * (r_inner ** 2)
        A_side_wetted = 2 * math.pi * r_inner * h_fill
        A_side_dry = 2 * math.pi * r_inner * max(0.0, h_total - h_fill)
        A_top = A_bottom
    elif utensil.geometry_type == GeometryType.KADHAI:
        R = r_inner
        h_fill = R / 2.0
        for _ in range(15):
            f = (math.pi / 3.0) * (h_fill**2) * (3*R - h_fill) - V_m3
            f_prime = math.pi * h_fill * (2*R - h_fill)
            if abs(f_prime) < 1e-9: break
            h_new = h_fill - f/f_prime
            if abs(h_new - h_fill) < 1e-6: break
            h_fill = h_new
        h_fill = max(0.0, min(h_total, h_fill))
        A_bottom = 0.0
        A_side_wetted = 2 * math.pi * R * h_fill
        A_side_dry = 2 * math.pi * R * max(0.0, h_total - h_fill)
        A_top = math.pi * r_inner ** 2
    else:
        h_fill = 0.0
        A_bottom = math.pi * (r_inner ** 2)
        A_side_wetted = 0.0
        A_side_dry = 0.0
        A_top = A_bottom

    A_bottom_loss = 0.0 

    A_top_loss = A_top

    A_m2 = A_side_wetted + A_side_dry + A_top_loss + A_bottom_loss

    return {"V_m3": V_m3, "d_m": r_inner * 2, "h_m": h_fill, "A_m2": A_m2, "A_top": A_top, "eta_geom": STOVE_THERMAL_EFFICIENCY}

def evaporation_loss_w(T_pot_c, T_amb_c, A_evap_m2, k_conv) -> float:
    if A_evap_m2 <= 0.0 or T_pot_c <= T_amb_c:
        return 0.0

    h_m = k_conv / 1200.0

    import math
    P_sat_pot = 610.78 * math.exp(17.27 * T_pot_c / (T_pot_c + 237.3))
    P_sat_amb = 610.78 * math.exp(17.27 * T_amb_c / (T_amb_c + 237.3)) * 0.50

    rho_v_pot = P_sat_pot * 0.018 / (8.314 * (T_pot_c + 273.15))
    rho_v_amb = P_sat_amb * 0.018 / (8.314 * (T_amb_c + 273.15))

    m_evap_rate_kg_s = h_m * A_evap_m2 * max(0.0, rho_v_pot - rho_v_amb)
    return m_evap_rate_kg_s * (L_V * 1000.0)

def heat_loss_w(
    T_pot_c,
    T_amb_c,
    A_m2,
    k_conv,
    emissivity,
    lid_factor = 1.0,
) -> float:
    T_pot_K = T_pot_c + 273.15
    T_amb_K = T_amb_c + 273.15
    P_conv = k_conv * A_m2 * (T_pot_K - T_amb_K)
    P_rad  = emissivity * SIGMA * A_m2 * (T_pot_K ** 4 - T_amb_K ** 4)
    return P_conv + P_rad

def heat_loss_kw(
    T_pot_c,
    T_amb_c,
    A_m2,
    k_conv,
    emissivity,
    lid_factor = 1.0,
) -> float:
    return heat_loss_w(T_pot_c, T_amb_c, A_m2, k_conv, emissivity, lid_factor) / 1000.0

def compute_safety_buffer_s(
    t_heat_s,
    k_conv,
    m_water_kg,
) -> float:
    buffer = 60.0
    buffer += min(30.0, 0.04 * t_heat_s)
    buffer += min(20.0, 5.0 * max(0.0, k_conv / 10.0 - 1.0))
    buffer += min(10.0, max(0.0, (m_water_kg - 8.0) * 1.5))
    return min(120.0, max(60.0, buffer))

def _transient_preview_tick(
    T_pot,
    m_water,
    m_food,
    cp_food,
    m_pot,
    cp_pot,
    P_in_kw,
    A_m2,
    A_top,
    k_conv,
    emissivity,
    T_amb,
    lid_fac,
) :
    """Execute one 1 Hz physics tick (Steps 2A–2D)."""
    Q_in  = P_in_kw * dt
    MCp_total = (m_food * cp_food) + (m_water * CP_WATER) + (m_pot * cp_pot)

    Q_out_dry = heat_loss_kw(T_pot, T_amb, A_m2, k_conv, emissivity, lid_fac) * dt

    m_evap_pre_boil = 0.0
    P_evap_pre_boil = 0.0
    if T_pot < 100.0 and m_water > 0.0:
        P_evap_pre_boil = evaporation_loss_w(T_pot, T_amb, A_top * lid_fac, k_conv) / 1000.0
        m_evap_pre_boil = (P_evap_pre_boil * dt) / L_V
        if m_evap_pre_boil > m_water:
            m_evap_pre_boil = m_water
            P_evap_pre_boil = (m_evap_pre_boil * L_V) / dt
        m_water -= m_evap_pre_boil

    Q_out = Q_out_dry + P_evap_pre_boil * dt
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

        if Q_avail > 0 and m_water > 0:
            m_evap_boil = (Q_avail / L_V) if lid_fac > 0.0 else 0.0
            if m_evap_boil <= m_water:
                m_water -= m_evap_boil
                Q_avail -= (m_evap_boil * L_V)
            else:
                Q_boil = m_water * L_V
                m_water = 0.0
                Q_avail -= Q_boil

        if Q_avail > 0 and m_water <= 0:
            MCp_dry = (m_food * cp_food) + (m_pot * cp_pot)
            if MCp_dry > 0:
                T_pot += Q_avail / MCp_dry
            Q_avail = 0.0

    return T_pot, m_water, Q_out

def estimate_cook_time(
    m_food,
    cp_food,
    m_water,
    m_pot,
    cp_pot,
    t_kinetic_s,
    P_in_kw,
    A_m2,
    A_top,
    k_conv,
    emissivity,
    T_amb,
    lid_fac,
) :
    T_pot = T_amb
    m_w   = m_water
    t_elapsed = 0.0
    t_boil = None
    Q_out_accum = 0.0
    heat_cannot_rise = False

    while T_pot < 100.0 and t_elapsed < MAX_SIMULATION_TIME:
        T_prev = T_pot
        T_pot, m_w, Q_out = _transient_preview_tick(
            T_pot, m_w, m_food, cp_food, m_pot, cp_pot,
            P_in_kw, A_m2, A_top, k_conv, emissivity, T_amb, lid_fac,
        )
        if T_pot <= T_prev and T_pot < 100.0:
            heat_cannot_rise = True
            break
        t_elapsed += dt
        Q_out_accum += Q_out
        if T_pot >= 100.0 and t_boil is None:
            t_boil = t_elapsed

    t_heat_s = t_elapsed

    if not heat_cannot_rise and t_kinetic_s > 0.0:
        kinetic_ticks = int(t_kinetic_s)
        for _ in range(kinetic_ticks):
            if t_elapsed >= MAX_SIMULATION_TIME:
                break
            T_pot, m_w, Q_out = _transient_preview_tick(
                T_pot, m_w, m_food, cp_food, m_pot, cp_pot,
                P_in_kw, A_m2, A_top, k_conv, emissivity, T_amb, lid_fac,
            )
            t_elapsed += dt
            Q_out_accum += Q_out

    return {
        "t_heat_s": t_heat_s,
        "t_boil_s": t_boil if t_boil is not None else 0.0,
        "t_preview_s": t_elapsed,
        "Q_out_accum_kj": Q_out_accum,
        "heat_cannot_rise": bool(heat_cannot_rise),
        "m_water_end_kg": m_w,
    }

_ANSI = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

def _c(text, *codes) -> str:
    return ("".join(codes) + text + "\033[0m") if _ANSI else text

RST = "\033[0m"; BLD = "\033[1m"; DIM = "\033[2m"
CYN = "\033[36m"; GRN = "\033[32m"; YLW = "\033[33m"
RED = "\033[31m"; BLU = "\033[34m"; ORG = "\033[38;5;214m"; WHT = "\033[97m"

def _hdr(title) -> None:
    print()
    print(_c("=" * 72, CYN, BLD))
    print(_c(f"  {title}", BLD, WHT))
    print(_c("=" * 72, CYN, BLD))

def _sec(title) -> None:
    print()
    print(_c(f"  ── {title} ──", BLD, YLW))
    print(_c("─" * 72, DIM))

def _warn(msg) -> None:
    print(_c(f"\n  [!]  {msg}", YLW))

def _prompt(msg, default=None) -> str:
    suffix = _c(f" [{default}]", DIM) if default is not None else ""
    try:
        raw = input(_c(f"\n  >>  {msg}", BLD, BLU) + suffix + _c(" : ", BLD, BLU)).strip()
    except EOFError:
        raw = ""
    return raw if (raw != "" or default is None) else default

def _prompt_float(msg, default, lo = 0.0, hi = 1e9) -> float:
    while True:
        try:
            raw = _prompt(msg, str(default))
            val = float(raw)
            if lo < val <= hi:
                return val
            _warn(f"Must be > {lo} and ≤ {hi}.")
        except ValueError:
            _warn("Enter a valid number.")
        except KeyboardInterrupt:
            _quit_or_continue()

def _prompt_int(msg, default, lo = 1) -> int:
    while True:
        try:
            raw = _prompt(msg, str(default))
            val = int(raw)
            if val >= lo:
                return val
            _warn(f"Must be ≥ {lo}.")
        except ValueError:
            _warn("Enter a whole number.")
        except KeyboardInterrupt:
            _quit_or_continue()

def _menu(title, options: list[str]) -> int:
    _sec(title)
    for i, opt in enumerate(options, 1):
        print(_c(f"    [{i}]  {opt}", WHT))
    while True:
        try:
            raw = _prompt("Select option number")
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                print(_c(f"  ✓  {options[idx]}", GRN))
                return idx
            _warn(f"Enter a number 1–{len(options)}.")
        except ValueError:
            _warn("Enter a valid number.")
        except KeyboardInterrupt:
            _quit_or_continue()

def _quit_or_continue() -> None:
    print(_c("\n  Ctrl+C detected. Type 'q' to quit or Enter to continue.", YLW))
    try:
        if input("  >> ").strip().lower() == "q":
            print(_c("\n  Goodbye.\n", DIM))
            sys.exit(0)
    except (KeyboardInterrupt, EOFError):
        sys.exit(0)

def collect_inputs() :
    _hdr("IIT DELHI  |  1Hz Transient Biomass Cookstove Simulator  |  v4")
    inp: dict = {}

    # ── Step 1: Dish selection ────────────────────────────────────────────────
    dish_names = get_dish_names()
    _sec("Step 1 / 7  —  Dish Selection")
    for i, name in enumerate(dish_names, 1):
        d = FOOD_DB[name]
        print(_c(f"    [{i:>2}]  {name:<42}  {d.category}", WHT))
    while True:
        try:
            raw = _prompt("Select dish number")
            idx = int(raw) - 1
            if 0 <= idx < len(dish_names):
                inp["dish_name"] = dish_names[idx]
                inp["dish"]      = FOOD_DB[inp["dish_name"]]
                break
            _warn(f"Enter 1–{len(dish_names)}.")
        except ValueError:
            _warn("Enter a valid number.")
        except KeyboardInterrupt:
            _quit_or_continue()

    dish: DishProfile = inp["dish"]

    # ── Step 2: Portions / water volume ───────────────────────────────────────
    if dish.variable_water:
        _sec("Step 2 / 7  —  Water Volume")
        inp["water_liters"] = _prompt_float(
            "Total water to boil (Litres)", default=5.0, lo=0.0, hi=200.0
        )
        inp["portions"] = 1
    else:
        _sec("Step 2 / 7  —  Number of People / Servings")
        inp["portions"] = _prompt_int("Number of people", default=2)

    n = inp["portions"]

    if dish.variable_water:
        inp["m_food"]          = dish.food_mass_per_serving_kg
        inp["cp_food"]         = dish.cp_food_kj_kgk
        inp["m_water_initial"] = inp["water_liters"]
        inp["t_kinetic_base_s"] = 0.0
    else:
        inp["m_food"]          = dish.food_mass_per_serving_kg    * n
        inp["cp_food"]         = dish.cp_food_kj_kgk
        inp["m_water_initial"] = dish.added_water_per_serving_kg  * n

        # We defer the actual kinetic time calculation until AFTER Step 5 
        inp["t_kinetic_base_s"] = 0.0

    # ── Step 3: Ambient temperature ───────────────────────────────────────────
    _sec("Step 3 / 7  —  Ambient Temperature")
    inp["t_ambient_c"] = _prompt_float(
        "Ambient temperature (°C)", default=25.0, lo=-10.0, hi=50.0
    )

    # ── Step 3b: Wind Factor  (NEW — replaces static K_CONV_STILL_AIR) ───────
    wind_labels = list(WIND_TIERS.keys())
    wind_idx = _menu("Wind Factor / Cooking Environment", wind_labels)
    inp["wind_label"]      = wind_labels[wind_idx]
    inp["k_conv_current"]  = WIND_TIERS[inp["wind_label"]]
    print(_c(
        f"  k_conv_current = {inp['k_conv_current']:.1f} W/m²·K", DIM
    ))

    # ── Step 4: Pellet selection ──────────────────────────────────────────────
    pellet_names = get_pellet_names()
    _sec("Step 4 / 7  —  Pellet Type")
    for i, name in enumerate(pellet_names, 1):
        p = PELLET_DB[name]
        print(_c(
            f"    [{i:>2}]  {name:<44}"
            f"  {p.gcv_min_kcal:,}–{p.gcv_max_kcal:,} kcal/kg  [{p.category}]",
            WHT
        ))
    while True:
        try:
            raw = _prompt("Select pellet type")
            idx = int(raw) - 1
            if 0 <= idx < len(pellet_names):
                inp["pellet_name"] = pellet_names[idx]
                inp["pellet"]      = PELLET_DB[inp["pellet_name"]]
                break
            _warn(f"Enter 1–{len(pellet_names)}.")
        except ValueError:
            _warn("Enter a valid number.")
        except KeyboardInterrupt:
            _quit_or_continue()

    pellet: PelletType = inp["pellet"]
    inp["gcv_kj_kg"] = pellet.conservative_gcv_kj

    # ── Step 5: Utensil selection  (silent Cp lookup + mass OVERRIDE) ────────
    utensil_names = get_utensil_names()
    while True:
        u_idx = _menu("Step 5 / 7  —  Utensil Selection", utensil_names)
        utensil: Utensil = get_utensil(utensil_names[u_idx])
        geom_str = utensil.geometry_type.name

        if geom_str in dish.forbidden_utensils:
            print(f"\n\033[91m[WARNING] {dish.name} cannot be cooked in a {geom_str} ({utensil.name}). Please select a different utensil.\033[0m")
            continue

        total_vol_l = inp["m_water_initial"] + inp.get("m_food", 0.0)
        effective_max_ratio = min(utensil.maximum_fill_ratio, getattr(dish, 'max_fill_ratio', 0.85))
        max_allowed_vol_l = utensil.capacity_l * effective_max_ratio

        if total_vol_l > max_allowed_vol_l:
            print(f"\n\033[91m[WARNING] The {utensil.name} is too small for this batch size!\033[0m")
            print(f"\033[91mTotal recipe volume (~{total_vol_l:.1f}L) exceeds the maximum safe fill limit ({max_allowed_vol_l:.1f}L).\033[0m")
            print(f"\033[91mPlease select a larger utensil.\033[0m")
            continue

        break

    inp["utensil_name"] = utensil.name
    inp["cp_pot"]        = utensil.cp_kj_kgk
    inp["is_pc"]         = utensil.is_pressure

    inp["m_pot"] = _prompt_float(
        f"Press Enter to accept [{utensil.empty_mass_kg}] kg, "
        f"or type a precise vessel mass (kg)",
        default=utensil.empty_mass_kg, lo=0.0, hi=50.0
    )

    if inp["is_pc"]:
        inp["lid_label"]  = "ON (Pressure Cooker — sealed)"
        inp["lid_factor"] = 0.0
    else:
        lid_idx = _menu("Lid State", ["Lid ON (covered)", "Lid OFF (open)"])
        if lid_idx == 0:
            inp["lid_label"]  = "Lid ON"
            inp["lid_factor"] = LID_ESCAPE_COEFFICIENT_ON
        else:
            inp["lid_label"]  = "Lid OFF"
            inp["lid_factor"] = 1.0

    m_w = inp["m_water_initial"]
    inp["emissivity"] = _emissivity_for_utensil(utensil)
    geom = compute_vessel_geometry(m_w, inp["utensil_name"], inp["lid_factor"])
    inp.update(geom)

    if not dish.variable_water:
        kinetic_time_s = 0.0
        for stage in dish.stages:
            if stage.stage_type == "kinetic":
                kinetic_time_s += stage.duration_s * (
                    PRESSURE_POST_BOIL_FACTOR if inp.get("is_pc", False) else 1.0
                )
            elif stage.stage_type == "frying":
                kinetic_time_s += stage.duration_s
        inp["t_kinetic_base_s"] = kinetic_time_s

    # ── Step 7: Total Time Estimator  (full transient preview) ───────────────
    _sec("Step 7 / 7  —  Total Cooking Time (Heating + Simmering)")

    eta_geom = inp["eta_geom"]
    P_in_kw = (FAN_HIGH / 3600.0) * inp["gcv_kj_kg"] * eta_geom
    MCp_total = (inp["m_food"] * inp["cp_food"]
                 + m_w * CP_WATER
                 + inp["m_pot"] * inp["cp_pot"])

    T_amb = inp["t_ambient_c"]
    k_conv = inp["k_conv_current"]

    preview = estimate_cook_time(
        m_food=inp["m_food"],
        cp_food=inp["cp_food"],
        m_water=m_w,
        m_pot=inp["m_pot"],
        cp_pot=inp["cp_pot"],
        t_kinetic_s=inp["t_kinetic_base_s"],
        P_in_kw=P_in_kw,
        A_m2=inp["A_m2"],
        k_conv=k_conv,
        emissivity=inp["emissivity"],
        T_amb=T_amb,
        lid_fac=inp["lid_factor"],
    )

    t_heat_s = preview["t_heat_s"]
    if preview["heat_cannot_rise"] > 0.5 or t_heat_s <= 0.0:
        t_heat_s = 0.0
        _warn(
            "Stove input power does not exceed heat loss during heat-up; "
            "heat-up time estimate defaulted to 0 s. Total time will rely on "
            "kinetic time only — review pellet/utensil selection."
        )

    Q_out_avg_kw = (
        preview["Q_out_accum_kj"] / preview["t_preview_s"]
        if preview["t_preview_s"] > 0.0 else 0.0
    )

    t_safety_buffer_s = compute_safety_buffer_s(t_heat_s, k_conv, m_w)
    t_core_s = t_heat_s + inp["t_kinetic_base_s"]
    t_suggested_total_s   = t_core_s + t_safety_buffer_s
    t_suggested_total_min = t_suggested_total_s / 60.0

    print(_c(f"\n  Estimated heat-up time     : {t_heat_s/60:.1f} min", DIM))
    print(_c(f"  Predicted boil time        : {preview['t_boil_s']/60:.1f} min", DIM))
    print(_c(f"  Dish kinetic time (base×n) : {inp['t_kinetic_base_s']/60:.1f} min", DIM))
    print(_c(f"  Safety buffer              : {t_safety_buffer_s:.0f} s", DIM))
    print(_c(
        f"  Suggested Total Time       : {t_suggested_total_min:.1f} min",
        GRN, BLD
    ))

    t_total_min = _prompt_float(
        "Total cooking time (heating + simmering) in minutes",
        default=round(t_suggested_total_min, 1),
        lo=0.0, hi=600.0
    )
    inp["t_total_s"] = t_total_min * 60.0
    inp["t_total_min_user"] = t_total_min

    inp["P_in_kw"]              = P_in_kw
    inp["MCp_total_init"]       = MCp_total
    inp["Q_out_avg_kw"]         = Q_out_avg_kw
    inp["t_heat_est_s"]         = t_heat_s
    inp["t_boil_est_s"]         = preview["t_boil_s"]
    inp["t_safety_buffer_s"]    = t_safety_buffer_s
    inp["t_preview_s"]          = preview["t_preview_s"]

    return inp

def zero_state(inp: dict) :
    inp.update({
        "t_elapsed_s":      0.0,
        "T_pot_c":          inp["t_ambient_c"],
        "m_water_current":  inp["m_water_initial"],
        "flag_dry_boil":    False,
        "flag_overheat":    False,
        "t_boil_reached_s": None,
        "tick_log":         [],
    })
    return inp

# PHASE 2 — 1Hz TRANSIENT LOOP (The Core Engine)

def run_1hz_loop(inp: dict) :
    m_food:   float = inp["m_food"]
    cp_food:  float = inp["cp_food"]
    m_pot:    float = inp["m_pot"]
    cp_pot:   float = inp["cp_pot"]
    A:        float = inp["A_m2"]
    eta_geom = inp["eta_geom"]
    gcv:      float = inp["gcv_kj_kg"]
    lid_fac:  float = inp["lid_factor"]
    T_amb:    float = inp["t_ambient_c"]
    t_total_s = inp["t_total_s"]
    k_conv:   float = inp["k_conv_current"]
    emissivity = inp.get("emissivity", 0.35)

    # Step 2A: Power In — constant for the entire run (high-fan rule)
    P_in_kw = (FAN_HIGH / 3600.0) * gcv * eta_geom

    T_pot:           float       = inp["T_pot_c"]
    m_water:         float       = inp["m_water_current"]
    t_elapsed:       float       = inp["t_elapsed_s"]
    flag_dry:        bool        = False
    flag_over:       bool        = False
    t_boil_reached = None

    Q_in_kj = 0.0
    Q_out_kj = 0.0
    Q_sensible_kj = 0.0
    Q_evap_kj = 0.0

    log_interval = 60
    tick_log: list = []
    tick = 0

    # ── LOOP CONDITION (UPDATED)ictly absolute-time based ────────────────
    while t_elapsed < t_total_s:

        T_before = T_pot
        m_w_before = m_water

        # Step 2A: Power In
        Q_in = P_in_kw * dt

        # Step 2B: Dynamic Mass (UNCHANGED)
        MCp_total = (m_food * cp_food) + (m_water * CP_WATER) + (m_pot * cp_pot)

        # Step 2C: Heat Bleed (shared helper — matches Total Time Estimator)
        Q_out = heat_loss_kw(T_pot, T_amb, A, k_conv, emissivity, lid_fac) * dt

        # Step 2D: Net Energy & State Routing (UNCHANGED — PROTECTED)
        Q_avail = Q_in - Q_out

        if Q_avail <= 0.0:
            # Route A: Cooling
            if MCp_total > 0:
                T_pot += Q_avail / MCp_total
        else:
            # Route B: Heating & Boiling Sequence
            if T_pot < 100.0:
                Q_to_100 = MCp_total * (100.0 - T_pot)
                if Q_avail <= Q_to_100:
                    T_pot   += Q_avail / MCp_total
                    Q_avail  = 0.0
                else:
                    T_pot    = 100.0
                    Q_avail -= Q_to_100
                    if t_boil_reached is None:
                        t_boil_reached = t_elapsed + dt

            # Route B2: Evaporation
            if Q_avail > 0 and m_water > 0:
                m_evap_potential = (Q_avail / L_V) * lid_fac
                if m_evap_potential <= m_water:
                    m_water -= m_evap_potential
                    Q_avail  = 0.0
                else:
                    Q_boil  = (m_water / lid_fac) * L_V
                    m_water = 0.0
                    Q_avail -= Q_boil

            # Route B3: Dry-Boil Runaway
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
                MCp_track = (m_food * cp_food) + (m_w_before * CP_WATER) + (m_pot * cp_pot)
            else:
                MCp_track = (m_food * cp_food) + (m_pot * cp_pot)
            Q_sensible_kj += MCp_track * dT
        dm_evap = m_w_before - m_water
        if dm_evap > 0.0 and lid_fac > 0.0:
            Q_evap_kj += (dm_evap / lid_fac) * L_V

        t_elapsed += dt

        # Safety break (NEW — prevents infinite loop on pathological input)
        if t_elapsed > MAX_SIMULATION_TIME:
            _warn(
                f"MAX_SIMULATION_TIME ({MAX_SIMULATION_TIME/3600:.1f} h) exceeded — "
                f"loop terminated early for safety."
            )
            break

        if m_water <= M_WATER_DRY and not flag_dry:
            flag_dry = True
        if T_pot > T_OVERHEAT_C and not flag_over:
            flag_over = True

        tick += 1
        if tick % log_interval == 0 or t_elapsed >= t_total_s:
            tick_log.append({
                "t_s": t_elapsed, "T_c": T_pot,
                "m_w_kg": m_water, "t_remaining_s": max(0.0, t_total_s - t_elapsed),
            })

    inp.update({
        "t_elapsed_s":      t_elapsed,
        "T_pot_c":          T_pot,
        "m_water_current":  m_water,
        "flag_dry_boil":    flag_dry,
        "flag_overheat":    flag_over,
        "t_boil_reached_s": t_boil_reached,
        "tick_log":         tick_log,
        "P_in_kw":          P_in_kw,
        "Q_in_kj":          Q_in_kj,
        "Q_out_kj":         Q_out_kj,
        "Q_sensible_kj":    Q_sensible_kj,
        "Q_evap_kj":        Q_evap_kj,
    })
    return inp

def post_process(inp: dict) :
    t_elapsed = inp["t_elapsed_s"]
    gcv       = inp["gcv_kj_kg"]
    eta_geom  = inp["eta_geom"]
    k_conv_current = inp.get("k_conv_current", 10.0)
    lid_factor     = inp.get("lid_factor", 1.0)
    utensil        = inp.get("utensil")

    Q_demand_kj = inp["Q_sensible_kj"] + inp["Q_evap_kj"] + inp["Q_out_kj"]

    effective_energy_kj_per_kg = gcv * eta_geom
    if effective_energy_kj_per_kg > 0:
        pellets_energy_based_g = (Q_demand_kj / effective_energy_kj_per_kg) * 1000.0
    else:
        pellets_energy_based_g = 0.0

    # loop control. The correct hopper load is:
    pellets_time_g = (t_elapsed / 3600.0) * FAN_HIGH * 1000.0

    if k_conv_current >= 50.0:
        procurement_margin = 0.12
        margin_reason = "High Wind (k_conv >= 50.0 W/m²·K)"
    elif lid_factor == 1.0:
        procurement_margin = 0.10
        margin_reason = "Open Pot (lid_factor = 1.00)"
    elif lid_factor < 1.0 and utensil and not utensil.is_pressure:
        procurement_margin = 0.07
        margin_reason = "Covered Pot (lid_factor < 1.00, non-pressure)"
    elif utensil and utensil.is_pressure:
        procurement_margin = 0.05
        margin_reason = "Pressure Cooker (sealed, minimal environmental loss)"
    else:
        procurement_margin = 0.08
        margin_reason = "Default (environmental variance not classified)"

    pellets_with_margin_g = pellets_time_g * (1.0 + procurement_margin)

    inp["Q_demand_kj"]               = Q_demand_kj
    inp["pellets_required_g"]        = pellets_with_margin_g
    inp["pellets_required_kg"]       = pellets_with_margin_g / 1000.0
    inp["pellets_time_based_g"]      = pellets_time_g
    inp["pellets_energy_based_g"]    = pellets_energy_based_g
    inp["procurement_margin_factor"] = (1.0 + procurement_margin)
    inp["procurement_margin_pct"]    = procurement_margin * 100.0
    inp["margin_reason"]             = margin_reason

    t_boil_s = inp.get("t_boil_reached_s") or inp.get("t_heat_est_s", t_elapsed * 0.5)
    t_kinetic = inp.get("t_kinetic_base_s", 0.0)
    inp["t_phase1_s"] = t_boil_s
    inp["t_phase2_s"] = min(t_kinetic, max(0.0, t_elapsed - t_boil_s))
    inp["t_phase3_s"] = max(0.0, t_elapsed - t_boil_s - inp["t_phase2_s"])

    inp["research_outputs"] = {
        "Q_demand_kj":            Q_demand_kj,
        "Q_sensible_kj":          inp["Q_sensible_kj"],
        "Q_evap_kj":              inp["Q_evap_kj"],
        "Q_out_kj":               inp["Q_out_kj"],
        "Q_in_kj":                inp.get("Q_in_kj", 0.0),
        "P_in_kw":                inp.get("P_in_kw", 0.0),
        "eta_geom":               eta_geom,
        "t_elapsed_s":            t_elapsed,
        "t_elapsed_min":          t_elapsed / 60.0,
        "T_pot_final_c":          inp.get("T_pot_c", 0.0),
        "m_water_remaining_kg":   inp.get("m_water_current", 0.0),
        "flag_dry_boil":          inp.get("flag_dry_boil", False),
        "flag_overheat":          inp.get("flag_overheat", False),
        "pellets_energy_based_g": pellets_energy_based_g,
        "pellets_time_based_g":   pellets_time_g,
        "pellets_required_g":     pellets_with_margin_g,
        "procurement_margin_pct": procurement_margin * 100.0,
        "margin_reason":          margin_reason,
    }

    return inp

def _bar(fraction, width = 28) -> str:
    filled = int(min(max(fraction, 0.0), 1.0) * width)
    return "|" + "█" * filled + "░" * (width - filled) + "|"

def print_receipt(inp: dict) -> None:
    now_str   = datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    t_el      = inp["t_elapsed_s"]
    t_el_min  = t_el / 60.0
    pellet    = inp["pellet"]
    pellets_g = inp["pellets_required_g"]
    q_in_total = inp["P_in_kw"] * t_el

    def box(label, val, unit = "", col = CYN) -> None:
        u   = f" {unit}" if unit else ""
        v   = f"{val}{u}"
        pad = max(0, 62 - len(label) - len(v))
        print(_c(f"  | {label}", col) + _c(v, GRN, BLD) + _c(" " * pad + "|", col))

    def div(col = CYN) -> None:
        print(_c("  +" + "─" * 66 + "+", col))

    def title(t, col = CYN) -> None:
        print(_c(f"\n  +── {t} " + "─" * max(2, 60 - len(t)) + "+", col, BLD))

    print()
    print(_c("=" * 72, CYN, BLD))
    print(_c("  IIT DELHI  |  1Hz Transient Biomass Cookstove Simulator  |  v4", BLD, WHT))
    print(_c("=" * 72, CYN, BLD))
    print(_c(f"  Generated : {now_str}", DIM))
    print(_c("  Engine    : 1Hz Discrete Transient Solver  |  Unified Total-Time Loop", DIM))
    print()

    title("SIMULATION INPUTS  &  HIDDEN GEOMETRY")
    box("Dish",                 inp["dish_name"])
    if inp["dish"].variable_water:
        box("Water volume",     f"{inp['water_liters']:.2f}", "L")
    else:
        box("Portions",         str(inp["portions"]), "serving(s)")
    box("Ambient temperature",  f"{inp['t_ambient_c']:.1f}", "°C")
    box("Wind Factor",          inp["wind_label"])
    box("k_conv_current",       f"{inp['k_conv_current']:.1f}", "W/m²·K")
    box("Utensil",              inp["utensil_name"])
    box("Vessel mass (used)",   f"{inp['m_pot']:.3f}", "kg")
    box("Vessel Cp (DB)",       f"{inp['cp_pot']:.3f}", "kJ/kg·K")
    box("Surface emissivity ε", f"{inp.get('emissivity', 0.35):.2f}", "")
    box("Lid state",            inp["lid_label"])
    box("Pellet",                pellet.name)
    box("GCV (conservative)",   f"{pellet.conservative_gcv_kj:,.1f}", "kJ/kg")
    div()

    title("TOTAL TIME ESTIMATOR  (transient preview)")
    box("Estimated heat-up time",  f"{inp['t_heat_est_s']/60:.1f}", "min")
    box("Predicted boil time",     f"{inp.get('t_boil_est_s', 0)/60:.1f}", "min")
    box("Dish kinetic base time",  f"{inp['t_kinetic_base_s']/60:.1f}", "min")
    t_suggested_min = (
        inp['t_heat_est_s'] + inp['t_kinetic_base_s'] + inp.get('t_safety_buffer_s', 60)
    ) / 60.0
    box("Safety buffer",           f"{inp.get('t_safety_buffer_s', 60):.0f}", "s")
    box("Suggested total",         f"{t_suggested_min:.1f}", "min")
    box("User-selected total",     f"{inp['t_total_min_user']:.1f}", "min", col=GRN)
    if inp.get("t_boil_reached_s") is not None:
        est_err = abs(inp["t_boil_reached_s"] - inp.get("t_boil_est_s", 0))
        box("Boil-time estimator error", f"{est_err:.0f}", "s")
    box("Q_out_avg (preview)",       f"{inp['Q_out_avg_kw']*1000:.2f}", "W")
    div()
    title("DERIVED GEOMETRY  (cylinder model)")
    box("Initial food mass",     f"{inp['m_food']*1000:.1f}", "g")
    box("Initial water mass",    f"{inp['m_water_initial']*1000:.1f}", "g")
    box("Vessel surface area A", f"{inp['A_m2']*1e4:.2f}", "cm²")
    box("η_geom",                f"{inp['eta_geom']:.6f}")
    box("P_in (constant)",       f"{inp['P_in_kw']:.6f}", "kW")
    div()

    title("SIMULATION TELEMETRY  (1 Hz loop, sparse log @ 1-min intervals)")
    print(_c(f"  {'Time (min)':<12} {'T_pot (°C)':<14} {'Water (g)':<14} {'Time left (s)':<16}", DIM))
    print(_c("  " + "─" * 58, DIM))
    for rec in inp["tick_log"]:
        print(_c(
            f"  {rec['t_s']/60:>9.1f}    {rec['T_c']:>10.2f}    "
            f"{rec['m_w_kg']*1000:>10.1f}    {rec['t_remaining_s']:>12.1f}",
            WHT
        ))
    if inp["t_boil_reached_s"] is not None:
        print(_c(f"\n  ► Boiling point (100°C) first reached at "
                  f"t = {inp['t_boil_reached_s']/60:.1f} min", GRN))
    div()

    title("ENERGY SUMMARY")
    box("Total simulation time", f"{t_el:.0f}", "s")
    box("Total simulation time", f"{t_el_min:.2f}", "min")
    box("Stove power (P_in)",    f"{inp['P_in_kw']:.6f}", "kW")
    box("Energy supplied (Q_in)", f"{inp.get('Q_in_kj', q_in_total):.2f}", "kJ")
    box("Heat losses (Q_out)",   f"{inp.get('Q_out_kj', 0):.2f}", "kJ")
    box("Sensible heating",      f"{inp.get('Q_sensible_kj', 0):.2f}", "kJ")
    box("Evaporation (Q_evap)",  f"{inp.get('Q_evap_kj', 0):.2f}", "kJ")
    box("Thermodynamic demand",  f"{inp.get('Q_demand_kj', 0):.2f}", "kJ")
    box("Water remaining",       f"{inp['m_water_current']*1000:.1f}", "g")
    div()

    title("SAFETY DIAGNOSTICS",
          col=RED if (inp["flag_dry_boil"] or inp["flag_overheat"]) else GRN)
    if inp["flag_dry_boil"]:
        print(_c("  [FATAL]  DRY-BOIL DETECTED — m_water reached 0 during simulation.", RED, BLD))
        print(_c("           Food is burnt. Increase water or reduce cook time.", RED))
    else:
        print(_c("  ✓  No dry-boil event detected.", GRN))
    if inp["flag_overheat"]:
        print(_c("  [CRITICAL]  VESSEL OVERHEAT — T_pot exceeded 150°C.", RED, BLD))
    else:
        print(_c(f"  ✓  Final vessel temperature: {inp['T_pot_c']:.1f} °C (≤ 150°C safe limit).", GRN))
    div()

    title("ACADEMIC 3-PHASE COMBUSTION TIMELINE  (display only)", col=BLU)
    print(_c("  DISCLAIMER: Illustrative post-processing receipt.", DIM))
    print(_c("  Does NOT alter the governing fuel physics.", DIM, BLD))
    ph1_end = inp["t_phase1_s"]
    ph2_end = ph1_end + inp["t_phase2_s"]
    ph3_end = ph2_end + inp["t_phase3_s"]
    print(_c(f"\n  Phase 1 — IGNITION     (0 → {ph1_end/60:.1f} min, 15%)", BLU, BLD))
    print(_c("    Stove reaching operating temperature. Expect initial smoke.", DIM))
    print(_c(f"  Phase 2 — STEADY STATE ({ph1_end/60:.1f} → {ph2_end/60:.1f} min, 65%)", BLU, BLD))
    print(_c("    Optimal clean combustion and rapid boiling.", DIM))
    print(_c(f"  Phase 3 — CHAR / COALS ({ph2_end/60:.1f} → {ph3_end/60:.1f} min, 20%)", BLU, BLD))
    print(_c("    Fresh wood exhausted. Simmer finishing on highly efficient radiant char.", DIM))
    div(col=BLU)

    mass_str = f"{pellets_g:.1f} g"
    if pellets_g >= 1000:
        mass_str += f"  ({pellets_g/1000:.3f} kg)"
    print()
    print(_c("=" * 72, ORG, BLD))
    print(_c("  RECOMMENDED PELLET LOAD", BLD, WHT))
    print(_c(
        "  Formula:  (t_elapsed / 3600) × FAN_HIGH × 1000",
        DIM
    ))
    print(_c("  " + "─" * 60, ORG))
    print(_c(f"  ►  {mass_str:<20} ◄", ORG, BLD) + _c(f"  [{pellet.name}]", DIM))
    print(_c("  " + "─" * 60, ORG))
    print(_c(
        f"  ►  Time-based reference: {inp.get('pellets_time_based_g', 0):.1f} g  "
        f"(HIGH FAN {FAN_HIGH} kg/hr × {t_el/3600:.3f} h)",
        DIM
    ))
    print(_c("  ► Simulation used HIGH FAN (0.78 kg/hr) throughout — conservative.", DIM))
    print(_c("=" * 72, ORG, BLD))
    print()

def main() -> None:
    while True:
        try:
            inp = collect_inputs()
            inp = zero_state(inp)

            _hdr("RUNNING 1Hz TRANSIENT PHYSICS LOOP")
            print(_c(
                f"  Simulating at 1 Hz until t_elapsed reaches "
                f"{inp['t_total_s']/60:.1f} min...", DIM
            ))

            inp = run_1hz_loop(inp)

            print(_c(
                f"\n  ✓  Loop complete.  t_elapsed = {inp['t_elapsed_s']:.0f} s "
                f"({inp['t_elapsed_s']/60:.1f} min)", GRN
            ))

            inp = post_process(inp)
            print_receipt(inp)

            raw = _prompt(
                "Calculate another dish? Enter to restart / type 'q' to quit",
                default="Enter"
            ).strip().lower()
            if raw == "q":
                print(_c("\n  Goodbye.\n", DIM))
                break

        except KeyboardInterrupt:
            _quit_or_continue()
        except KeyError as exc:
            print(_c(f"\n  [X]  Database lookup error: {exc}\n", RED))
        except Exception as exc:
            print(_c(f"\n  [X]  Unexpected error: {exc}\n", RED))
            raise

if __name__ == "__main__":
    main()
