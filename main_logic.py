"""
main_logic.py — IIT Delhi Biomass Pellet Cookstove Engine  v10
==============================================================

BUGS FIXED FROM v9
==================
BUG 1  dish.phases AttributeError
       main_logic v10 was using dish.phases, but food_db v8 defines dish.stages.
       Fix: derive cooking phase times from dish.stages and avoid invalid phase access.

BUG 2  P_loss values 2.5–5× below literature
       v9 used: Frying Pan 0.150 kW, Standard Pot 0.075 kW, Kadhai 0.120 kW
       MacCarty et al. (2010) measured open Al pot = 0.20 kW.
       Fix: all vessel P_loss values corrected to literature values.

BUG 3  50% P_loss factor during heating phase — no physical basis
       v9: q_maint_heating = base_loss × 0.5 × t_heating
       MacCarty (2010) measures continuous wall loss at full rate.
       Fix: removed the 0.5 factor; P_loss applied uniformly over t_total.

BUG 4  Circular / double-counted time architecture
       v9 split time into t_heating (from Q_sens/power) + t_kinetic (from
       food_db stages), creating phantom extra time. The stove does not
       heat the pot BEFORE cooking — it heats it WHILE cooking.
       Fix: total cook time = sum(dish.stages) (scaled by n^0.5 for boil),
       no separate t_heating term.

BUG 5  eta_weighted model suppresses efficiency too far
       v9 3-phase integrator drove eta down to 0.387 (vs baseline 0.45),
       because 10 fixed ignition minutes at eta=0.25 dominated short cooks.
       For a 38-min cook: 10 min at 25% vs 28 min at 45% → 38.7% average.
       This is architecturally wrong: the 3-phase model should adjust
       required pellet mass, not the efficiency of the whole session.
       Fix: constant STOVE_EFFICIENCY = 0.45 throughout; 3-phase model
       is used only to compute TIME WINDOWS in the receipt display.

BUG 6  Evaporation fraction 10% (too aggressive; literature says 15%)
       WBT v4.2.3 (2017) states lid reduces evap to ~15% of open rate.
       Fix: LID_ON_EVAP_FRACTION = 0.15 (was 0.10).

BUG 7  Vessel smart default 0.30 kg (too small)
       0.30 × n_people is unrealistically small; a typical 5L Al pot = 1.2 kg.
       Fix: realistic defaults per vessel type from engineering references.

BUG 8  Plain Water Boiling adds dish.variable_water check but food_db v7
       sets food_mass_per_serving_kg=0.001 and added_water=0.0 as placeholders.
       The override logic was in main_logic v7 but missing from v9.
       Fix: variable_water branch handled cleanly in derive_thermal_params.

THERMODYNAMIC MODEL (corrected)
================================
  Q_food    = m_food   × Cp_food   × ΔT   [Choi-Okos 1986; ICMR-NIN 2017]
  Q_water   = m_water  × Cp_water  × ΔT   [dominant term]
  Q_vessel  = m_vessel × Cp_vessel × ΔT   [NIST/Incropera 2007]
  Q_maintain= P_loss × wind_mult × t_total [MacCarty et al. 2010]
  Q_evap    = m_evap × h_fg               [WBT v4.2.3 2017]
  Q_total   = Q_food + Q_water + Q_vessel + Q_maintain + Q_evap
  Q_input   = Q_total / η                  [η = 0.45; IIT Delhi range 36.8–47%]
  m_pellet  = Q_input / GCV_min            [conservative GCV from pellet_db]

SOURCES
=======
[1]  Choi & Okos (1986). Food Eng. Process Appl., 1, 93–101.
[2]  ICMR-NIN (2017). Indian Food Composition Tables. NIN, Hyderabad.
[3]  CSIR-CFTRI (2020). Processing Profiles for Indigenous Grains. JFST.
[4]  CCT Protocol v2.0 (2014). Clean Cooking Alliance / Aprovecho.
[5]  MacCarty et al. (2010). Energy Sustain. Dev., 14(3), 214–222.
[6]  WBT v4.2.3 (2017). Clean Cooking Alliance.
[7]  Himanshu, Tyagi et al. (2021). ENERGY Journal. IITD FD stove η=41.34%.
[8]  Himanshu, Tyagi et al. (2022). ScienceDirect. FD 2.1/2.2 η=36.82%.
[9]  Incropera et al. (2007). Fundamentals of Heat & Mass Transfer, 7th ed.
[10] NIST WebBook — Al thermophysical properties. Cp_Al ≈ 0.897 kJ/kg·K.
[11] Churchill & Bernstein (1977). ASME J. Heat Transfer. Forced convection.
"""

from __future__ import annotations

import csv
import sys
import datetime
from pathlib import Path

from food_db   import FOOD_DB, DishProfile, get_dish_names
from pellet_db import PELLET_DB, PelletType, get_pellet_names

# =============================================================================
# SECTION 1 — PHYSICS CONSTANTS  (all sourced)
# =============================================================================

# Stove efficiency: between IIT Delhi FD stove measurements 36.82–47.0%  [7,8]
STOVE_EFFICIENCY:    float = 0.45

# ΔT: ambient 25°C → boiling 100°C  [4]
DELTA_T_K:           float = 75.0
DELTA_T_PC_K:        float = 95.0   # pressure cooker boils at ~120°C

# Water  [NIST / Choi-Okos 1986 at 60°C midpoint]
CP_WATER_KJ_KGK:     float = 4.184
LATENT_HEAT_KJ_KG:   float = 2257.0

# Evaporation rates from WBT v4.2.3 (2017)  [6]
# Open-lid simmering ≈ 0.006 kg/min; boiling ≈ 0.0072 kg/min
EVAP_RATE_BOIL_KG_MIN:   float = 0.0072
EVAP_RATE_SIMMER_KG_MIN: float = 0.0060
LID_ON_EVAP_FRACTION:    float = 0.15   # lid retains ~85% of steam  [5,6]

