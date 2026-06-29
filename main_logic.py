"""
main_logic.py
=============
1Hz Discrete Transient Biomass Cookstove Simulator
IIT Delhi · Department of Energy Studies

Architecture Reference:
    Pre-PRD Master Workflow — "1Hz Discrete Transient Biomass Cookstove Simulator"

────────────────────────────────────────────────────────────────────────────────
CORE DIRECTIVE — The "Safe Overestimate" Rule (IMMUTABLE)
────────────────────────────────────────────────────────────────────────────────
    The simulation assumes the stove burns at a CONSTANT High Fan rate
    (0.78 kg/hr) for the ENTIRE cook duration.

    • NO dynamic fan speeds.
    • NO PID controllers.
    • NO combustion efficiency penalties.

    This guarantees the pellet recommendation is always a safe upper bound —
    the user will never run out of fuel mid-cook.

    The academic "3-Phase Combustion Timeline" is generated ONLY as an
    illustrative post-processing receipt for UI/UX purposes and does NOT
    alter the governing fuel physics.

────────────────────────────────────────────────────────────────────────────────
MODEL ASSUMPTIONS (Version 1)
────────────────────────────────────────────────────────────────────────────────
    1. Lumped Capacitance: Internal temperature gradients within the pot are
       neglected — the entire thermal mass is at one uniform temperature T_pot.
    2. Static Area: The vessel surface area A is constant throughout the
       simulation; wetted-area decrease from evaporation is ignored.
    3. Empirical Geometric Coupling: η_geom is calibrated against Water
       Boiling Test (WBT) data to approximate the fraction of combustion
       energy that the pot actually captures.
"""

import math
import sys

# =============================================================================
# EXTERNAL DATABASE IMPORTS
# =============================================================================
# food_db.py — Provides FOOD_DB (dict of DishProfile), DishProfile dataclass,
#              and get_dish_names() helper.
# pellet_db.py — Provides PELLET_DB (dict of PelletType), PelletType dataclass,
#                and get_pellet_names() helper.
# Both files must be in the same directory as this script.
# =============================================================================
try:
    from food_db import FOOD_DB, DishProfile, get_dish_names
    from pellet_db import PELLET_DB, PelletType, get_pellet_names
except ModuleNotFoundError:
    print(
        "\n[FATAL] Missing database files. "
        "Ensure 'food_db.py' and 'pellet_db.py' are in this directory.\n"
    )
    sys.exit(1)


# █████████████████████████████████████████████████████████████████████████████
# ██                                                                         ██
# ██   PHASE 1: STATE INITIALIZATION (The Setup)                             ██
# ██   Before the simulation begins, the engine gathers inputs and           ██
# ██   calculates starting conditions without asking the user for            ██
# ██   complex geometry.                                                     ██
# ██                                                                         ██
# █████████████████████████████████████████████████████████████████████████████

# ─────────────────────────────────────────────────────────────────────────────
# Phase 1, §1: THE IMMOVABLE CONSTANTS (No Magic Numbers)
# ─────────────────────────────────────────────────────────────────────────────
# These values are locked by the PRD and must NEVER be changed during a
# simulation run. They represent the physical laws and stove calibration data.
# ─────────────────────────────────────────────────────────────────────────────

FAN_HIGH: float = 0.78
"""Locked fan rate [kg/hr]. The mechanical pellet feed rate on High Fan.
This is the ONLY fan speed the simulator ever uses (Safe Overestimate Rule)."""

MAX_EFFICIENCY: float = 0.45
"""Maximum thermal transfer efficiency [dimensionless, 0–1].
Baseline empirical value calibrated against WBT data for improved biomass
cookstoves. Represents the theoretical best-case fraction of combustion
energy that reaches the pot."""

K_CONV: float = 10.0
"""Convective heat transfer coefficient [W/m²·K].
Still-air natural convection from the pot surface to the ambient environment.
Source: Standard correlations for heated vertical/horizontal cylinders in
quiescent air (Incropera & DeWitt, 2007)."""

L_V: float = 2257.0
"""Latent heat of vaporization of water [kJ/kg].
Energy required to convert 1 kg of liquid water at 100°C into steam at 100°C.
This is the energy "consumed" by evaporation during the boiling phase."""

dt: float = 1.0
"""Discrete timestep interval [s].
The simulation advances exactly 1 second per iteration of the core loop.
This gives the engine its name: "1Hz Transient Simulator"."""

SIGMA: float = 5.67e-8
"""Stefan-Boltzmann constant [W/m²·K⁴].
Fundamental physical constant governing thermal radiation emission."""

EMISSIVITY: float = 0.3
"""Surface emissivity of the cooking vessel [dimensionless, 0–1].
Approximate value for polished/semi-polished aluminum, the most common
Indian cookware material. Used in the radiation heat loss calculation."""

# ── Derived / Supplementary Constants ────────────────────────────────────────

