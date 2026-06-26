"""
main_logic.py -- IIT Delhi Biomass Pellet Cookstove Recommendation Engine (v9)

Architecture: 4-Step Thermodynamic Solver
=========================================
  Step 1  | Sensible Heat Target (Q_sensible)
  Step 2  | Time Anchor  (t_heating + t_kinetic -> t_total)
  Step 3  | Energy Bleed -- Convection Loss + Square-Cube Evaporation
  Step 4  | 3-Phase Combustion Integrator (absolute time windows)

STRICT BOUNDARIES
-----------------
  * food_db.py and pellet_db.py are READ-ONLY external dependencies.
  * Only the conservative (minimum) GCV is used for safety-margin calculations.
  * No user input is accepted that could create thermodynamic conflicts:
      - Time is DERIVED from physics first, then adjusted by the user.
      - Burn rate is fixed at 0.78 kg/hr for the time anchor only.

HIDDEN BACKEND CONSTANTS
------------------------
  STOVE_BURN_RATE_KG_HR   = 0.78   (kg/hr)  -- theoretical power anchor
  CP_WATER                = 4.184  (kJ/kg*K) -- NIST-exact latent-heat Cp
  L_WATER                 = 2257   (kJ/kg)   -- latent heat of vaporisation @ 100 C
  BASELINE_EFFICIENCY     = 0.45   (45 %)    -- steady-state combustion efficiency

Authors : IIT Delhi Biomass Energy Group
Version : 9.0.0
"""

from __future__ import annotations

import sys
import datetime

# -- Database imports (read-only) ----------------------------------------------
from food_db   import FOOD_DB, DishProfile, get_dish_names
from pellet_db import PELLET_DB, PelletType, get_pellet_names

# =============================================================================
# SECTION 1 -- HIDDEN BACKEND CONSTANTS
# =============================================================================

STOVE_BURN_RATE_KG_HR:   float = 0.78    # kg/hr
CP_WATER_KJ_KGK:         float = 4.184   # kJ/kg*K  NIST exact
L_WATER_KJ_KG:           float = 2257.0  # kJ/kg    latent heat @ 100 C
BASELINE_EFFICIENCY:     float = 0.45    # steady-phase combustion efficiency

T_BOIL_NORMAL_C:         float = 100.0
T_BOIL_PRESSURE_C:       float = 120.0

# Vessel-specific thermal properties (Base Convection Loss kW, Base Evap Rate g/min)
VESSEL_PROPERTIES: dict[str, dict] = {
    "Frying Pan":      {"loss_kw": 0.150, "evap_g_min": 15.0},
    "Kadhai":          {"loss_kw": 0.120, "evap_g_min": 12.0},
    "Standard Pot":    {"loss_kw": 0.075, "evap_g_min":  8.0},
    "Pressure Cooker": {"loss_kw": 0.050, "evap_g_min":  2.0},
}

REF_VOLUME_L: float = 1.0   # reference volume for Square-Cube law baseline

IGNITION_PHASE_DURATION_MIN: float = 10.0
DECLINE_PHASE_DURATION_MIN:  float = 5.0

EFF_IGNITION_NORMAL:   float = 0.25
EFF_IGNITION_HIGHWIND: float = 0.15
EFF_DECLINE:           float = 0.35
EFF_STEADY:            float = 0.45   # == BASELINE_EFFICIENCY

EVAP_FRAC_LID_OFF:         float = 1.00
EVAP_FRAC_LID_ON:          float = 0.10
EVAP_FRAC_PRESSURE_COOKER: float = 0.00

PC_KINETIC_FACTOR: float = 0.35   # 65% reduction for pressure cooker

# =============================================================================
# SECTION 2 -- VESSEL & ENVIRONMENT LOOKUP TABLES
# =============================================================================

VESSEL_TYPES: dict[str, str] = {
    "1": "Frying Pan",
    "2": "Standard Pot",
    "3": "Kadhai",
    "4": "Pressure Cooker",
}

VESSEL_MATERIALS: dict[str, tuple] = {
    "1": ("Aluminum",  0.89),
    "2": ("Steel",     0.50),
    "3": ("Cast Iron", 0.46),
    "4": ("Copper",    0.39),
}

WIND_OPTIONS: dict[str, tuple] = {
    "1": ("Inside (sheltered)",     1.00),
    "2": ("Outside -- Low wind",    1.15),
    "3": ("Outside -- Medium wind", 1.35),
    "4": ("Outside -- High wind",   1.55),
}

# =============================================================================
# SECTION 3 -- TERMINAL UI HELPERS
# =============================================================================