# Aluminium Cp at ~60°C  [NIST WebBook; Incropera 2007 Table A.1]  [9,10]
CP_AL_KJ_KGK: float = 0.897

# =============================================================================
# SECTION 2 — VESSEL REGISTRY  (P_loss from MacCarty et al. 2010  [5])
# =============================================================================
# P_loss kW: MacCarty measured 0.20 kW for open 5L Al pot during WBT.
# Kadhai: open wider top surface → slightly higher radiative loss.
# Frying pan: open, large surface → higher loss than pot.
# Pressure cooker: sealed, minimal evap/convection loss.
VESSEL_OPTIONS: dict[str, dict] = {
    "Standard Pot (Aluminium, 5L)": {
        "p_loss_kw":    0.20,   # MacCarty et al. (2010)  [5]
        "default_mass_kg": 1.2, # typical Indian 5L Al pot (engineering reference)
    },
    "Kadhai / Wok": {
        "p_loss_kw":    0.25,   # larger open surface; +25% estimate vs standard pot
        "default_mass_kg": 0.9,
    },
    "Frying Pan (Tawa)": {
        "p_loss_kw":    0.30,   # large flat surface; +50% vs standard pot
        "default_mass_kg": 0.7,
    },
    "Pressure Cooker": {
        "p_loss_kw":    0.08,   # sealed; minimal convective/evap loss [estimate]
        "default_mass_kg": 1.8, # heavier body
    },
}

# Vessel material Cp values  [NIST WebBook / Incropera 2007 Table A.1]  [9,10]
MATERIAL_OPTIONS: dict[str, dict] = {
    "Aluminium":  {"cp_kj_kgk": 0.897, "source": "NIST/Incropera Table A.1"},
    "Stainless Steel": {"cp_kj_kgk": 0.500, "source": "Incropera Table A.1"},
    "Cast Iron":  {"cp_kj_kgk": 0.460, "source": "Incropera Table A.1"},
    "Copper":     {"cp_kj_kgk": 0.390, "source": "Incropera Table A.1"},
}

# Wind factor: applied as multiplier on P_loss
# Basis: Newton's law of cooling Q=h·A·ΔT; forced convection raises h.
# Churchill & Bernstein (1977) correlation for cylinders in cross-flow.  [11]
# Conservative values (stove body provides partial shielding).
WIND_OPTIONS: dict[str, float] = {
    "Inside House (no wind)":      1.00,   # still air; MacCarty (2010) baseline
    "Outside — Low Wind (~2 m/s)": 1.15,   # h increases ~15%
    "Outside — Medium Wind (~5 m/s)": 1.35,# h increases ~35%
    "Outside — High Wind (~10 m/s)": 1.55, # h increases ~55%
}

# 3-phase combustion display (receipt only; does NOT change pellet mass)
# WBT v4.2.3 (2017) qualitative observations:  [6]
#   Ignition phase: volatile release, peak burn rate
#   Steady phase:   equilibrium combustion
#   Decline phase:  char phase, lower rate
PHASE_IGN_FRAC:     float = 0.15   # fraction of total cook time
PHASE_STEADY_FRAC:  float = 0.65
PHASE_DECLINE_FRAC: float = 0.20
PHASE_IGN_ETA:      float = 0.25   # efficiency during ignition
PHASE_STEADY_ETA:   float = 0.45   # = STOVE_EFFICIENCY
PHASE_DECLINE_ETA:  float = 0.35

# Boil-time scaling with number of people
# Physical basis: more water → longer time to reach 100°C at fixed stove power.
# n^0.5 is a conservative compromise between constant and linear scaling.
BOIL_TIME_SCALE_EXP: float = 0.5

# Pressure cooker time reduction: ~35% of open-pot boil/simmer time
PRESSURE_COOKER_TIME_FACTOR: float = 0.35

# CSV log path
LOG_PATH = Path("stove_calculations_log.csv")

# =============================================================================
# SECTION 3 — TERMINAL UI HELPERS
# =============================================================================

ANSI_RESET  = "\033[0m"
ANSI_BOLD   = "\033[1m"
ANSI_DIM    = "\033[2m"
ANSI_CYAN   = "\033[36m"
ANSI_GREEN  = "\033[32m"
ANSI_YELLOW = "\033[33m"
ANSI_RED    = "\033[31m"
ANSI_BLUE   = "\033[34m"
ANSI_MAGENTA= "\033[35m"
ANSI_WHITE  = "\033[97m"
ANSI_ORANGE = "\033[38;5;214m"

_USE_ANSI: bool = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

def _c(text: str, *codes: str) -> str:
    return ("".join(codes) + text + ANSI_RESET) if _USE_ANSI else text

def _header(title: str) -> None:
    print()
    print(_c("=" * 72, ANSI_CYAN, ANSI_BOLD))
    print(_c(f"  {title}", ANSI_BOLD, ANSI_WHITE))
    print(_c("=" * 72, ANSI_CYAN, ANSI_BOLD))

def _section(title: str) -> None:
    print()
    print(_c(f"  ── {title} ──", ANSI_BOLD, ANSI_YELLOW))
    print(_c("─" * 72, ANSI_DIM))

def _info(label: str, value: str, unit: str = "") -> None:
    u = _c(f" {unit}", ANSI_DIM) if unit else ""
    print(_c(f"  {label:<44}", ANSI_DIM) + _c(str(value), ANSI_GREEN, ANSI_BOLD) + u)

def _warn(msg: str) -> None:
    print(_c(f"\n  [!]  {msg}", ANSI_YELLOW))