CP_WATER: float = 4.184
"""Specific heat of liquid water [kJ/kg·K].
Used in the dynamic thermal mass (MCp) calculation every tick. Slightly
higher than the Choi-Okos midpoint value (4.171) to be conservative."""

LID_FACTOR_ON: float = 0.15
"""Evaporation multiplier when the lid is CLOSED [dimensionless].
With a lid on, only ~15% of the open-pot evaporation rate escapes through
gaps around the imperfect seal of a typical Indian cookware lid.
Sources: Brundrett & Poultney (1979); Probert (1987)."""

LID_FACTOR_OFF: float = 1.00
"""Evaporation multiplier when the lid is OPEN [dimensionless].
Full evaporation rate — no lid to trap steam."""

MAX_SIMULATION_TIME: float = 36000.0
"""Maximum allowed simulation time [s] = 10 hours.
If t_elapsed exceeds this value, the loop forcibly breaks to prevent
infinite thermal-equilibrium loops (e.g., when stove power is insufficient
to ever reach boiling for an enormous thermal mass)."""


# =============================================================================
# TERMINAL UI UTILITIES
# =============================================================================
# Clean ANSI-colored styling for the interactive receipt.
# These are purely cosmetic and do not affect physics.
# =============================================================================

def _c(text: str, color_code: str) -> str:
    """Wrap text in ANSI color codes if the terminal supports it."""
    if hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
        return f"{color_code}{text}\033[0m"
    return text

# ANSI escape sequences for terminal colors
CYN = "\033[36m"   # Cyan   — section borders
GRN = "\033[32m"   # Green  — success messages
YLW = "\033[33m"   # Yellow — warnings and prompts
RED = "\033[31m"   # Red    — errors and safety flags
DIM = "\033[2m"    # Dim    — secondary information
BLD = "\033[1m"    # Bold   — emphasis


def _prompt_float(msg: str, default: float, lo: float = 0.0, hi: float = 1e9) -> float:
    """Prompt the user for a floating-point number with validation and a default."""
    while True:
        raw = input(f"\n  >> {_c(msg, BLD)} {_c(f'[{default}]', DIM)} : ").strip()
        if not raw:
            return default
        try:
            val = float(raw)
            if lo <= val <= hi:
                return val
            print(_c(f"  [!] Must be between {lo} and {hi}.", YLW))
        except ValueError:
            print(_c("  [!] Enter a valid number.", YLW))


def _prompt_int(msg: str, default: int, lo: int = 1) -> int:
    """Prompt the user for an integer with validation and a default."""
    while True:
        raw = input(f"\n  >> {_c(msg, BLD)} {_c(f'[{default}]', DIM)} : ").strip()
        if not raw:
            return default
        try:
            val = int(raw)
            if val >= lo:
                return val
            print(_c(f"  [!] Must be ≥ {lo}.", YLW))
        except ValueError:
            print(_c("  [!] Enter a whole number.", YLW))


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1, §2: USER INPUTS & PRE-CALCULATIONS
# ─────────────────────────────────────────────────────────────────────────────
# The engine pulls food/water mass from the database, multiplies by
# Portions, and handles the crucial Plain Water vs. Food logic.
# ─────────────────────────────────────────────────────────────────────────────