ANSI_RESET   = "\033[0m"
ANSI_BOLD    = "\033[1m"
ANSI_DIM     = "\033[2m"
ANSI_CYAN    = "\033[36m"
ANSI_GREEN   = "\033[32m"
ANSI_YELLOW  = "\033[33m"
ANSI_RED     = "\033[31m"
ANSI_BLUE    = "\033[34m"
ANSI_MAGENTA = "\033[35m"
ANSI_WHITE   = "\033[97m"

_USE_ANSI: bool = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def c(text: str, *codes: str) -> str:
    """Wrap text in ANSI codes if the terminal supports it."""
    if not _USE_ANSI:
        return text
    return "".join(codes) + text + ANSI_RESET


def header(title: str) -> None:
    print()
    print(c("=" * 72, ANSI_CYAN, ANSI_BOLD))
    print(c(f"  {title}", ANSI_BOLD, ANSI_WHITE))
    print(c("=" * 72, ANSI_CYAN, ANSI_BOLD))


def section(title: str) -> None:
    print()
    print(c(f"  -- {title} --", ANSI_BOLD, ANSI_YELLOW))
    print(c("-" * 72, ANSI_DIM))


def info(label: str, value: str, unit: str = "") -> None:
    u = c(f" {unit}", ANSI_DIM) if unit else ""
    print(c(f"  {label:<44}", ANSI_DIM) + c(str(value), ANSI_GREEN, ANSI_BOLD) + u)


def warn(msg: str) -> None:
    print(c(f"\n  [!]  {msg}", ANSI_YELLOW))


def prompt(msg: str, default: str | None = None) -> str:
    suffix = f" [default: {default}]" if default is not None else ""
    try:
        raw = input(c(f"\n  >>  {msg}{suffix} : ", ANSI_BOLD, ANSI_BLUE)).strip()
    except EOFError:
        raw = ""
    return raw if (raw != "" or default is None) else default


def numbered_menu(title: str, options: dict) -> str:
    section(title)
    for key, val in options.items():
        label = val[0] if isinstance(val, tuple) else val
        print(c(f"    [{key}]  {label}", ANSI_WHITE))
    while True:
        choice = prompt("Enter option number").upper()
        if choice in options:
            return choice
        warn(f"Invalid choice. Please enter one of: {', '.join(options)}")


# =============================================================================
# SECTION 4 -- INPUT COLLECTION (UI)
# =============================================================================