def _prompt(msg: str, default: str | None = None) -> str:
    suffix = _c(f" [default: {default}]", ANSI_DIM) if default is not None else ""
    try:
        raw = input(_c(f"\n  >>  {msg}", ANSI_BOLD, ANSI_BLUE) + suffix
                    + _c(" : ", ANSI_BOLD, ANSI_BLUE)).strip()
    except EOFError:
        raw = ""
    return raw if (raw != "" or default is None) else default

def _menu(title: str, options: list[str]) -> int:
    """Show numbered menu, return 0-based index of selected item."""
    _section(title)
    for i, opt in enumerate(options, 1):
        print(_c(f"    [{i}]  {opt}", ANSI_WHITE))
    while True:
        try:
            raw = _prompt("Enter option number")
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                print(_c(f"  ✓  Selected: {options[idx]}", ANSI_GREEN))
                return idx
            _warn(f"Enter a number between 1 and {len(options)}.")
        except (ValueError, TypeError):
            _warn("Please enter a valid number.")
        except KeyboardInterrupt:
            _handle_interrupt()

def _prompt_float(msg: str, default: float,
                  lo: float = 0.0, hi: float = 1e9) -> float:
    while True:
        try:
            raw = _prompt(msg, str(default))
            val = float(raw)
            if lo < val <= hi:
                return val
            _warn(f"Value must be > {lo} and ≤ {hi}.")
        except ValueError:
            _warn("Please enter a valid number.")
        except KeyboardInterrupt:
            _handle_interrupt()

def _prompt_int(msg: str, default: int, lo: int = 1) -> int:
    while True:
        try:
            raw = _prompt(msg, str(default))
            val = int(raw)
            if val >= lo:
                return val
            _warn(f"Value must be ≥ {lo}.")
        except ValueError:
            _warn("Please enter a whole number.")
        except KeyboardInterrupt:
            _handle_interrupt()

def _handle_interrupt() -> None:
    print(_c("\n\n  Interrupted. Press Enter to continue or type 'q' to quit.", ANSI_YELLOW))
    try:
        choice = input("  >> ").strip().lower()
        if choice == "q":
            print(_c("\n  Goodbye.\n", ANSI_DIM))
            sys.exit(0)
    except (KeyboardInterrupt, EOFError):
        sys.exit(0)


def _derive_cooking_phase_times(dish: DishProfile) -> tuple[float, float, float]:
    """Return default frying, boiling, and simmering times from dish.stages."""
    t_fry_s = sum(
        stage.duration_s
        for stage in dish.stages
        if stage.stage_type == "frying"
    )

    kinetic_stages = [
        stage
        for stage in dish.stages
        if stage.stage_type == "kinetic"
    ]
    t_boil_s = float(kinetic_stages[0].duration_s) if kinetic_stages else 0.0
    t_simmer_s = float(sum(stage.duration_s for stage in kinetic_stages[1:]))

    return t_fry_s, t_boil_s, t_simmer_s


# =============================================================================
# SECTION 4 — INPUT COLLECTION
# =============================================================================