def collect_inputs() -> tuple[dict, PelletType]:
    """
    Phase 1, §2 — Collect User Inputs & Perform Database Lookups.

    Walks the user through an interactive menu to select:
        1. Dish (from food_db)
        2. Portions / water volume
        3. Ambient temperature
        4. Pellet type (from pellet_db)
        5. Vessel configuration (mass, specific heat)
        6. Lid state (on/off)
        7. Kinetic cooking time (auto-calculated, user-overridable)

    Returns
    -------
    inp : dict
        Dictionary of all collected and derived input parameters.
    pellet : PelletType
        The selected pellet dataclass for post-processing output.
    """
    print(
        f"\n{_c('=' * 72, CYN)}"
        f"\n{_c('  IIT DELHI | 1Hz Discrete Transient Biomass Cookstove Simulator', BLD)}"
        f"\n{_c('=' * 72, CYN)}"
    )
    inp = {}

    # ── Step 1: Dish Selection ───────────────────────────────────────────────
    # The user picks a dish from the food database.
    # This determines food mass, water mass, Cp, and cooking phases.
    dishes = get_dish_names()
    print(f"\n{_c('  ── Step 1: Dish Selection ──', YLW)}")
    for i, name in enumerate(dishes, 1):
        print(f"    [{i}] {name}")
    d_idx = _prompt_int("Select dish number", 1) - 1
    inp["dish_name"] = dishes[d_idx]
    dish: DishProfile = FOOD_DB[inp["dish_name"]]

    # ── Step 2: Portions & Mass ──────────────────────────────────────────────
    # The engine pulls food/water mass from the database and multiplies
    # by the number of portions.
    #
    # CRUCIAL RULE: If the dish is "Plain Water" (variable_water=True),
    # the user is prompted for total water volume directly, and there are
    # no portions to multiply.
    print(f"\n{_c('  ── Step 2: Portions & Mass ──', YLW)}")
    if dish.variable_water:
        # Plain Water mode: user specifies total litres, no portions.
        inp["water_liters"] = _prompt_float("Total water to boil (Litres)", 5.0)
        inp["portions"] = 1
    else:
        # Food mode: user specifies servings, masses scale linearly.
        inp["portions"] = _prompt_int("Number of people/servings", 2)
    n = inp["portions"]

    # ── Step 3: Ambient Temperature ──────────────────────────────────────────
    # Starting temperature of the pot, water, and food.
    # Default 25°C is the Indian Standard Testing Condition.
    print(f"\n{_c('  ── Step 3: Environment ──', YLW)}")
    inp["t_ambient_c"] = _prompt_float("Ambient temperature (°C)", 25.0)

    # ── Step 4: Pellet Type Selection ────────────────────────────────────────
    # Determines the Gross Calorific Value (GCV) used in Q_in calculation.
    # The conservative (minimum) GCV is always used (Safe Overestimate).
    pellets = get_pellet_names()
    print(f"\n{_c('  ── Step 4: Pellet Type ──', YLW)}")
    for i, name in enumerate(pellets, 1):
        print(f"    [{i}] {name}")
    p_idx = _prompt_int("Select pellet number", 1) - 1
    inp["pellet_name"] = pellets[p_idx]
    pellet: PelletType = PELLET_DB[inp["pellet_name"]]
    inp["gcv_kj_kg"] = pellet.conservative_gcv_kj  # Always use worst-case GCV

    # ── Step 5: Vessel Configuration ─────────────────────────────────────────
    # The pot's empty mass and specific heat contribute to the thermal mass
    # (MCp) calculation. Defaults are for a standard Indian aluminum vessel.
    print(f"\n{_c('  ── Step 5: Vessel Config ──', YLW)}")
    inp["m_pot"] = _prompt_float("Vessel empty mass (kg)", 0.829)
    inp["cp_pot"] = _prompt_float("Vessel specific heat (kJ/kgK)", 0.897)  # Aluminum

    # ── Step 6: Lid State ────────────────────────────────────────────────────
    # The lid factor controls evaporation rate during the boiling phase:
    #   Lid ON  → lid_factor = 0.15 (85% evaporation reduction)
    #   Lid OFF → lid_factor = 1.00 (full evaporation)
    print(f"\n{_c('  ── Step 6: Lid State ──', YLW)}")
    lid = _prompt_int("Lid state: [1] ON (Covered), [2] OFF (Open)", 1)
    inp["lid_factor"] = LID_FACTOR_ON if lid == 1 else LID_FACTOR_OFF
    inp["lid_label"] = "Lid ON" if lid == 1 else "Lid OFF"

    # ── Step 7: Kinetic Cooking Time ─────────────────────────────────────────
    # CRUCIAL RULE from PRD:
    #   • If the dish is "Plain Water", kinetic simmer time = 0.0 s.
    #     Water only needs sensible heating to 100°C — no cooking reaction.
    #   • If it is food, kinetic time is calculated from the database
    #     (frying + boiling + simmering phases).
    #
    # Sub-linear batch scaling (v8): boiling time scales as n^0.5 to reflect
    # the physical reality that cooking-at-temperature is largely batch-
    # independent (only heating time scales linearly with mass).
    print(f"\n{_c('  ── Step 7: Kinetic Time ──', YLW)}")
    if dish.variable_water:
        # ━━ PLAIN WATER PATH ━━
        # Kinetic simmer time is EXACTLY 0.0 seconds.
        # The simulation will heat water to 100°C and immediately stop.
        t_kinetic_base_s = 0.0
        inp["m_food"] = dish.food_mass_per_serving_kg  # Trace solids (0.001 kg)
        inp["m_water_initial"] = inp["water_liters"]   # 1 litre ≈ 1 kg water
    else:
        # ━━ FOOD PATH ━━
        # Sum all cooking phases from the database:
        #   frying_s   — oil-based pre-cook (tadka, sauté, etc.)
        #   boiling_s  — time at boiling temperature (scales sub-linearly)
        #   simmering_s — low-heat finishing phase
        t_boil = dish.phases.boiling_s * (n ** 0.5)  # Sub-linear scaling
        t_kinetic_base_s = (
            float(dish.phases.frying_s)
            + t_boil
            + float(dish.phases.simmering_s)
        )
        inp["m_food"] = dish.food_mass_per_serving_kg * n
        inp["m_water_initial"] = dish.added_water_per_serving_kg * n

    inp["cp_food"] = dish.cp_food_kj_kgk
    t_kinetic_min = t_kinetic_base_s / 60.0

    # Display the physics-derived time and allow the user to override.
    print(_c(f"  Physics-derived kinetic (simmer) time: {t_kinetic_min:.1f} min", DIM))
    t_override = _prompt_float(
        "Total cook/simmer time (minutes) - Enter to accept",
        round(t_kinetic_min, 1),
    )
    inp["t_kinetic_s"] = t_override * 60.0

    return inp, pellet


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1, §2 (cont.): GEOMETRY & GEOMETRIC COUPLING
# ─────────────────────────────────────────────────────────────────────────────
# The engine assumes a standard cylinder (height = diameter) to silently
# reverse-engineer the pot's surface area from the water volume.
# ─────────────────────────────────────────────────────────────────────────────