def collect_inputs() -> dict:
    """Walk the user through the full CLI input sequence."""
    header("IIT DELHI  |  Biomass Pellet Cookstove Recommendation Engine  |  v9")
    inp: dict = {}

    # 4.1 Dish selection -------------------------------------------------------
    section("Step 1 of 7 -- Dish Selection")
    dish_names = get_dish_names()
    dish_menu  = {str(i + 1): name for i, name in enumerate(dish_names)}
    for key, name in dish_menu.items():
        cat = FOOD_DB[name].category
        print(c(f"    [{key:>2}]  {name:<36} {cat}", ANSI_WHITE))
    while True:
        choice = prompt("Select dish number")
        if choice in dish_menu:
            inp["dish_name"] = dish_menu[choice]
            break
        warn(f"Enter a number between 1 and {len(dish_menu)}.")
    dish: DishProfile = FOOD_DB[inp["dish_name"]]
    inp["dish"] = dish

    # Plain Water Boiling: ask volume directly
    if dish.variable_water:
        while True:
            vol_str = prompt("Enter water volume to boil (Litres)", default="5.0")
            try:
                vol_l = float(vol_str)
                if vol_l > 0:
                    inp["water_liters"] = vol_l
                    inp["portions"] = 1
                    break
            except ValueError:
                pass
            warn("Please enter a positive number of litres.")
    else:
        # 4.2 Portion size -----------------------------------------------------
        section("Step 2 of 7 -- Portion Size")
        while True:
            p_str = prompt("Number of people / servings", default="2")
            try:
                portions = int(p_str)
                if portions >= 1:
                    inp["portions"] = portions
                    break
            except ValueError:
                pass
            warn("Enter a whole number >= 1.")

    # 4.3 Ambient temperature --------------------------------------------------
    section("Step 3 of 7 -- Ambient Temperature")
    while True:
        t_str = prompt("Ambient temperature (deg C)", default="25")
        try:
            t_amb = float(t_str)
            if -10 <= t_amb <= 50:
                inp["t_ambient_c"] = t_amb
                break
        except ValueError:
            pass
        warn("Enter a realistic ambient temperature between -10 C and 50 C.")

    # 4.4 Wind / environment ---------------------------------------------------
    wind_key = numbered_menu("Step 4 of 7 -- Cooking Environment (Wind)", WIND_OPTIONS)
    inp["wind_label"]      = WIND_OPTIONS[wind_key][0]
    inp["wind_multiplier"] = WIND_OPTIONS[wind_key][1]
    inp["wind_high"]       = (wind_key == "4")

    # 4.5 Vessel configuration -------------------------------------------------
    vessel_key = numbered_menu("Step 5 of 7 -- Vessel Type", VESSEL_TYPES)
    inp["vessel_type"]       = VESSEL_TYPES[vessel_key]
    is_pc                    = (vessel_key == "4")
    inp["is_pressure_cooker"] = is_pc

    mat_key = numbered_menu("Vessel Material", VESSEL_MATERIALS)
    inp["vessel_material_name"] = VESSEL_MATERIALS[mat_key][0]
    inp["cp_vessel_kj_kgk"]     = VESSEL_MATERIALS[mat_key][1]

    # Smart default vessel mass
    ref_count = inp["water_liters"] if dish.variable_water else inp["portions"]
    ref_label = "L" if dish.variable_water else "person"
    smart_kg  = max(round(0.3 * ref_count, 2), 0.30)
    section("Vessel Mass")
    plural = "s" if ref_count != 1 else ""
    print(c(f"  Smart Default: {smart_kg:.2f} kg  (~0.30 kg x {ref_count} {ref_label}{plural})", ANSI_DIM))
    while True:
        m_str = prompt("Vessel mass (kg) -- press Enter to accept smart default",
                       default=str(smart_kg))
        try:
            m_vessel = float(m_str)
            if m_vessel > 0:
                inp["m_vessel_kg"] = m_vessel
                break
        except ValueError:
            pass
        warn("Enter a positive mass in kg.")

    # 4.6 Lid state ------------------------------------------------------------
    if is_pc:
        inp["lid_state"]     = "On (Pressure Cooker -- forced)"
        inp["evap_fraction"] = EVAP_FRAC_PRESSURE_COOKER
    else:
        section("Step 6 of 7 -- Lid State")
        lid_opts = {"1": "Lid On", "2": "Lid Off"}
        lid_key  = numbered_menu("Lid State", lid_opts)
        inp["lid_state"]     = lid_opts[lid_key]
        inp["evap_fraction"] = EVAP_FRAC_LID_ON if lid_key == "1" else EVAP_FRAC_LID_OFF

    # 4.7 Pellet selection -----------------------------------------------------
    section("Step 7 of 7 -- Pellet Type")
    pellet_names = get_pellet_names()
    pel_menu     = {str(i + 1): name for i, name in enumerate(pellet_names)}
    for key, name in pel_menu.items():
        p = PELLET_DB[name]
        gcv_str = f"{p.gcv_min_kcal:,}-{p.gcv_max_kcal:,} kcal/kg  [{p.category}]"
        print(c(f"    [{key:>2}]  {name:<42} {gcv_str}", ANSI_WHITE))
    while True:
        choice = prompt("Select pellet type")
        if choice in pel_menu:
            inp["pellet_name"] = pel_menu[choice]
            inp["pellet"]      = PELLET_DB[inp["pellet_name"]]
            break
        warn(f"Enter a number between 1 and {len(pel_menu)}.")

    return inp


# =============================================================================
# SECTION 5 -- PHYSICS ENGINE
# =============================================================================

def derive_thermal_params(inp: dict) -> dict:
    """Derive food mass, water mass, and delta_T from validated inputs."""
    dish: DishProfile = inp["dish"]
    is_pc: bool       = inp["is_pressure_cooker"]

    t_target_c = T_BOIL_PRESSURE_C if is_pc else T_BOIL_NORMAL_C
    delta_t    = max(t_target_c - inp["t_ambient_c"], 1.0)

    if dish.variable_water:
        m_food_kg  = 0.001
        m_water_kg = inp["water_liters"]
        cp_food    = dish.cp_food_kj_kgk
    else:
        n          = inp["portions"]
        m_food_kg  = dish.food_mass_per_serving_kg   * n
        m_water_kg = dish.added_water_per_serving_kg * n
        cp_food    = dish.cp_food_kj_kgk

    inp.update({
        "m_food_kg":  m_food_kg,
        "m_water_kg": m_water_kg,
        "cp_food":    cp_food,
        "t_target_c": t_target_c,
        "delta_t":    delta_t,
    })
    return inp


# -- Step 1 -- Sensible Heat --------------------------------------------------