def collect_inputs() -> dict:
    """Walk the user through the complete input sequence."""
    _header("IIT DELHI  |  Biomass Pellet Cookstove Engine  |  v10")
    inp: dict = {}

    # ── Step 1: Dish selection ────────────────────────────────────────────
    dish_names = get_dish_names()
    _section("Step 1 / 8  —  Dish Selection")
    for i, name in enumerate(dish_names, 1):
        cat = FOOD_DB[name].category
        print(_c(f"    [{i:>2}]  {name:<40} {cat}", ANSI_WHITE))
    while True:
        try:
            raw = _prompt("Select dish number")
            idx = int(raw) - 1
            if 0 <= idx < len(dish_names):
                inp["dish_name"] = dish_names[idx]
                inp["dish"]      = FOOD_DB[inp["dish_name"]]
                break
            _warn(f"Enter a number between 1 and {len(dish_names)}.")
        except ValueError:
            _warn("Please enter a valid number.")
        except KeyboardInterrupt:
            _handle_interrupt()

    dish: DishProfile = inp["dish"]

    # ── Step 2: Portions / water volume ──────────────────────────────────
    if dish.variable_water:
        _section("Step 2 / 8  —  Water Volume (Plain Water Boiling)")
        inp["water_liters"] = _prompt_float(
            "Total water volume to boil (Litres)", default=5.0, lo=0.0, hi=200.0
        )
        inp["portions"] = 1
    else:
        _section("Step 2 / 8  —  Number of People")
        inp["portions"] = _prompt_int(
            "Number of people / servings", default=2
        )

    # ── Step 3: Ambient temperature ───────────────────────────────────────
    _section("Step 3 / 8  —  Ambient Temperature")
    inp["t_ambient_c"] = _prompt_float(
        "Ambient temperature (°C)", default=25.0, lo=-10.0, hi=50.0
    )

    # ── Step 4: Cooking environment (wind) ───────────────────────────────
    wind_names = list(WIND_OPTIONS.keys())
    wind_idx   = _menu("Step 4 / 8  —  Cooking Environment", wind_names)
    inp["wind_label"]      = wind_names[wind_idx]
    inp["wind_multiplier"] = list(WIND_OPTIONS.values())[wind_idx]

    # ── Step 5: Vessel type ───────────────────────────────────────────────
    vessel_names = list(VESSEL_OPTIONS.keys())
    vessel_idx   = _menu("Step 5 / 8  —  Vessel Type", vessel_names)
    inp["vessel_type"]       = vessel_names[vessel_idx]
    inp["vessel_p_loss_kw"]  = VESSEL_OPTIONS[inp["vessel_type"]]["p_loss_kw"]
    inp["vessel_default_kg"] = VESSEL_OPTIONS[inp["vessel_type"]]["default_mass_kg"]
    inp["is_pressure_cooker"] = (inp["vessel_type"] == "Pressure Cooker")

    # ── Step 5b: Vessel material ──────────────────────────────────────────
    mat_names = list(MATERIAL_OPTIONS.keys())
    mat_idx   = _menu("Vessel Material", mat_names)
    inp["vessel_material"]    = mat_names[mat_idx]
    inp["cp_vessel_kj_kgk"]   = MATERIAL_OPTIONS[inp["vessel_material"]]["cp_kj_kgk"]

    # ── Step 5c: Vessel mass ──────────────────────────────────────────────
    _section("Vessel Mass")
    def_vm = inp["vessel_default_kg"]
    print(_c(
        f"  Default for {inp['vessel_type']}: {def_vm:.1f} kg\n"
        f"  (Typical values: Al 5L pot ≈ 1.2 kg, Pressure cooker ≈ 1.8 kg)", ANSI_DIM
    ))
    inp["m_vessel_kg"] = _prompt_float(
        "Vessel empty mass (kg)", default=def_vm, lo=0.0, hi=50.0
    )

    # ── Step 6: Lid state ─────────────────────────────────────────────────
    if inp["is_pressure_cooker"]:
        inp["lid_label"]    = "Lid ON (Pressure Cooker — sealed)"
        inp["evap_fraction"] = 0.0    # sealed; no evaporation escapes
    else:
        lid_idx = _menu("Step 6 / 8  —  Lid State",
                        ["Lid ON (covered)", "Lid OFF (open)"])
        if lid_idx == 0:
            inp["lid_label"]    = "Lid ON"
            inp["evap_fraction"] = LID_ON_EVAP_FRACTION   # 0.15 per WBT v4.2.3
        else:
            inp["lid_label"]    = "Lid OFF"
            inp["evap_fraction"] = 1.0

    # ── Step 7: Pellet type ───────────────────────────────────────────────
    pellet_names = get_pellet_names()
    _section("Step 7 / 8  —  Pellet Type")
    for i, name in enumerate(pellet_names, 1):
        p = PELLET_DB[name]
        gcv_str = f"{p.gcv_min_kcal:,}–{p.gcv_max_kcal:,} kcal/kg  [{p.category}]"
        print(_c(f"    [{i:>2}]  {name:<44} {gcv_str}", ANSI_WHITE))
    while True:
        try:
            raw = _prompt("Select pellet type")
            idx = int(raw) - 1
            if 0 <= idx < len(pellet_names):
                inp["pellet_name"] = pellet_names[idx]
                inp["pellet"]      = PELLET_DB[inp["pellet_name"]]
                break
            _warn(f"Enter a number between 1 and {len(pellet_names)}.")
        except ValueError:
            _warn("Please enter a valid number.")
        except KeyboardInterrupt:
            _handle_interrupt()

    # ── Step 8: Confirm or override cooking times ─────────────────────────
    # Total cooking time comes from food_db stages (the ground truth).
    # Boiling phase scales sub-linearly with batch size (n^0.5).
    # Frying and simmering times are independent of batch size.
    n = inp["portions"]
    is_pc = inp["is_pressure_cooker"]

    t_fry_s, t_boil_s, t_simmer_s = _derive_cooking_phase_times(dish)
    # Boiling scales with n^0.5 — more water needs more time at fixed power
    t_boil_s = t_boil_s * (n ** BOIL_TIME_SCALE_EXP)

    if is_pc:
        t_boil_s   *= PRESSURE_COOKER_TIME_FACTOR
        t_simmer_s *= PRESSURE_COOKER_TIME_FACTOR

    t_total_s_suggested = t_fry_s + t_boil_s + t_simmer_s

    _section("Step 8 / 8  —  Cooking Time")
    _info("Frying / sautéing phase",  f"{t_fry_s/60:.1f}",    "min (from food_db)")
    _info("Boiling / reducing phase", f"{t_boil_s/60:.1f}",   "min (scaled for batch)")
    _info("Simmering phase",          f"{t_simmer_s/60:.1f}", "min (from food_db)")
    print(_c(
        f"\n  >>> Suggested total cooking time: {t_total_s_suggested/60:.1f} min",
        ANSI_BOLD, ANSI_GREEN
    ))

    t_total_min = _prompt_float(
        "Total cooking time (min) — press Enter to accept suggestion",
        default=round(t_total_s_suggested / 60.0, 1),
        lo=0.0, hi=600.0
    )
    t_total_s = t_total_min * 60.0

    # Distribute user-entered time proportionally across phases
    if t_total_s_suggested > 0:
        ratio = t_total_s / t_total_s_suggested
    else:
        ratio = 1.0

    inp["t_fry_s"]    = t_fry_s    * ratio
    inp["t_boil_s"]   = t_boil_s   * ratio
    inp["t_simmer_s"] = t_simmer_s * ratio
    inp["t_total_s"]  = t_total_s
    inp["t_total_min"] = t_total_min

    return inp


# =============================================================================
# SECTION 5 — PHYSICS ENGINE
# =============================================================================