def setup_geometry_and_zero_state(inp: dict) -> dict:
    """
    Phase 1, §2 — Hidden Geometry, Geometric Coupling, & Zero State.

    This function performs three critical pre-calculations:

    1. HIDDEN GEOMETRY (PRD: "standard cylinder, height = diameter")
       Given the water volume V, solve for the pot diameter d:
           V = π/4 × d² × h,  where h = d  →  V = π/4 × d³
           d = (4V / π)^(1/3)
       Then the total surface area of the cylinder (1 base + side wall):
           A = π/4 × d²  +  π × d × h  =  π/4 × d²  +  π × d²
           A = 1.25 × π × d²

    2. GEOMETRIC COUPLING (η_geom)
       The physical percentage of fire energy the pot captures:
           η_geom = 0.45 × max(0.25, min(1.0, √(Volume_water / 5.0)))
       Small pots capture less flame; very large pots plateau at 100%.
       The 0.25 floor prevents unrealistically low coupling for tiny volumes.

    3. ZERO STATE
       Initialize all dynamic simulation variables to their starting values:
       temperature = ambient, water = initial, timer = kinetic time, etc.

    Parameters
    ----------
    inp : dict
        The input dictionary from collect_inputs().

    Returns
    -------
    inp : dict
        The same dictionary, augmented with geometry and zero-state fields.
    """
    # ── Hidden Geometry ──────────────────────────────────────────────────────
    # Convert water mass (kg) to volume (m³). For water, 1 kg ≈ 1 litre = 0.001 m³.
    V_m3 = inp["m_water_initial"] / 1000.0

    # Solve for the cylinder diameter where height = diameter:
    #   V = (π/4) × d³   →   d = (4V / π)^(1/3)
    d = (4.0 * V_m3 / math.pi) ** (1.0 / 3.0)

    # Total exposed surface area: base + lateral wall (no top — it's open or lidded)
    #   A_base = π/4 × d²
    #   A_side = π × d × h = π × d × d = π × d²
    #   A_total = (π/4 + π) × d² = 1.25 × π × d²
    A = 1.25 * math.pi * (d ** 2)

    # ── Geometric Coupling (η_geom) ─────────────────────────────────────────
    # η_geom represents what fraction of the stove's combustion energy
    # actually reaches the pot. It depends on the pot size relative to the
    # flame spread:
    #
    #   η_geom = MAX_EFFICIENCY × max(0.25, min(1.0, √(V_water / 5.0)))
    #
    # • V_water = m_water_initial (kg ≈ litres for water)
    # • √(V/5) maps 5 litres → 1.0 (full capture), 1.25 litres → 0.5, etc.
    # • The max(0.25, ...) floor prevents coupling from dropping below 25%
    #   for very small pots (e.g., a single cup of tea).
    # • The min(1.0, ...) ceiling caps coupling at 100% for large pots.
    eta_geom = MAX_EFFICIENCY * max(
        0.25,
        min(1.0, math.sqrt(inp["m_water_initial"] / 5.0))
    )

    # ── Zero State Initialization ────────────────────────────────────────────
    # Set all dynamic variables to their starting values before the 1Hz loop.
    inp.update({
        "V_m3": V_m3,                              # Water volume [m³]
        "d_m": d,                                   # Pot diameter [m]
        "A_m2": A,                                  # Pot surface area [m²]
        "eta_geom": eta_geom,                       # Geometric coupling [0–1]
        "t_elapsed_s": 0.0,                         # Elapsed simulation time [s]
        "T_pot_c": inp["t_ambient_c"],              # Pot temperature [°C] = ambient
        "m_water_current": inp["m_water_initial"],  # Current water mass [kg]
        "t_kinetic_remaining": inp["t_kinetic_s"],  # Remaining kinetic timer [s]
        "flag_dry_boil": False,                     # Safety: did the pot boil dry?
        "flag_overheat": False,                     # Safety: did temp exceed 150°C?
        "tick_log": [],                             # Telemetry log [(min, °C, g, s)]
    })
    return inp


# █████████████████████████████████████████████████████████████████████████████
# ██                                                                         ██
# ██   PHASE 2: THE 1Hz TRANSIENT LOOP (The Core Engine)                     ██
# ██   This while loop steps forward exactly 1 second per iteration.         ██
# ██   It represents the physical progression of time and stops when         ██
# ██   the kinetic timer hits zero (or the 10-hour safety break fires).      ██
# ██                                                                         ██
# █████████████████████████████████████████████████████████████████████████████