def step1_sensible_heat(inp: dict) -> float:
    """
    Q_sensible = m_food*Cp_food*dT + m_water*Cp_water*dT + m_pot*Cp_pot*dT
    Returns Q_sensible in kJ.
    """
    q_food  = inp["m_food_kg"]   * inp["cp_food"]          * inp["delta_t"]
    q_water = inp["m_water_kg"]  * CP_WATER_KJ_KGK          * inp["delta_t"]
    q_pot   = inp["m_vessel_kg"] * inp["cp_vessel_kj_kgk"]  * inp["delta_t"]
    q_sens  = q_food + q_water + q_pot

    inp["q_food_kj"]     = q_food
    inp["q_water_kj"]    = q_water
    inp["q_pot_kj"]      = q_pot
    inp["q_sensible_kj"] = q_sens
    return q_sens


# -- Step 2 -- Time Anchor ----------------------------------------------------

def step2_time_anchor(inp: dict) -> float:
    """
    Derives physics-based t_total suggestion, displays it, then lets the user
    confirm or override. Returns the user-approved t_total in seconds.
    """
    pellet: PelletType  = inp["pellet"]
    dish:   DishProfile = inp["dish"]
    is_pc:  bool        = inp["is_pressure_cooker"]

    gcv_kj_kg = pellet.conservative_gcv_kj

    # Stove thermal power: burn_rate (kg/s) * GCV (kJ/kg) * eta_baseline
    stove_power_kw = (STOVE_BURN_RATE_KG_HR / 3600.0) * gcv_kj_kg * BASELINE_EFFICIENCY

    # Heating time: Q_sensible (kJ) / Power (kW) = seconds
    t_heating_s   = inp["q_sensible_kj"] / stove_power_kw
    t_heating_min = t_heating_s / 60.0

    # Kinetic time: sum all kinetic & frying stages from food_db
    t_kinetic_s: float = sum(
        s.duration_s for s in dish.stages if s.stage_type in ("kinetic", "frying")
    )
    if is_pc:
        t_kinetic_s *= PC_KINETIC_FACTOR
    t_kinetic_min = t_kinetic_s / 60.0

    t_suggested_s   = t_heating_s + t_kinetic_s
    t_suggested_min = t_suggested_s / 60.0

    inp["t_heating_s"]    = t_heating_s
    inp["t_kinetic_s"]    = t_kinetic_s
    inp["stove_power_kw"] = stove_power_kw

    section("Step 2 -- Time Anchor  (Physics-Derived Suggestion)")
    info("Stove thermal power  (0.78 kg/hr @ 45% eta)", f"{stove_power_kw:.4f}", "kW")
    info("Heating time   (Q_sensible / Power)",          f"{t_heating_min:.1f}",  "min")
    info("Kinetic time   (food_db stages)",               f"{t_kinetic_min:.1f}",  "min")
    if is_pc:
        print(c("  [Pressure Cooker: kinetic time reduced by 65%]", ANSI_DIM))
    print()
    print(c(
        f"  >>> Suggested total cooking time :  "
        f"{t_suggested_min:.1f} min  ({t_suggested_s:.0f} s)",
        ANSI_BOLD, ANSI_GREEN
    ))

    section("Enter Your Planned Cooking Time")
    while True:
        t_str = prompt(
            f"Total cooking time (minutes) -- press Enter to accept {t_suggested_min:.1f} min",
            default=f"{t_suggested_min:.1f}"
        )
        try:
            t_total_min = float(t_str)
            if t_total_min > 0:
                break
        except ValueError:
            pass
        warn("Enter a positive number of minutes.")

    t_total_s = t_total_min * 60.0
    inp["t_total_s"]   = t_total_s
    inp["t_total_min"] = t_total_min
    return t_total_s


# -- Step 3 -- Energy Bleed ---------------------------------------------------