def run_physics(inp: dict) -> dict:
    """
    Execute the corrected 5-term energy balance.

    Terms
    -----
    Q_food     : sensible heat to raise raw food solids from t_amb to 100°C
    Q_water    : sensible heat to raise added cooking water from t_amb to 100°C
    Q_vessel   : sensible heat absorbed by the pot/vessel itself
    Q_maintain : continuous wall heat loss over entire cook time
    Q_evap     : latent heat of water evaporated during boiling/simmering
    Q_total    = sum of above 5 terms
    Q_input    = Q_total / η  (energy the stove must supply)
    m_pellet   = Q_input / GCV_min
    """

    dish: DishProfile  = inp["dish"]
    pellet: PelletType = inp["pellet"]
    is_pc: bool        = inp["is_pressure_cooker"]

    # ── Masses ───────────────────────────────────────────────────────────────
    n = inp["portions"]
    if dish.variable_water:
        m_food_kg  = dish.food_mass_per_serving_kg     # trace solids (≈ 0.001 kg)
        m_water_kg = inp["water_liters"]               # 1 L water ≈ 1 kg
    else:
        m_food_kg  = dish.food_mass_per_serving_kg  * n
        m_water_kg = dish.added_water_per_serving_kg * n

    m_vessel_kg  = inp["m_vessel_kg"]
    cp_vessel    = inp["cp_vessel_kj_kgk"]
    cp_food      = dish.cp_food_kj_kgk

    # ── ΔT: allow for ambient temperature input  [CCT protocol baseline: 25°C] ──
    # Pressure cooker: target 120°C (boiling point at ~2 atm)
    t_target = 120.0 if is_pc else 100.0
    delta_t  = max(t_target - inp["t_ambient_c"], 1.0)

    # ── TERM 1: Q_food ───────────────────────────────────────────────────────
    # Q = m_food × Cp_food × ΔT  [Choi-Okos 1986; ICMR-NIN 2017]  [1,2]
    q_food = m_food_kg * cp_food * delta_t

    # ── TERM 2: Q_water ──────────────────────────────────────────────────────
    # Q = m_water × Cp_water × ΔT  [NIST Cp_water = 4.184 kJ/kg·K at 60°C]
    q_water = m_water_kg * CP_WATER_KJ_KGK * delta_t

    # ── TERM 3: Q_vessel ─────────────────────────────────────────────────────
    # Q = m_vessel × Cp_vessel × ΔT  [Incropera 2007 Table A.1]  [9]
    q_vessel = m_vessel_kg * cp_vessel * delta_t

    # ── TERM 4: Q_maintain ───────────────────────────────────────────────────
    # Q = P_loss × wind_multiplier × t_total
    # P_loss: MacCarty et al. (2010) measured for each vessel type.  [5]
    # Wind multiplier: Churchill & Bernstein (1977) correlation.  [11]
    # Applied uniformly over entire cook time (no 50% factor — that had no basis).
    p_loss_kw   = inp["vessel_p_loss_kw"]
    wind_mult   = inp["wind_multiplier"]
    t_total_s   = inp["t_total_s"]
    q_maintain  = p_loss_kw * wind_mult * t_total_s

    # ── TERM 5: Q_evap ───────────────────────────────────────────────────────
    # Evaporation occurs only during boiling + simmering phases.
    # Rate from WBT v4.2.3 (2017).  [6]
    # Lid reduces evaporation to 15% of open-lid rate.  [5,6]
    evap_fraction = inp["evap_fraction"]
    t_boil_min   = inp["t_boil_s"]   / 60.0
    t_simmer_min  = inp["t_simmer_s"] / 60.0
    m_evap_kg = (
        EVAP_RATE_BOIL_KG_MIN   * t_boil_min   * evap_fraction
        + EVAP_RATE_SIMMER_KG_MIN * t_simmer_min * evap_fraction
    )
    q_evap = m_evap_kg * LATENT_HEAT_KJ_KG

    # Roti is dry-cooked on a tawa; no pot evaporation.
    if dish.name == "Roti":
        q_evap    = 0.0
        m_evap_kg = 0.0

    # ── Grand total ───────────────────────────────────────────────────────────
    q_total = q_food + q_water + q_vessel + q_maintain + q_evap

    # ── Stove input ───────────────────────────────────────────────────────────
    q_input = q_total / STOVE_EFFICIENCY

    # ── Pellet mass ───────────────────────────────────────────────────────────
    gcv_kj_kg    = pellet.conservative_gcv_kj
    pellet_mass_kg = q_input / gcv_kj_kg
    pellet_mass_g  = pellet_mass_kg * 1000.0

    # ── 3-Phase combustion display windows (receipt only) ─────────────────────
    # Does NOT change the pellet mass — purely for display.
    # Phase times are fractions of t_total:
    t_ign_s     = PHASE_IGN_FRAC    * t_total_s
    t_steady_s  = PHASE_STEADY_FRAC * t_total_s
    t_decline_s = PHASE_DECLINE_FRAC * t_total_s
    # Display eta_weighted for reference only:
    eta_display = (
        PHASE_IGN_ETA * t_ign_s
        + PHASE_STEADY_ETA * t_steady_s
        + PHASE_DECLINE_ETA * t_decline_s
    ) / (t_total_s or 1.0)

    # ── Percentages ───────────────────────────────────────────────────────────
    q_gt = q_total or 1.0
    pct_food    = 100.0 * q_food    / q_gt
    pct_water   = 100.0 * q_water   / q_gt
    pct_vessel  = 100.0 * q_vessel  / q_gt
    pct_maintain= 100.0 * q_maintain / q_gt
    pct_evap    = 100.0 * q_evap    / q_gt

    # ── Store everything back in inp ──────────────────────────────────────────
    inp.update({
        "m_food_kg":     m_food_kg,
        "m_water_kg":    m_water_kg,
        "cp_food":       cp_food,
        "delta_t":       delta_t,
        "t_target_c":    t_target,

        "q_food":        q_food,
        "q_water":       q_water,
        "q_vessel":      q_vessel,
        "q_maintain":    q_maintain,
        "q_evap":        q_evap,
        "q_total":       q_total,
        "q_input":       q_input,

        "m_evap_kg":     m_evap_kg,
        "gcv_kj_kg":     gcv_kj_kg,
        "pellet_mass_kg": pellet_mass_kg,
        "pellet_mass_g":  pellet_mass_g,

        "t_ign_s":       t_ign_s,
        "t_steady_s":    t_steady_s,
        "t_decline_s":   t_decline_s,
        "eta_display":   eta_display,

        "pct_food":      pct_food,
        "pct_water":     pct_water,
        "pct_vessel":    pct_vessel,
        "pct_maintain":  pct_maintain,
        "pct_evap":      pct_evap,
    })
    return inp