def run_1hz_loop(inp: dict) -> dict:
    """
    Phase 2 — The 1Hz Discrete Transient Physics Loop.

    This is the heart of the simulator. Each iteration of the while loop
    represents exactly 1 second of real time. The loop performs five steps
    per tick (Steps 2A through 2E) and terminates when:
        • The pot has reached ≥100°C AND the kinetic timer has counted down
          to zero, OR
        • The 10-hour safety break fires (infinite loop protection).

    The loop enforces strict energy conservation: if the pot reaches 100°C
    mid-tick, the remaining energy in that second cascades into evaporation.

    Parameters
    ----------
    inp : dict
        The fully initialized state dictionary from setup_geometry_and_zero_state().

    Returns
    -------
    inp : dict
        The state dictionary updated with final simulation values.
    """
    print(f"\n{_c('  [Executing 1Hz Transient Loop...]', DIM)}")

    # ── Unpack state variables for tight-loop performance ────────────────────
    # These are read from the dictionary once and written back at the end
    # to avoid dict-lookup overhead on every tick.
    m_food   = inp["m_food"]       # Total food mass [kg]
    cp_food  = inp["cp_food"]      # Food specific heat [kJ/kg·K]
    m_pot    = inp["m_pot"]        # Pot empty mass [kg]
    cp_pot   = inp["cp_pot"]       # Pot specific heat [kJ/kg·K]
    A        = inp["A_m2"]         # Pot surface area [m²]
    eta_geom = inp["eta_geom"]     # Geometric coupling efficiency [0–1]
    gcv      = inp["gcv_kj_kg"]    # Pellet gross calorific value [kJ/kg]
    lid_fac  = inp["lid_factor"]   # Evaporation lid factor [0–1]
    T_amb    = inp["t_ambient_c"]  # Ambient temperature [°C]

    T_pot    = inp["T_pot_c"]              # Current pot temperature [°C]
    m_water  = inp["m_water_current"]      # Current water mass [kg]
    t_elapsed = inp["t_elapsed_s"]         # Elapsed time [s]
    t_kin_rem = inp["t_kinetic_remaining"] # Remaining kinetic timer [s]

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2A: POWER IN (Q_in)
    # ─────────────────────────────────────────────────────────────────────────
    # Because of the "Safe Overestimate" rule, the stove is LOCKED on High Fan.
    # Power is constant for the entire simulation — calculated once outside
    # the loop.
    #
    #   Power = (FAN_HIGH / 3600) × GCV × η_geom   [kW]
    #
    # FAN_HIGH is in kg/hr, so dividing by 3600 converts to kg/s.
    # Multiplying by GCV (kJ/kg) gives kW (kJ/s).
    # η_geom scales this to the fraction actually absorbed by the pot.
    #
    #   Q_in = Power × dt   [kJ]
    #
    # Since dt = 1.0 s, Q_in numerically equals Power in kW.
    # ─────────────────────────────────────────────────────────────────────────
    P_in_kw = (FAN_HIGH / 3600.0) * gcv * eta_geom  # Thermal power input [kW]
    Q_in = P_in_kw * dt                              # Energy input per tick [kJ]

    tick_count = 0  # Counter for sparse telemetry logging

    # ═══════════════════════════════════════════════════════════════════════════
    # THE MAIN WHILE LOOP
    # Continues while:
    #   1. The pot hasn't reached 100°C yet (still in sensible heating), OR
    #   2. The kinetic timer hasn't expired (still needs to cook at temperature).
    # ═══════════════════════════════════════════════════════════════════════════
    while (T_pot < 100.0) or (t_kin_rem > 0):

        # ─────────────────────────────────────────────────────────────────────
        # INFINITE LOOP PROTECTION (Safety Break)
        # PRD: "If t_elapsed exceeds 10 hours, the loop forcibly breaks
        # to prevent infinite thermal equilibrium loops."
        #
        # This fires when the stove simply cannot overcome heat losses to
        # reach boiling — e.g., an enormous pot in a freezing environment.
        # ─────────────────────────────────────────────────────────────────────
        if t_elapsed > MAX_SIMULATION_TIME:
            print(_c(
                "\n  [!] THERMAL EQUILIBRIUM WARNING: "
                "Vessel cannot reach boiling point.", RED
            ))
            print(_c(
                "      Stove lacks power for this thermal mass/surface area.", RED
            ))
            break

        # ─────────────────────────────────────────────────────────────────────
        # STEP 2B: DYNAMIC THERMAL MASS (MCp)
        # ─────────────────────────────────────────────────────────────────────
        # Because water evaporates, the engine recalculates the physical
        # weight of the pot EVERY SINGLE SECOND.
        #
        #   MCp_total = (m_food × Cp_food) + (m_water × Cp_water) + (m_pot × Cp_pot)
        #
        # Units: kJ/K — the total energy required to raise the entire
        # system (food + water + pot) by 1 Kelvin.
        # ─────────────────────────────────────────────────────────────────────
        MCp_total = (m_food * cp_food) + (m_water * CP_WATER) + (m_pot * cp_pot)

        # ─────────────────────────────────────────────────────────────────────
        # STEP 2C: HEAT BLEED (Q_out)
        # ─────────────────────────────────────────────────────────────────────
        # The pot loses heat to the environment through two mechanisms:
        #   1. Convection — warm air rising from the pot surface
        #   2. Radiation  — electromagnetic emission (Stefan-Boltzmann law)
        #
        # Temperatures MUST be converted to Kelvin (K) to satisfy radiation
        # laws (T^4 requires absolute temperature).
        # ─────────────────────────────────────────────────────────────────────

        # Convert Celsius → Kelvin for both pot and ambient temperatures
        T_pot_K = T_pot + 273.15
        T_amb_K = T_amb + 273.15

        # Convective heat loss [W]:
        #   P_conv = k_conv × A × (T_pot_K − T_amb_K)
        P_conv = K_CONV * A * (T_pot_K - T_amb_K)

        # Radiative heat loss [W]:
        #   P_rad = ε × σ × A × (T_pot_K⁴ − T_amb_K⁴)
        P_rad = EMISSIVITY * SIGMA * A * (T_pot_K ** 4 - T_amb_K ** 4)

        # Total heat bleed per tick [kJ]:
        #   Q_out = (P_conv + P_rad) / 1000 × dt
        # Division by 1000 converts W → kW, then × dt gives kJ.
        Q_out = ((P_conv + P_rad) / 1000.0) * dt

        # ─────────────────────────────────────────────────────────────────────
        # STEP 2D: NET ENERGY ROUTING (Energy Conservation)
        # ─────────────────────────────────────────────────────────────────────
        # Subtract heat bleed from heat applied:
        #   Q_avail = Q_in − Q_out
        #
        # The available energy is then routed through a cascade of three
        # possible paths. Energy conservation is strictly enforced —
        # if the pot hits 100°C mid-tick, leftover energy transitions
        # into evaporation within the SAME second.
        # ─────────────────────────────────────────────────────────────────────
        Q_avail = Q_in - Q_out

        if Q_avail <= 0.0:
            # ── COOLING SCENARIO ─────────────────────────────────────────────
            # Heat losses exceed heat input. The pot cools down.
            # ΔT = Q_avail / MCp (negative, so temperature drops).
            T_pot += (Q_avail / MCp_total) if MCp_total > 0 else 0
        else:
            # ── HEATING SCENARIO ─────────────────────────────────────────────
            # Net energy is positive. Route through the cascade:

            # ┌─────────────────────────────────────────────────────────────┐
            # │ ROUTE A: Sensible Heating (T_pot < 100°C)                  │
            # │ Temperature rises toward boiling point.                    │
            # │   ΔT = Q_avail / MCp_total                                │
            # │   T_pot = T_pot + ΔT                                      │
            # │                                                            │
            # │ ENERGY CONSERVATION: If Q_avail would push T_pot past      │
            # │ 100°C, we calculate the exact energy needed to reach 100°C │
            # │ and pass the remainder to Route B (evaporation).           │
            # └─────────────────────────────────────────────────────────────┘
            if T_pot < 100.0:
                # Energy needed to reach exactly 100°C from current temp:
                Q_to_100 = MCp_total * (100.0 - T_pot)

                if Q_avail <= Q_to_100:
                    # Not enough energy to reach boiling — all goes to heating.
                    T_pot += (Q_avail / MCp_total)
                    Q_avail = 0.0  # Fully consumed
                else:
                    # Enough energy to reach boiling — clamp at 100°C and
                    # cascade the surplus into evaporation (Route B).
                    T_pot = 100.0
                    Q_avail -= Q_to_100  # Surplus energy for evaporation

            # ┌─────────────────────────────────────────────────────────────┐
            # │ ROUTE B: Boiling & Evaporation (T_pot ≥ 100°C, water > 0) │
            # │ Temperature is locked at 100°C.                            │
            # │ Available energy goes into evaporating water:              │
            # │   m_evap = (Q_avail / L_v) × Lid_Factor                   │
            # │   m_water = m_water − m_evap                              │
            # └─────────────────────────────────────────────────────────────┘
            if T_pot >= 100.0 and Q_avail > 0 and m_water > 0:
                # Calculate mass of water that can be evaporated:
                m_evap_potential = (Q_avail / L_V) * lid_fac

                if m_evap_potential <= m_water:
                    # Normal evaporation — some water remains.
                    m_water -= m_evap_potential
                    Q_avail = 0.0  # Fully consumed by evaporation
                else:
                    # All remaining water evaporates. Calculate the energy
                    # that was actually used, and cascade the rest to Route C.
                    #
                    # m_water (kg) of evaporation requires:
                    #   Q_boil = (m_water / lid_fac) × L_v
                    # (Dividing by lid_fac inverts the evaporation scaling
                    #  to get the raw energy consumed.)
                    Q_boil = (m_water / lid_fac) * L_V
                    m_water = 0.0
                    Q_avail -= Q_boil  # Remaining energy cascades to Route C

            # ┌─────────────────────────────────────────────────────────────┐
            # │ ROUTE C: Dry-Boil Runaway (m_water ≤ 0)                   │
            # │ Water is gone. The 100°C lock breaks.                     │
            # │ The pot temperature rises unconstrained:                  │
            # │   ΔT = Q_avail / (m_food × Cp_food + m_pot × Cp_pot)     │
            # │   T_pot = T_pot + ΔT                                      │
            # └─────────────────────────────────────────────────────────────┘
            if Q_avail > 0 and m_water <= 0:
                inp["flag_dry_boil"] = True  # Flag for safety diagnostics
                MCp_dry = (m_food * cp_food) + (m_pot * cp_pot)
                T_pot += (Q_avail / MCp_dry) if MCp_dry > 0 else 0

        # ── Overheat Safety Check ────────────────────────────────────────────
        # If the pot temperature exceeds 150°C, flag as critically overheated.
        # This indicates burnt food and potential vessel damage.
        if T_pot > 150.0:
            inp["flag_overheat"] = True

        # ─────────────────────────────────────────────────────────────────────
        # STEP 2E: ADVANCE CLOCK & TIMER HYSTERESIS
        # ─────────────────────────────────────────────────────────────────────
        # Advance the simulation clock by exactly 1 second:
        #   t_elapsed = t_elapsed + dt
        #
        # Timer Hysteresis (99°C threshold):
        #   The kinetic timer only ticks down when T_pot ≥ 99°C.
        #   The 1°C hysteresis below boiling prevents "numerical stuttering"
        #   where the timer would start/stop rapidly as temperature oscillates
        #   around exactly 100°C due to evaporative cooling.
        # ─────────────────────────────────────────────────────────────────────
        t_elapsed += dt

        if T_pot >= 99.0:
            t_kin_rem -= dt

        # ── Sparse Telemetry Logging ─────────────────────────────────────────
        # Log state every 60 ticks (1 minute) and at the final tick.
        # This keeps the log manageable while still capturing the trajectory.
        tick_count += 1
        if tick_count % 60 == 0 or t_kin_rem <= 0:
            inp["tick_log"].append((
                t_elapsed / 60.0,     # Time [min]
                T_pot,                # Temperature [°C]
                m_water * 1000,       # Water remaining [g]
                t_kin_rem,            # Kinetic timer remaining [s]
            ))

    # ── Save final simulation state back to the dictionary ───────────────────
    inp.update({
        "T_pot_c": T_pot,
        "m_water_current": m_water,
        "t_elapsed_s": t_elapsed,
        "P_in_kw": P_in_kw,
    })
    return inp