def step3_energy_bleed(inp: dict) -> tuple:
    """
    Q_maintain: convective/radiative loss split between heating and kinetic phases.
    Q_evap:     evaporation using Square-Cube Law, applied mostly during kinetic phase.
    """
    t_heating_s: float = inp.get("t_heating_s", 0.0)
    t_kinetic_s: float = inp.get("t_total_s", 0.0) - t_heating_s
    if t_kinetic_s < 0:
        t_kinetic_s = 0.0

    wind_mult:  float  = inp["wind_multiplier"]
    evap_frac:  float  = inp["evap_fraction"]
    m_water_kg: float  = inp["m_water_kg"]
    vessel: str        = inp["vessel_type"]

    # Extract vessel-specific properties
    base_loss_kw    = VESSEL_PROPERTIES[vessel]["loss_kw"]
    base_evap_g_min = VESSEL_PROPERTIES[vessel]["evap_g_min"]
    base_evap_kg_s  = (base_evap_g_min / 1000.0) / 60.0

    # 1. Convection / radiation loss
    # Pot averages 50% temp during heating phase, 100% temp during kinetic phase
    q_maintain_heating = (base_loss_kw * 0.5) * wind_mult * t_heating_s
    q_maintain_kinetic = base_loss_kw * wind_mult * t_kinetic_s
    q_maintain_kj = q_maintain_heating + q_maintain_kinetic

    # 2. Square-Cube evaporation scaling
    volume_l     = m_water_kg  # rho_water ~ 1 kg/L
    volume_ratio = volume_l / REF_VOLUME_L
    scaled_evap_rate_kg_s = base_evap_kg_s * (volume_ratio ** (2.0 / 3.0))

    # Evaporation is ~10% during heat-up, 100% during kinetic simmer
    m_evap_heating = scaled_evap_rate_kg_s * t_heating_s * evap_frac * 0.10
    m_evap_kinetic = scaled_evap_rate_kg_s * t_kinetic_s * evap_frac * 1.00

    m_evap_kg = m_evap_heating + m_evap_kinetic
    q_evap_kj = m_evap_kg * L_WATER_KJ_KG

    inp["q_maintain_kj"]         = q_maintain_kj
    inp["q_evap_kj"]             = q_evap_kj
    inp["m_evap_kg"]             = m_evap_kg
    inp["scaled_evap_rate_kg_s"] = scaled_evap_rate_kg_s
    inp["volume_l"]              = volume_l

    return q_maintain_kj, q_evap_kj


# -- Step 4 -- 3-Phase Combustion Integrator ----------------------------------

def step4_combustion_integrator(inp: dict) -> float:
    """
    Absolute time-window phase boundaries (NOT percentages of t_total):
      Phase 1 -- Ignition : minutes 0 -> 10
      Phase 2 -- Steady   : minutes 10 -> (t_total - 5)
      Phase 3 -- Decline  : last 5 minutes of t_total

    High-wind condition drops ignition efficiency from 25% to 15%.
    Returns eta_weighted (dimensionless).
    """
    t_total_s: float = inp["t_total_s"]
    wind_high: bool  = inp["wind_high"]

    t_ign_s  = IGNITION_PHASE_DURATION_MIN * 60.0
    t_dec_s  = DECLINE_PHASE_DURATION_MIN  * 60.0
    eff_ign  = EFF_IGNITION_HIGHWIND if wind_high else EFF_IGNITION_NORMAL

    t_phase1 = min(t_ign_s, t_total_s)
    t_phase3 = min(t_dec_s, max(0.0, t_total_s - t_ign_s))
    t_phase2 = max(0.0, t_total_s - t_phase1 - t_phase3)

    eta_weighted = (
        eff_ign      * t_phase1 +
        EFF_STEADY   * t_phase2 +
        EFF_DECLINE  * t_phase3
    ) / t_total_s

    inp["t_phase1_s"]   = t_phase1
    inp["t_phase2_s"]   = t_phase2
    inp["t_phase3_s"]   = t_phase3
    inp["eff_ign"]      = eff_ign
    inp["eta_weighted"] = eta_weighted
    return eta_weighted


# -- Final Calculation --------------------------------------------------------

def final_calculation(inp: dict) -> float:
    """
    Q_total = Q_sensible + Q_maintain + Q_evap
    Pellet_mass_g = (Q_total / (eta_weighted * GCV_conservative)) * 1000
    Returns pellet mass in grams.
    """
    q_total_kj = inp["q_sensible_kj"] + inp["q_maintain_kj"] + inp["q_evap_kj"]
    pellet: PelletType = inp["pellet"]
    gcv_kj_kg          = pellet.conservative_gcv_kj

    pellet_mass_kg = q_total_kj / (inp["eta_weighted"] * gcv_kj_kg)
    pellet_mass_g  = pellet_mass_kg * 1000.0

    inp["q_total_kj"]     = q_total_kj
    inp["pellet_mass_kg"] = pellet_mass_kg
    inp["pellet_mass_g"]  = pellet_mass_g
    return pellet_mass_g


# =============================================================================
# SECTION 6 -- PROFESSIONAL TERMINAL RECEIPT
# =============================================================================

def _bar(fraction: float, width: int = 24) -> str:
    filled = int(min(max(fraction, 0.0), 1.0) * width)
    return "|" + "#" * filled + "-" * (width - filled) + "|"