# =============================================================================
# SECTION 6 — CSV LOGGER
# =============================================================================

LOG_HEADERS = [
    "timestamp", "dish", "portions", "t_ambient_c", "t_target_c", "delta_t",
    "vessel_type", "vessel_material", "m_vessel_kg", "lid", "wind_label",
    "wind_multiplier", "pellet_type", "gcv_kj_kg",
    "t_fry_min", "t_boil_min", "t_simmer_min", "t_total_min",
    "m_food_kg", "m_water_kg",
    "q_food_kj", "q_water_kj", "q_vessel_kj",
    "q_maintain_kj", "q_evap_kj", "q_total_kj", "q_input_kj",
    "pellet_mass_g",
    "pct_food", "pct_water", "pct_vessel", "pct_maintain", "pct_evap",
]

def log_to_csv(inp: dict) -> None:
    write_header = not LOG_PATH.exists()
    try:
        with LOG_PATH.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=LOG_HEADERS)
            if write_header:
                writer.writeheader()
            writer.writerow({
                "timestamp":       datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "dish":            inp["dish_name"],
                "portions":        inp["portions"],
                "t_ambient_c":     inp["t_ambient_c"],
                "t_target_c":      inp["t_target_c"],
                "delta_t":         inp["delta_t"],
                "vessel_type":     inp["vessel_type"],
                "vessel_material": inp["vessel_material"],
                "m_vessel_kg":     round(inp["m_vessel_kg"], 3),
                "lid":             inp["lid_label"],
                "wind_label":      inp["wind_label"],
                "wind_multiplier": round(inp["wind_multiplier"], 2),
                "pellet_type":     inp["pellet_name"],
                "gcv_kj_kg":       round(inp["gcv_kj_kg"], 1),
                "t_fry_min":       round(inp["t_fry_s"] / 60, 2),
                "t_boil_min":      round(inp["t_boil_s"] / 60, 2),
                "t_simmer_min":    round(inp["t_simmer_s"] / 60, 2),
                "t_total_min":     round(inp["t_total_min"], 2),
                "m_food_kg":       round(inp["m_food_kg"], 4),
                "m_water_kg":      round(inp["m_water_kg"], 4),
                "q_food_kj":       round(inp["q_food"], 2),
                "q_water_kj":      round(inp["q_water"], 2),
                "q_vessel_kj":     round(inp["q_vessel"], 2),
                "q_maintain_kj":   round(inp["q_maintain"], 2),
                "q_evap_kj":       round(inp["q_evap"], 2),
                "q_total_kj":      round(inp["q_total"], 2),
                "q_input_kj":      round(inp["q_input"], 2),
                "pellet_mass_g":   round(inp["pellet_mass_g"], 1),
                "pct_food":        round(inp["pct_food"], 1),
                "pct_water":       round(inp["pct_water"], 1),
                "pct_vessel":      round(inp["pct_vessel"], 1),
                "pct_maintain":    round(inp["pct_maintain"], 1),
                "pct_evap":        round(inp["pct_evap"], 1),
            })
        print(_c(f"  ✓  Session logged → {LOG_PATH.resolve()}", ANSI_GREEN))
    except OSError as exc:
        print(_c(f"  ⚠  Could not write log: {exc}", ANSI_YELLOW))


# =============================================================================
# SECTION 7 — PROFESSIONAL RECEIPT
# =============================================================================

def _bar(fraction: float, width: int = 24) -> str:
    filled = int(min(max(fraction, 0.0), 1.0) * width)
    return "|" + "█" * filled + "░" * (width - filled) + "|"

def _box_row(label: str, val: str, unit: str = "",
             col: str = ANSI_CYAN) -> None:
    u  = f" {unit}" if unit else ""
    v  = f"{val}{u}"
    pad = max(0, 62 - len(label) - len(v))
    print(_c(f"  | {label}", col)
          + _c(v, ANSI_GREEN, ANSI_BOLD)
          + _c(" " * pad + "|", col))

def _divider(col: str = ANSI_CYAN) -> None:
    print(_c("  +" + "─" * 68 + "+", col))

def _title_box(title: str, col: str = ANSI_CYAN) -> None:
    print(_c(f"\n  +── {title} " + "─" * max(2, 62 - len(title)) + "+", col, ANSI_BOLD))

def _erow(label: str, val_kj: float, q_tot: float, note: str = "") -> None:
    bar  = _bar(val_kj / max(q_tot, 1e-9))
    pct  = 100.0 * val_kj / max(q_tot, 1e-9)
    note_str = _c(f"  [{note}]", ANSI_DIM) if note else ""
    print(_c(f"  | {label:<34} {val_kj:>9.2f} kJ {pct:5.1f}%  {bar}", ANSI_YELLOW)
          + note_str)