# █████████████████████████████████████████████████████████████████████████████
# ██                                                                         ██
# ██   PHASE 3: FINAL OUTPUT & DIAGNOSTICS                                   ██
# ██   The loop terminates. The engine extracts final variables to            ██
# ██   generate the receipt.                                                  ██
# ██                                                                         ██
# █████████████████████████████████████████████████████████████████████████████

def post_process_and_print(inp: dict, pellet: PelletType):
    """
    Phase 3 — Final Output & Diagnostics.

    Generates three output sections:

    1. ULTIMATE PELLET CALCULATION (The Recommendation):
       Because the math is safely overestimated based on the locked High Fan:
           Total_Pellets_Required = (t_elapsed / 3600) × 0.78 × 1000  [grams]

    2. SAFETY DIAGNOSTICS:
       Checks for dry-boil and overheat conditions flagged during the loop.

    3. ACADEMIC 3-PHASE TIMELINE (UI Post-Processing):
       The final t_elapsed is cosmetically sliced for the receipt:
           Phase 1 (Ignition):    First 15% of total time
           Phase 2 (Steady State): Middle 65% of total time
           Phase 3 (Char/Coals):  Final 20% of total time
       This does NOT alter the raw fuel physics — it is purely illustrative.

    Parameters
    ----------
    inp : dict
        The final state dictionary from run_1hz_loop().
    pellet : PelletType
        The selected pellet type, for display in the output.
    """
    t_elapsed = inp["t_elapsed_s"]

    # ─────────────────────────────────────────────────────────────────────────
    # §1: ULTIMATE PELLET CALCULATION
    # ─────────────────────────────────────────────────────────────────────────
    # Total_Pellets_Required = (t_elapsed / 3600) × FAN_HIGH × 1000  [grams]
    #
    # Derivation:
    #   t_elapsed [s] / 3600 → hours of burn time
    #   × FAN_HIGH [kg/hr]  → total kg of pellets consumed
    #   × 1000              → convert kg → grams
    #
    # This is the SAFE UPPER BOUND. The stove was assumed to run on High Fan
    # for the entire duration. Actual consumption will be ≤ this value.
    # ─────────────────────────────────────────────────────────────────────────
    pellets_g = (t_elapsed / 3600.0) * FAN_HIGH * 1000.0

    # ── Energy Summary Banner ────────────────────────────────────────────────
    print(f"\n{_c('=' * 72, CYN)}")
    print(_c("  SIMULATION RESULTS", BLD))
    print(_c('=' * 72, CYN))

    print(f"\n{_c('  +── ENERGY SUMMARY ───────────────────────────────+', DIM)}")
    print(f"  | Total simulation time : {t_elapsed:.0f} s ({t_elapsed / 60:.2f} min)")
    print(f"  | Stove power (P_in)    : {inp['P_in_kw']:.4f} kW (Constant - High Fan)")
    print(f"  | Water remaining       : {inp['m_water_current'] * 1000:.1f} g")
    print(f"{_c('  +─────────────────────────────────────────────────+', DIM)}")

    # ─────────────────────────────────────────────────────────────────────────
    # §2: SAFETY DIAGNOSTICS
    # ─────────────────────────────────────────────────────────────────────────
    # Check for dry-boil (all water evaporated) and overheat (T > 150°C)
    # conditions that were flagged during the 1Hz loop.
    # ─────────────────────────────────────────────────────────────────────────
    if inp["flag_dry_boil"] or inp["flag_overheat"]:
        print(f"\n{_c('  +── SAFETY DIAGNOSTICS ────────────────────────────+', RED)}")
        if inp["flag_dry_boil"]:
            print(_c("  | [FATAL] DRY-BOIL: Pot boiled dry. Food burnt.", RED))
        if inp["flag_overheat"]:
            print(_c(
                "  | [CRITICAL] OVERHEAT: Vessel temp exceeded 150°C safe limits.", RED
            ))
        print(f"{_c('  +─────────────────────────────────────────────────+', RED)}")
    else:
        print(f"\n{_c('  ✓ Safety Diagnostics: All clear (No dry-boil or overheat).', GRN)}")

    # ─────────────────────────────────────────────────────────────────────────
    # §3: ACADEMIC 3-PHASE COMBUSTION TIMELINE (UI Post-Processing)
    # ─────────────────────────────────────────────────────────────────────────
    # To satisfy the academic requirement without altering the raw fuel
    # physics, the final t_elapsed is cosmetically sliced for the receipt:
    #
    #   Phase 1 (Ignition):     First  15% of total time
    #   Phase 2 (Steady State): Middle 65% of total time
    #   Phase 3 (Char/Coals):   Final  20% of total time
    #
    # These percentages are arbitrary UI conventions and do NOT feed back
    # into any energy calculation.
    # ─────────────────────────────────────────────────────────────────────────
    t_min = t_elapsed / 60.0
    p1 = 0.15 * t_min  # Phase 1: Ignition     [minutes]
    p2 = 0.65 * t_min  # Phase 2: Steady State [minutes]
    p3 = 0.20 * t_min  # Phase 3: Char/Coals   [minutes]

    print(f"\n{_c('  +── ACADEMIC 3-PHASE COMBUSTION TIMELINE ─────────+', CYN)}")
    print(_c(
        "  | DISCLAIMER: Illustrative timeline only. Not used in governing physics.",
        DIM,
    ))
    print(f"  | Phase 1 (Ignition) : 0.0 → {p1:.1f} min")
    print(_c(
        "  |   Stove reaching operating temperature. Expect initial smoke.", DIM
    ))
    print(f"  | Phase 2 (Steady)   : {p1:.1f} → {p1 + p2:.1f} min")
    print(_c(
        "  |   Optimal clean combustion and rapid boiling.", DIM
    ))
    print(f"  | Phase 3 (Char)     : {p1 + p2:.1f} → {t_min:.1f} min")
    print(_c(
        "  |   Fresh wood exhausted. Simmer finishing on highly efficient radiant char.",
        DIM,
    ))
    print(f"{_c('  +─────────────────────────────────────────────────+', CYN)}")

    # ── Final Pellet Recommendation Display ──────────────────────────────────
    print(f"\n{_c('=' * 72, YLW)}")
    print(_c("  RECOMMENDED PELLET LOAD", BLD))
    print(f"  Formula: (t_elapsed / 3600) × FAN_HIGH × 1000")
    print(f"  Pellets: ({t_elapsed:.0f} / 3600) × {FAN_HIGH} × 1000")
    print(f"\n  ► {_c(f'{pellets_g:.1f} g', BLD)}  [{pellet.name}]")
    print(_c("=" * 72, YLW))
    print()


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """
    Top-level controller. Runs the three-phase simulation in a loop,
    allowing the user to perform multiple calculations without restarting.
    """
    while True:
        # Phase 1: State Initialization
        inp, pellet = collect_inputs()
        inp = setup_geometry_and_zero_state(inp)

        # Phase 2: 1Hz Transient Loop
        inp = run_1hz_loop(inp)

        # Phase 3: Final Output & Diagnostics
        post_process_and_print(inp, pellet)

        # Prompt for another simulation run
        if input("  >> Run another simulation? (y/n): ").strip().lower() != 'y':
            break


if __name__ == "__main__":
    main()