def print_receipt(inp: dict) -> None:
    """Render a clean, professional calculation receipt to stdout."""
    now_str    = datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    dish_name  = inp["dish_name"]
    pellet: PelletType = inp["pellet"]
    q_tot      = inp["q_total_kj"]

    def box_row(label: str, val: str, unit: str = "", col: str = ANSI_CYAN) -> None:
        u = f" {unit}" if unit else ""
        v = f"{val}{u}"
        pad = max(0, 60 - len(label) - len(v))
        print(c(f"  | {label}", col) + c(v, ANSI_GREEN, ANSI_BOLD) + c(" " * pad + "|", col))

    def divider(col: str = ANSI_CYAN) -> None:
        print(c("  +" + "-" * 70 + "+", col))

    def title_box(title_: str, col: str = ANSI_CYAN) -> None:
        print(c(f"\n  +-- {title_} " + "-" * max(2, 65 - len(title_)) + "+", col, ANSI_BOLD))

    # Header -------------------------------------------------------------------
    print()
    print(c("=" * 72, ANSI_CYAN, ANSI_BOLD))
    print(c("  IIT DELHI -- BIOMASS PELLET COOKSTOVE  |  CALCULATION RECEIPT", ANSI_BOLD, ANSI_WHITE))
    print(c("=" * 72, ANSI_CYAN, ANSI_BOLD))
    print(c(f"  Generated  : {now_str}", ANSI_DIM))
    print(c(f"  Engine     : main_logic.py v9.0.0  |  IIT Delhi Thermodynamic Solver", ANSI_DIM))
    print()

    # Inputs -------------------------------------------------------------------
    title_box("INPUTS", ANSI_CYAN)
    box_row("Dish",                        dish_name,                         col=ANSI_CYAN)
    if inp["dish"].variable_water:
        box_row("Water volume",            f"{inp['water_liters']:.2f}",      "L",       ANSI_CYAN)
    else:
        box_row("Portions",                str(inp["portions"]),               "person(s)",ANSI_CYAN)
    box_row("Ambient temperature",         f"{inp['t_ambient_c']:.1f}",       "C",       ANSI_CYAN)
    box_row("Target temperature",          f"{inp['t_target_c']:.0f}",        "C",       ANSI_CYAN)
    box_row("Delta-T",                     f"{inp['delta_t']:.1f}",           "K",       ANSI_CYAN)
    box_row("Cooking environment",         inp["wind_label"],                             ANSI_CYAN)
    box_row("Vessel type",                 inp["vessel_type"],                            ANSI_CYAN)
    box_row("Vessel material  (Cp)",
            f"{inp['vessel_material_name']}  Cp={inp['cp_vessel_kj_kgk']:.2f}",
            "kJ/kg.K", ANSI_CYAN)
    box_row("Vessel mass",                 f"{inp['m_vessel_kg']:.3f}",       "kg",      ANSI_CYAN)
    box_row("Lid state",                   inp["lid_state"],                              ANSI_CYAN)
    box_row("Pellet type",                 pellet.name,                                   ANSI_CYAN)
    box_row("Pellet GCV (conservative)",
            f"{pellet.gcv_min_kcal:,}",
            f"kcal/kg = {pellet.conservative_gcv_kj:,.1f} kJ/kg", ANSI_CYAN)
    box_row("Total cook time",             f"{inp['t_total_min']:.1f}",       "min",     ANSI_CYAN)
    divider(ANSI_CYAN)

    # Thermal mass -------------------------------------------------------------
    title_box("THERMAL MASS BREAKDOWN", ANSI_MAGENTA)
    box_row("Food mass (solids)",          f"{inp['m_food_kg']*1000:.2f}",    "g",       ANSI_MAGENTA)
    box_row("Water mass (cooking)",        f"{inp['m_water_kg']*1000:.2f}",   "g",       ANSI_MAGENTA)
    box_row("Vessel mass",                 f"{inp['m_vessel_kg']*1000:.2f}",  "g",       ANSI_MAGENTA)
    box_row("Food Cp",                     f"{inp['cp_food']:.3f}",           "kJ/kg.K", ANSI_MAGENTA)
    box_row("Water Cp (NIST exact)",       f"{CP_WATER_KJ_KGK:.3f}",         "kJ/kg.K", ANSI_MAGENTA)
    box_row("Vessel Cp",                   f"{inp['cp_vessel_kj_kgk']:.2f}",  "kJ/kg.K", ANSI_MAGENTA)
    divider(ANSI_MAGENTA)

    # Energy breakdown ---------------------------------------------------------
    q_sens  = inp["q_sensible_kj"]
    q_maint = inp["q_maintain_kj"]
    q_evap  = inp["q_evap_kj"]
    vol_ratio = inp["volume_l"] / REF_VOLUME_L

    title_box("ENERGY BREAKDOWN", ANSI_YELLOW)

    def erow(label: str, val_kj: float, note: str = "") -> None:
        bar_str = _bar(val_kj / max(q_tot, 1e-9))
        pct     = 100.0 * val_kj / max(q_tot, 1e-9)
        print(c(f"  | {label:<32} {val_kj:>9.2f} kJ {pct:5.1f}%  {bar_str}", ANSI_YELLOW)
              + c(f"  [{note}]" if note else "", ANSI_DIM))

    erow("Q_food   (sensible, food solids)",
         inp["q_food_kj"],
         f"m={inp['m_food_kg']:.4f}kg, Cp={inp['cp_food']:.3f} kJ/kg.K")
    erow("Q_water  (sensible, water)",
         inp["q_water_kj"],
         f"m={inp['m_water_kg']:.4f}kg, Cp={CP_WATER_KJ_KGK:.3f} kJ/kg.K")
    erow("Q_pot    (sensible, vessel)",
         inp["q_pot_kj"],
         f"m={inp['m_vessel_kg']:.4f}kg, Cp={inp['cp_vessel_kj_kgk']:.2f} kJ/kg.K")
    print(c("  |" + " " * 70 + "|", ANSI_YELLOW))
    print(c(f"  |  {'Q_SENSIBLE  (subtotal)':<32} {q_sens:>9.2f} kJ" + " " * 26 + "|",
            ANSI_YELLOW, ANSI_BOLD))
    print(c("  |" + "." * 70 + "|", ANSI_YELLOW))
    erow("Q_maintain (convection losses)",
         q_maint,
         f"Vessel base {VESSEL_PROPERTIES[inp['vessel_type']]['loss_kw']:.3f} kW x "
         f"{inp['wind_multiplier']:.2f}x wind | heat-phase 50%, kinetic 100%")
    erow("Q_evap   (latent heat losses)",
         q_evap,
         f"V={inp['volume_l']:.3f}L, scaling=(V/Vref)^2/3={vol_ratio**(2/3):.4f}, "
         f"frac={inp['evap_fraction']:.2f}, m_evap={inp['m_evap_kg']*1000:.2f}g")
    print(c("  |" + " " * 70 + "|", ANSI_YELLOW))
    print(c(f"  |  {'Q_TOTAL  (grand total)':<32} {q_tot:>9.2f} kJ" + " " * 26 + "|",
            ANSI_YELLOW, ANSI_BOLD))
    divider(ANSI_YELLOW)

    # Combustion phase analysis ------------------------------------------------
    title_box("3-PHASE COMBUSTION INTEGRATOR", ANSI_BLUE)

    def crow(label: str, val: str) -> None:
        pad = max(0, 52 - len(label) - len(val))
        print(c(f"  | {label}", ANSI_BLUE) + c(val, ANSI_WHITE) + c(" " * pad + "|", ANSI_BLUE))

    crow("Total cook time",
         f"{inp['t_total_min']:.1f} min  ({inp['t_total_s']:.0f} s)")
    crow("Phase 1 -- Ignition  (min 0 to 10)",
         f"{inp['t_phase1_s']/60:.1f} min @ eta = {inp['eff_ign']*100:.0f}%"
         + (" [HIGH-WIND PENALTY]" if inp["wind_high"] else ""))
    crow("Phase 2 -- Steady    (10 min to t-5 min)",
         f"{inp['t_phase2_s']/60:.1f} min @ eta = {EFF_STEADY*100:.0f}%")
    crow("Phase 3 -- Decline   (last 5 min)",
         f"{inp['t_phase3_s']/60:.1f} min @ eta = {EFF_DECLINE*100:.0f}%")
    print(c("  |" + "." * 70 + "|", ANSI_BLUE))
    crow("eta_weighted  (time-weighted avg)",
         f"{inp['eta_weighted']*100:.4f}%")
    divider(ANSI_BLUE)

    # Final result -------------------------------------------------------------
    mass_g   = inp["pellet_mass_g"]
    mass_str = f"{mass_g:.1f} g"
    if mass_g >= 1000:
        mass_str += f"  ({mass_g/1000:.3f} kg)"

    print()
    print(c("=" * 72, ANSI_GREEN, ANSI_BOLD))
    print(c("  RECOMMENDED PELLET MASS : ", ANSI_BOLD, ANSI_WHITE)
          + c(mass_str, ANSI_BOLD, ANSI_GREEN)
          + c(f"   <-- {pellet.name}", ANSI_DIM))
    print()
    formula = (
        f"  Formula: m = Q_total / (eta_w x GCV) = "
        f"{q_tot:.2f} / ({inp['eta_weighted']:.4f} x "
        f"{pellet.conservative_gcv_kj:.1f}) = {inp['pellet_mass_kg']:.6f} kg"
    )
    print(c(formula, ANSI_DIM))
    print(c("=" * 72, ANSI_GREEN, ANSI_BOLD))
    print()
    print(c("  NOTE: Add >= 10% safety margin for real-world procurement.", ANSI_DIM))
    print(c("  All physics: 4-Step IIT Delhi Thermodynamic Solver v9.0.0.", ANSI_DIM))
    print(c("-" * 72, ANSI_DIM))
    print()