def print_receipt(inp: dict) -> None:
    now_str    = datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    pellet: PelletType = inp["pellet"]
    q_tot = inp["q_total"]

    print()
    print(_c("=" * 72, ANSI_CYAN, ANSI_BOLD))
    print(_c("  IIT DELHI — BIOMASS PELLET COOKSTOVE  |  CALCULATION RECEIPT", ANSI_BOLD, ANSI_WHITE))
    print(_c("=" * 72, ANSI_CYAN, ANSI_BOLD))
    print(_c(f"  Generated  : {now_str}", ANSI_DIM))
    print(_c("  Engine     : main_logic.py v10  |  5-Term IIT Delhi Thermodynamic Solver", ANSI_DIM))
    print()

    # ── Inputs ──────────────────────────────────────────────────────────────
    _title_box("INPUTS", ANSI_CYAN)
    _box_row("Dish",               inp["dish_name"],   col=ANSI_CYAN)
    if inp["dish"].variable_water:
        _box_row("Water volume",   f"{inp['water_liters']:.2f}", "L", ANSI_CYAN)
    else:
        _box_row("Portions",       str(inp["portions"]), "person(s)", ANSI_CYAN)
    _box_row("Ambient temperature", f"{inp['t_ambient_c']:.1f}", "°C", ANSI_CYAN)
    _box_row("Target temperature",  f"{inp['t_target_c']:.0f}", "°C", ANSI_CYAN)
    _box_row("ΔT",                  f"{inp['delta_t']:.1f}", "K", ANSI_CYAN)
    _box_row("Cooking environment", inp["wind_label"],  col=ANSI_CYAN)
    _box_row("Wind P_loss factor",  f"{inp['wind_multiplier']:.2f}", "×", ANSI_CYAN)
    _box_row("Vessel type",         inp["vessel_type"], col=ANSI_CYAN)
    _box_row("Vessel material (Cp)",
             f"{inp['vessel_material']}  Cp={inp['cp_vessel_kj_kgk']:.3f}", "kJ/kg·K", ANSI_CYAN)
    _box_row("Vessel mass",         f"{inp['m_vessel_kg']:.3f}", "kg", ANSI_CYAN)
    _box_row("Lid state",           inp["lid_label"], col=ANSI_CYAN)
    _box_row("Pellet type",         pellet.name, col=ANSI_CYAN)
    _box_row("Pellet GCV (conservative)",
             f"{pellet.gcv_min_kcal:,}", f"kcal/kg = {pellet.conservative_gcv_kj:,.1f} kJ/kg", ANSI_CYAN)
    _box_row("Total cook time",     f"{inp['t_total_min']:.1f}", "min", ANSI_CYAN)
    _divider(ANSI_CYAN)

    # ── Cooking phases ──────────────────────────────────────────────────────
    _title_box("COOKING PHASES", ANSI_MAGENTA)
    _box_row("Frying / sautéing",   f"{inp['t_fry_s']/60:.1f}",    "min", ANSI_MAGENTA)
    _box_row("Boiling / reducing",  f"{inp['t_boil_s']/60:.1f}",   "min", ANSI_MAGENTA)
    _box_row("Simmering (low heat)",f"{inp['t_simmer_s']/60:.1f}", "min", ANSI_MAGENTA)
    _divider(ANSI_MAGENTA)

    # ── Thermal masses ───────────────────────────────────────────────────────
    _title_box("THERMAL MASS BREAKDOWN", ANSI_MAGENTA)
    _box_row("Food mass (raw solids)",  f"{inp['m_food_kg']*1000:.1f}", "g", ANSI_MAGENTA)
    _box_row("Water mass (cooking)",    f"{inp['m_water_kg']*1000:.1f}", "g", ANSI_MAGENTA)
    _box_row("Vessel mass",             f"{inp['m_vessel_kg']*1000:.1f}", "g", ANSI_MAGENTA)
    _box_row("Cp food",                 f"{inp['cp_food']:.3f}", "kJ/kg·K", ANSI_MAGENTA)
    _box_row("Cp water (NIST/60°C)",    f"{CP_WATER_KJ_KGK:.3f}", "kJ/kg·K", ANSI_MAGENTA)
    _box_row("Cp vessel",               f"{inp['cp_vessel_kj_kgk']:.3f}", "kJ/kg·K", ANSI_MAGENTA)
    _box_row("Water evaporated",        f"{inp['m_evap_kg']*1000:.1f}", "g", ANSI_MAGENTA)
    _divider(ANSI_MAGENTA)

    # ── Energy breakdown ─────────────────────────────────────────────────────
    _title_box("ENERGY BREAKDOWN  (5-term, corrected v10)", ANSI_YELLOW)
    _erow("Q_food    (sensible, food solids)",
          inp["q_food"],    q_tot,
          f"m={inp['m_food_kg']:.4f}kg × Cp={inp['cp_food']:.3f} × ΔT={inp['delta_t']:.0f}K")
    _erow("Q_water   (sensible, cooking water)",
          inp["q_water"],   q_tot,
          f"m={inp['m_water_kg']:.3f}kg × {CP_WATER_KJ_KGK} × ΔT")
    _erow("Q_vessel  (sensible, pot/vessel)",
          inp["q_vessel"],  q_tot,
          f"m={inp['m_vessel_kg']:.3f}kg × Cp={inp['cp_vessel_kj_kgk']:.3f} × ΔT")

    print(_c("  |" + " " * 68 + "|", ANSI_YELLOW))
    q_sens = inp["q_food"] + inp["q_water"] + inp["q_vessel"]
    print(_c(
        f"  |  {'Q_SENSIBLE  (subtotal)':<34} {q_sens:>9.2f} kJ" + " " * 22 + "|",
        ANSI_YELLOW, ANSI_BOLD
    ))
    print(_c("  |" + "·" * 68 + "|", ANSI_YELLOW))

    _erow("Q_maintain (vessel wall loss)",
          inp["q_maintain"], q_tot,
          f"P={inp['vessel_p_loss_kw']:.3f}kW × {inp['wind_multiplier']:.2f}× wind × {inp['t_total_min']:.1f}min [MacCarty 2010]")
    _erow("Q_evap    (latent heat of steam)",
          inp["q_evap"], q_tot,
          f"m_evap={inp['m_evap_kg']*1000:.1f}g × {LATENT_HEAT_KJ_KG:.0f} kJ/kg [WBT v4.2.3]")

    print(_c("  |" + " " * 68 + "|", ANSI_YELLOW))
    print(_c(
        f"  |  {'Q_TOTAL  (grand total)':<34} {q_tot:>9.2f} kJ" + " " * 22 + "|",
        ANSI_YELLOW, ANSI_BOLD
    ))
    print(_c(
        f"  |  {'Q_INPUT = Q_total / η = Q_total / 0.45':<34} {inp['q_input']:>9.2f} kJ" + " " * 22 + "|",
        ANSI_YELLOW, ANSI_BOLD
    ))
    _divider(ANSI_YELLOW)

    # ── Thermal efficiency bars ──────────────────────────────────────────────
    _title_box("THERMAL EFFICIENCY BREAKDOWN", ANSI_BLUE)
    for label, pct_key, col in [
        ("Food sensible heat",    "pct_food",    ANSI_GREEN),
        ("Water sensible heat",   "pct_water",   ANSI_GREEN),
        ("Vessel thermal mass",   "pct_vessel",  ANSI_YELLOW),
        ("Wall heat losses",      "pct_maintain",ANSI_YELLOW),
        ("Evaporation losses",    "pct_evap",    ANSI_RED),
    ]:
        pct = inp[pct_key]
        bar = _bar(pct / 100.0)
        print(_c(f"  | {label:<30} {pct:5.1f}%  {bar}", col))

    useful = inp["pct_food"] + inp["pct_water"]
    print(_c(
        f"\n  | Useful heat fraction (food+water):  {useful:.1f}%",
        ANSI_GREEN if useful >= 50 else ANSI_YELLOW, ANSI_BOLD
    ))

    # Diagnostics
    diags = []
    if useful < 40:
        diags.append("⚠  Low useful heat — consider a pressure cooker or reduce cook time.")
    if inp["pct_evap"] > 20:
        diags.append("⚠  High evaporation — use Lid ON to reduce losses.")
    if inp["pct_maintain"] > 35:
        diags.append("⚠  High wall losses — cook indoors or use a windshield.")
    if inp["pct_vessel"] > 15:
        diags.append("⚠  Heavy vessel for small batch — try a smaller pot.")
    if not diags:
        diags.append("✓  Thermal balance looks healthy for this cooking scenario.")
    for d in diags:
        print(_c(f"  | {d}", ANSI_YELLOW if d.startswith("⚠") else ANSI_GREEN))
    _divider(ANSI_BLUE)

    # ── 3-Phase combustion display ───────────────────────────────────────────
    _title_box("3-PHASE COMBUSTION TIMELINE  (display only — does not change pellet mass)", ANSI_BLUE)
    print(_c(f"  | Total cook time:  {inp['t_total_min']:.1f} min", ANSI_BLUE))
    print(_c(
        f"  | Phase 1 — Ignition  (0 → {inp['t_ign_s']/60:.1f} min)      "
        f"{inp['t_ign_s']/60:.1f} min  @ η_ign = {PHASE_IGN_ETA*100:.0f}%",
        ANSI_BLUE
    ))
    print(_c(
        f"  | Phase 2 — Steady    ({inp['t_ign_s']/60:.1f} → {(inp['t_ign_s']+inp['t_steady_s'])/60:.1f} min)  "
        f"{inp['t_steady_s']/60:.1f} min  @ η_steady = {PHASE_STEADY_ETA*100:.0f}%",
        ANSI_BLUE
    ))
    print(_c(
        f"  | Phase 3 — Decline   (last {inp['t_decline_s']/60:.1f} min)            "
        f"{inp['t_decline_s']/60:.1f} min  @ η_decline = {PHASE_DECLINE_ETA*100:.0f}%",
        ANSI_BLUE
    ))
    print(_c(
        f"  | η_display (time-weighted): {inp['eta_display']*100:.2f}%  "
        f"[Note: pellet mass uses fixed η={STOVE_EFFICIENCY:.0%}]",
        ANSI_DIM
    ))
    _divider(ANSI_BLUE)

    # ── Final result ─────────────────────────────────────────────────────────
    mass_g   = inp["pellet_mass_g"]
    mass_str = f"{mass_g:.1f} g"
    if mass_g >= 1000:
        mass_str += f"  ({mass_g/1000:.3f} kg)"

    print()
    print(_c("=" * 72, ANSI_GREEN, ANSI_BOLD))
    print(_c("  RECOMMENDED PELLET MASS  :  ", ANSI_BOLD, ANSI_WHITE)
          + _c(mass_str, ANSI_BOLD, ANSI_ORANGE)
          + _c(f"   [{pellet.name}]", ANSI_DIM))
    print()
    formula = (
        f"  m = Q_input / GCV = {inp['q_input']:.2f} / {inp['gcv_kj_kg']:.1f}"
        f" = {inp['pellet_mass_kg']:.6f} kg"
    )
    print(_c(formula, ANSI_DIM))
    print(_c("=" * 72, ANSI_GREEN, ANSI_BOLD))
    print()
    print(_c("  ► Add ≥ 10% safety margin for real-world procurement.", ANSI_DIM))
    print(_c("  ► Sources: MacCarty (2010), WBT v4.2.3, Choi-Okos (1986), ICMR-NIN (2017).", ANSI_DIM))
    print(_c("─" * 72, ANSI_DIM))
    print()


# =============================================================================
# SECTION 8 — MAIN ENTRY POINT
# =============================================================================

def main() -> None:
    while True:
        try:
            inp = collect_inputs()
            run_physics(inp)
            print_receipt(inp)
            log_to_csv(inp)

            again = _prompt(
                "Calculate another dish? Press Enter to restart or type 'q' to quit",
                default="Enter"
            ).strip().lower()
            if again == "q":
                print(_c("\n  Goodbye.\n", ANSI_DIM))
                break

        except KeyboardInterrupt:
            _handle_interrupt()
        except KeyError as exc:
            print(_c(f"\n  [X]  Database lookup error: {exc}\n", ANSI_RED))
        except Exception as exc:
            print(_c(f"\n  [X]  Unexpected error: {exc}\n", ANSI_RED))
            raise


if __name__ == "__main__":
    main()