# =============================================================================
# SECTION 7 -- MAIN ENTRY POINT
# =============================================================================

def main() -> None:
    """CLI entry point -- executes the 4-step thermodynamic architecture in sequence."""
    try:
        # PHASE A: Collect all user inputs
        inp = collect_inputs()

        # PHASE B: Derive thermal parameters
        derive_thermal_params(inp)

        header("PHYSICS ENGINE -- Executing 4-Step Thermodynamic Solver")

        # Step 1 ---------------------------------------------------------------
        section("Step 1 -- Sensible Heat Target  (Q_sensible)")
        step1_sensible_heat(inp)
        info("Q_food   (food solids, sensible)",   f"{inp['q_food_kj']:.4f}",  "kJ")
        info("Q_water  (cooking water, sensible)",  f"{inp['q_water_kj']:.4f}", "kJ")
        info("Q_pot    (vessel, sensible)",          f"{inp['q_pot_kj']:.4f}",  "kJ")
        info("Q_sensible  TOTAL",                    f"{inp['q_sensible_kj']:.4f}", "kJ")

        # Step 2 ---------------------------------------------------------------
        step2_time_anchor(inp)

        # Step 3 ---------------------------------------------------------------
        section("Step 3 -- Energy Bleed  (Convection + Evaporation)")
        step3_energy_bleed(inp)
        vol_ratio = inp["volume_l"] / REF_VOLUME_L
        info("Water volume (cooking)",              f"{inp['volume_l']:.4f}",          "L")
        info("Volume ratio  V / V_ref",             f"{vol_ratio:.4f}")
        info("Square-Cube factor  (V/Vref)^(2/3)",  f"{vol_ratio**(2/3):.4f}")
        info("Scaled evaporation rate",             f"{inp['scaled_evap_rate_kg_s']*1000:.4f}", "g/s")
        info("Evaporation fraction (lid state)",    f"{inp['evap_fraction']:.2f}")
        info("Total mass evaporated",               f"{inp['m_evap_kg']*1000:.2f}",    "g")
        info("Q_maintain (convection loss)",         f"{inp['q_maintain_kj']:.4f}",    "kJ")
        info("Q_evap     (latent heat loss)",        f"{inp['q_evap_kj']:.4f}",        "kJ")

        # Step 4 ---------------------------------------------------------------
        section("Step 4 -- 3-Phase Combustion Integrator")
        step4_combustion_integrator(inp)
        info("Ignition phase duration",             f"{inp['t_phase1_s']/60:.2f}", "min")
        info("Steady   phase duration",             f"{inp['t_phase2_s']/60:.2f}", "min")
        info("Decline  phase duration",             f"{inp['t_phase3_s']/60:.2f}", "min")
        info("eta_weighted  (time-weighted avg)",    f"{inp['eta_weighted']*100:.4f}", "%")

        # Final ----------------------------------------------------------------
        section("Final Calculation -- Pellet Mass")
        final_calculation(inp)
        info("Q_total  (sensible + all losses)",   f"{inp['q_total_kj']:.4f}",  "kJ")
        info("eta_weighted",                        f"{inp['eta_weighted']:.6f}")
        info("GCV (conservative / worst-case)",    f"{inp['pellet'].conservative_gcv_kj:.2f}", "kJ/kg")
        info("Pellet mass  (calculation result)",  f"{inp['pellet_mass_g']:.2f}", "g")

        # Receipt --------------------------------------------------------------
        print_receipt(inp)

    except KeyboardInterrupt:
        print(c("\n\n  [X]  Session cancelled by user.\n", ANSI_RED))
        sys.exit(0)
    except KeyError as exc:
        print(c(f"\n  [X]  Database lookup error: {exc}\n", ANSI_RED))
        sys.exit(1)
    except Exception as exc:
        print(c(f"\n  [X]  Unexpected error: {exc}\n", ANSI_RED))
        raise


if __name__ == "__main__":
    main()
