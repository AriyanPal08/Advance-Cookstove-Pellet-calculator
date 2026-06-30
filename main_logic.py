"""
main_logic.py
1Hz Discrete Transient Biomass Cookstove Simulator  — Version 3
IIT Delhi · Department of Energy Studies

=============================================================================
CHANGE LOG  v2 → v3
=============================================================================
1. WIND FACTOR / DYNAMIC CONVECTION COEFFICIENT (NEW)
   K_CONV_STILL_AIR removed from the top-level immovable constants. It is
   replaced by inp["k_conv_current"], set once per session from a 4-option
   menu (Indoors/Still Air, Outdoors Low/Medium/High Wind). This value is
   then used everywhere the convection coefficient previously appeared:
   both in the Total Time Estimator's average heat-bleed calculation and
   in the live 1Hz loop's Step 2C convection term. No other physics term
   is touched — this is a single coefficient substitution.

2. VESSEL MASS OVERRIDE (NEW)
   The utensil selection step still performs a silent DB lookup for
   cp_pot, but m_pot is now an editable field: the database default mass
   is shown, and the user may press Enter to accept it or type a precise
   override value. inp["m_pot"] holds whichever value is used downstream.

3. TOTAL TIME ESTIMATOR (UPDATED — transient heat-up integration)
   P_conv now reads inp["k_conv_current"] (v3).  t_heat_s is computed by
   a 1 Hz transient ramp that mirrors the live loop's Step 2C + Route B
   (T < 100 °C) so temperature-dependent convection and T⁴ radiation are
   captured.  t_suggested_total_s adds a 60–120 s safety buffer.

4. 1Hz LOOP — STEP 2C (UPDATED — convection term only)
   P_conv reads inp["k_conv_current"] instead of K_CONV_STILL_AIR.
   Step 2D (Net Energy & State Routing — Routes A, B, B2/B3) is
   BYTE-FOR-BYTE UNCHANGED from v2. No route, threshold, or formula in
   the energy-routing cascade has been touched.

5. RECEIPT (UPDATED)
   The chosen Wind Factor / environment label and its k_conv value are
   added to the "SIMULATION INPUTS" section of the printed receipt.

Everything else (dish/food_db lookups, pellet_db lookups, lid factor,
geometry reverse-engineering, loop termination condition, MAX_SIMULATION_TIME
safety break, §6A/§6B/§6C outputs) is unchanged from v2.

Core Directive (unchanged): The stove runs at constant FAN_HIGH (0.78 kg/hr)
for the entire simulation. No PID controllers, no random wind gusts, no
dynamic efficiency penalties, no variable fan speed are introduced anywhere
in this file.

=============================================================================
SOURCES
=============================================================================
[1] MacCarty et al. (2010). Energy Sustain. Dev., 14(3), 214-222.
[2] NIST WebBook — Aluminium thermophysical properties.
[3] Incropera et al. (2007). Fundamentals of Heat and Mass Transfer, 7th ed.
    [Table 7.x: representative convection coefficients used for the wind
    factor tiers — still air ≈10 W/m²K; low/medium/high forced convection
    ranges ≈20-50 W/m²K for cylinders in cross-flow.]
[4] WBT v4.2.3 (2017). Clean Cooking Alliance. [Lid factor reference]
[5] Choi & Okos (1986); ICMR-NIN (2017). [food_db.py Cp_food sourcing]
"""

from __future__ import annotations

import math
import sys
import datetime
from pathlib import Path

from food_db    import FOOD_DB, DishProfile, get_dish_names
from pellet_db  import PELLET_DB, PelletType, get_pellet_names
from utensil_db import UTENSIL_DB, Utensil, get_utensil_names, get_utensil

# =============================================================================
# SECTION 3 — IMMOVABLE PHYSICAL CONSTANTS  (unchanged from v1)
# =============================================================================

FAN_HIGH:    float = 0.78     # kg/hr  — high-fan mechanical feed rate
MAX_EFFICIENCY: float = 0.45  # —       maximum combustion efficiency
L_V:         float = 2257.0   # kJ/kg  — latent heat of vaporisation at 100°C
SIGMA:       float = 5.67e-8  # W/m²·K⁴ — Stefan-Boltzmann constant
dt:          float = 1.0      # s      — simulation time step (1 Hz)
EMISSIVITY:  float = 0.3      # —       vessel surface emissivity
# Note: K_CONV_STILL_AIR is REMOVED from the hardcoded constants in v3.
# It is now set dynamically per-session as inp["k_conv_current"] from the
# Wind Factor menu below (still air = 10.0 W/m²K is preserved as option [1]).

# Additional sourced constants
CP_WATER:    float = 4.184    # kJ/kg·K — specific heat of water (NIST, ~60°C)

# Wind Factor tiers — convection coefficient h (W/m²·K)  [source: 3]
# Selected once per session into inp["k_conv_current"]; used in both the
# Total Time Estimator and the live 1Hz loop's Step 2C convection term.
WIND_TIERS: dict[str, float] = {
    "Indoors / Still Air":        10.0,
    "Outdoors (Low Wind)":        20.0,
    "Outdoors (Medium Wind)":     35.0,
    "Outdoors (High Wind)":       50.0,
}

# Safety thresholds
T_OVERHEAT_C: float = 150.0   # °C — critical vessel overheat threshold
M_WATER_DRY:  float = 0.0     # kg — dry-boil threshold

# Lid factors  [WBT v4.2.3, source: 4]
LID_FACTOR_ON:  float = 0.15
LID_FACTOR_OFF: float = 1.00

# Loop safety cap (prevents infinite loop on pathological inputs)
MAX_SIMULATION_TIME: float = 6 * 3600.0  # 6 hours in seconds

# =============================================================================
# TERMINAL COLOUR HELPERS
# =============================================================================

_ANSI = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

def _c(text: str, *codes: str) -> str:
    return ("".join(codes) + text + "\033[0m") if _ANSI else text

RST = "\033[0m"; BLD = "\033[1m"; DIM = "\033[2m"
CYN = "\033[36m"; GRN = "\033[32m"; YLW = "\033[33m"
RED = "\033[31m"; BLU = "\033[34m"; ORG = "\033[38;5;214m"; WHT = "\033[97m"

def _hdr(title: str) -> None:
    print()
    print(_c("=" * 72, CYN, BLD))
    print(_c(f"  {title}", BLD, WHT))
    print(_c("=" * 72, CYN, BLD))

def _sec(title: str) -> None:
    print()
    print(_c(f"  ── {title} ──", BLD, YLW))
    print(_c("─" * 72, DIM))

def _warn(msg: str) -> None:
    print(_c(f"\n  [!]  {msg}", YLW))

def _prompt(msg: str, default: str | None = None) -> str:
    suffix = _c(f" [{default}]", DIM) if default is not None else ""
    try:
        raw = input(_c(f"\n  >>  {msg}", BLD, BLU) + suffix + _c(" : ", BLD, BLU)).strip()
    except EOFError:
        raw = ""
    return raw if (raw != "" or default is None) else default

def _prompt_float(msg: str, default: float, lo: float = 0.0, hi: float = 1e9) -> float:
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

def _prompt_int(msg: str, default: int, lo: int = 1) -> int:
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

def _menu(title: str, options: list[str]) -> int:
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


# =============================================================================
# PHASE 1 — STATE INITIALIZATION (The Setup)
# =============================================================================

def collect_inputs() -> dict:
    """
    Phase 1: collect dish, utensil, pellet, ambient temperature, and the
    unified Total Cooking Time (via the new Total Time Estimator).
    """
    _hdr("IIT DELHI  |  1Hz Transient Biomass Cookstove Simulator  |  v3")
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

    n: int = inp["portions"]

    # ── Database lookups: food mass/water/Cp + base kinetic time ─────────────
    # "If variable_water is True, t_kinetic_base_s MUST equal 0.0"
    if dish.variable_water:
        inp["m_food"]          = dish.food_mass_per_serving_kg     # trace solids
        inp["cp_food"]         = dish.cp_food_kj_kgk
        inp["m_water_initial"] = inp["water_liters"]               # 1 L ≈ 1 kg
        inp["t_kinetic_base_s"] = 0.0
    else:
        inp["m_food"]          = dish.food_mass_per_serving_kg    * n
        inp["cp_food"]         = dish.cp_food_kj_kgk
        inp["m_water_initial"] = dish.added_water_per_serving_kg  * n
        inp["t_kinetic_base_s"] = float(dish.phases.total_s)

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
    u_idx = _menu("Step 5 / 7  —  Utensil Selection", utensil_names)
    utensil: Utensil = get_utensil(utensil_names[u_idx])
    inp["utensil_name"] = utensil.name
    inp["cp_pot"]        = utensil.cp_kj_kgk   # silent assignment (unchanged)
    inp["is_pc"]         = utensil.is_pressure

    # ── Vessel Mass Override  (NEW) ───────────────────────────────────────────
    # Database default mass is shown; user may accept it or type a precise
    # measured value for their actual vessel.
    inp["m_pot"] = _prompt_float(
        f"Press Enter to accept [{utensil.mass_kg}] kg, "
        f"or type a precise vessel mass (kg)",
        default=utensil.mass_kg, lo=0.0, hi=50.0
    )

    # ── Lid state ──────────────────────────────────────────────────────────────
    if inp["is_pc"]:
        inp["lid_label"]  = "ON (Pressure Cooker — sealed)"
        inp["lid_factor"] = 0.0
    else:
        lid_idx = _menu("Lid State", ["Lid ON (covered)", "Lid OFF (open)"])
        if lid_idx == 0:
            inp["lid_label"]  = "Lid ON"
            inp["lid_factor"] = LID_FACTOR_ON
        else:
            inp["lid_label"]  = "Lid OFF"
            inp["lid_factor"] = LID_FACTOR_OFF

    # ── Geometry: reverse-engineer pot diameter, A_m2, eta_geom ──────────────
    m_w = inp["m_water_initial"]
    V_m3 = m_w / 1000.0
    d    = (4.0 * V_m3 / math.pi) ** (1.0 / 3.0)
    A    = 1.25 * math.pi * d ** 2
    eta_geom = MAX_EFFICIENCY * max(0.25, min(1.0, math.sqrt(m_w / 5.0)))
    inp.update({"V_m3": V_m3, "d_m": d, "A_m2": A, "eta_geom": eta_geom})

    # ── Step 7: Total Time Estimator  (transient heat-up integration) ────────
    _sec("Step 7 / 7  —  Total Cooking Time (Heating + Simmering)")

    P_in_kw = (FAN_HIGH / 3600.0) * inp["gcv_kj_kg"] * eta_geom
    MCp_total = (inp["m_food"] * inp["cp_food"]
                 + m_w * CP_WATER
                 + inp["m_pot"] * inp["cp_pot"])

    T_amb = inp["t_ambient_c"]
    T_amb_K = T_amb + 273.15
    k_conv = inp["k_conv_current"]

    # Transient heat-up integration — mirrors 1 Hz loop Steps 2C + Route B
    # (T < 100 °C).  Heat bleed grows with vessel temperature (convection
    # ∝ ΔT, radiation ∝ T⁴), so a single average-temperature estimate
    # mis-predicts the ramp; stepping at 1 Hz matches the live solver.
    T_pot_est = T_amb
    t_heat_s = 0.0
    Q_out_accum_kw_s = 0.0
    heat_cannot_rise = False

    while T_pot_est < 100.0 and t_heat_s < MAX_SIMULATION_TIME:
        T_pot_K = T_pot_est + 273.15
        P_conv = k_conv * A * (T_pot_K - T_amb_K)
        P_rad  = EMISSIVITY * SIGMA * A * (T_pot_K**4 - T_amb_K**4)
        Q_out_kw = (P_conv + P_rad) / 1000.0
        Q_avail = P_in_kw * dt - Q_out_kw * dt

        if Q_avail <= 0.0:
            heat_cannot_rise = True
            break

        Q_to_100 = MCp_total * (100.0 - T_pot_est)
        if Q_avail <= Q_to_100:
            T_pot_est += Q_avail / MCp_total
        else:
            T_pot_est = 100.0

        t_heat_s += dt
        Q_out_accum_kw_s += Q_out_kw * dt

    if heat_cannot_rise or T_pot_est < 100.0:
        t_heat_s = 0.0
        Q_out_accum_kw_s = 0.0
        _warn(
            "Stove input power does not exceed heat loss during heat-up; "
            "heat-up time estimate defaulted to 0 s. Total time will rely on "
            "kinetic time only — review pellet/utensil selection."
        )

    Q_out_avg_kw = (Q_out_accum_kw_s / t_heat_s) if t_heat_s > 0.0 else 0.0

    # Post heat-up safety margin (60–120 s) for discrete-step lag and
    # brief post-boil transients before kinetic simmering stabilises.
    t_safety_buffer_s = min(120.0, max(60.0, 60.0 + 0.03 * t_heat_s))
    t_suggested_total_s   = t_heat_s + inp["t_kinetic_base_s"] + t_safety_buffer_s
    t_suggested_total_min = t_suggested_total_s / 60.0

    print(_c(f"\n  Estimated heat-up time     : {t_heat_s/60:.1f} min", DIM))
    print(_c(f"  Dish kinetic time (base×n) : {inp['t_kinetic_base_s']/60:.1f} min", DIM))
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

    # Diagnostics carried into the receipt
    inp["P_in_kw"]        = P_in_kw
    inp["MCp_total_init"] = MCp_total
    inp["Q_out_avg_kw"]   = Q_out_avg_kw
    inp["t_heat_est_s"]   = t_heat_s

    return inp


# =============================================================================
# ZERO STATE  (Phase 1 continued)
# =============================================================================

def zero_state(inp: dict) -> dict:
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


# =============================================================================
# PHASE 2 — 1Hz TRANSIENT LOOP (The Core Engine)
# =============================================================================

def run_1hz_loop(inp: dict) -> dict:
    """
    Phase 2: Execute the 1Hz transient loop.

    Loop condition (UPDATED): while t_elapsed < inp["t_total_s"].
    No t_kinetic_remaining, no 99°C hysteresis gate.

    Physics cascade (Steps 2A-2D) is UNCHANGED / PROTECTED — identical to
    the previously verified Route A / Route B / Route B2 / Route B3 logic.
    """
    m_food:   float = inp["m_food"]
    cp_food:  float = inp["cp_food"]
    m_pot:    float = inp["m_pot"]
    cp_pot:   float = inp["cp_pot"]
    A:        float = inp["A_m2"]
    eta_geom: float = inp["eta_geom"]
    gcv:      float = inp["gcv_kj_kg"]
    lid_fac:  float = inp["lid_factor"]
    T_amb:    float = inp["t_ambient_c"]
    T_amb_K:  float = T_amb + 273.15
    t_total_s: float = inp["t_total_s"]
    k_conv:   float = inp["k_conv_current"]   # NEW v3 — dynamic wind factor

    # Step 2A: Power In — constant for the entire run (high-fan rule)
    P_in_kw: float = (FAN_HIGH / 3600.0) * gcv * eta_geom

    T_pot:           float       = inp["T_pot_c"]
    m_water:         float       = inp["m_water_current"]
    t_elapsed:       float       = inp["t_elapsed_s"]
    flag_dry:        bool        = False
    flag_over:       bool        = False
    t_boil_reached:  float | None = None

    log_interval = 60
    tick_log: list = []
    tick = 0

    # ── LOOP CONDITION (UPDATED): strictly absolute-time based ────────────────
    while t_elapsed < t_total_s:

        # Step 2A: Power In
        Q_in = P_in_kw * dt

        # Step 2B: Dynamic Mass (UNCHANGED)
        MCp_total = (m_food * cp_food) + (m_water * CP_WATER) + (m_pot * cp_pot)

        # Step 2C: Heat Bleed (convection term UPDATED to dynamic Wind Factor;
        #          radiation term UNCHANGED)
        T_pot_K = T_pot + 273.15
        P_conv  = k_conv * A * (T_pot_K - T_amb_K)
        P_rad   = EMISSIVITY * SIGMA * A * (T_pot_K**4 - T_amb_K**4)
        Q_out   = ((P_conv + P_rad) / 1000.0) * dt

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

        # ── Advance Clock (UPDATED): no hysteresis gate ────────────────────────
        t_elapsed += dt

        # Safety break (NEW — prevents infinite loop on pathological input)
        if t_elapsed > MAX_SIMULATION_TIME:
            _warn(
                f"MAX_SIMULATION_TIME ({MAX_SIMULATION_TIME/3600:.1f} h) exceeded — "
                f"loop terminated early for safety."
            )
            break

        # Safety flags
        if m_water <= M_WATER_DRY and not flag_dry:
            flag_dry = True
        if T_pot > T_OVERHEAT_C and not flag_over:
            flag_over = True

        # Sparse telemetry log
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
    })
    return inp


# =============================================================================
# PHASE 3 — FINAL OUTPUT & DIAGNOSTICS  (UNCHANGED)
# =============================================================================

def post_process(inp: dict) -> dict:
    """
    §6A: Ultimate fuel output (unchanged formula).
    §6C: Academic 3-phase receipt slicing (unchanged 15/65/20 split).
    """
    t_elapsed = inp["t_elapsed_s"]

    pellets_g = (t_elapsed / 3600.0) * FAN_HIGH * 1000.0
    inp["pellets_required_g"]  = pellets_g
    inp["pellets_required_kg"] = pellets_g / 1000.0

    inp["t_phase1_s"] = 0.15 * t_elapsed
    inp["t_phase2_s"] = 0.65 * t_elapsed
    inp["t_phase3_s"] = 0.20 * t_elapsed

    return inp


# =============================================================================
# RECEIPT PRINTER
# =============================================================================

def _bar(fraction: float, width: int = 28) -> str:
    filled = int(min(max(fraction, 0.0), 1.0) * width)
    return "|" + "█" * filled + "░" * (width - filled) + "|"


def print_receipt(inp: dict) -> None:
    now_str   = datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    t_el      = inp["t_elapsed_s"]
    t_el_min  = t_el / 60.0
    pellet    = inp["pellet"]
    pellets_g = inp["pellets_required_g"]
    q_in_total = inp["P_in_kw"] * t_el

    def box(label: str, val: str, unit: str = "", col: str = CYN) -> None:
        u   = f" {unit}" if unit else ""
        v   = f"{val}{u}"
        pad = max(0, 62 - len(label) - len(v))
        print(_c(f"  | {label}", col) + _c(v, GRN, BLD) + _c(" " * pad + "|", col))

    def div(col: str = CYN) -> None:
        print(_c("  +" + "─" * 66 + "+", col))

    def title(t: str, col: str = CYN) -> None:
        print(_c(f"\n  +── {t} " + "─" * max(2, 60 - len(t)) + "+", col, BLD))

    print()
    print(_c("=" * 72, CYN, BLD))
    print(_c("  IIT DELHI  |  1Hz Transient Biomass Cookstove Simulator  |  v3", BLD, WHT))
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
    box("Lid state",            inp["lid_label"])
    box("Pellet",                pellet.name)
    box("GCV (conservative)",   f"{pellet.conservative_gcv_kj:,.1f}", "kJ/kg")
    div()

    title("TOTAL TIME ESTIMATOR  (new in v2)")
    box("Estimated heat-up time",  f"{inp['t_heat_est_s']/60:.1f}", "min")
    box("Dish kinetic base time",  f"{inp['t_kinetic_base_s']/60:.1f}", "min")
    box("Suggested total",         f"{(inp['t_heat_est_s']+inp['t_kinetic_base_s'])/60:.1f}", "min")
    box("User-selected total",     f"{inp['t_total_min_user']:.1f}", "min", col=GRN)
    box("Q_out_avg (at T_avg)",    f"{inp['Q_out_avg_kw']*1000:.2f}", "W")
    div()

    title("DERIVED GEOMETRY  (cylinder h=d)")
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
    box("Total energy supplied", f"{q_in_total:.2f}", "kJ")
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
    print(_c("  Formula:  Pellets = (t_elapsed / 3600) × FAN_HIGH × 1000", DIM))
    print(_c(f"            Pellets = ({t_el:.0f} / 3600) × {FAN_HIGH} × 1000", DIM))
    print(_c("  " + "─" * 60, ORG))
    print(_c(f"  ►  {mass_str:<20} ◄", ORG, BLD) + _c(f"  [{pellet.name}]", DIM))
    print(_c("  " + "─" * 60, ORG))
    print(_c("  ► Add ≥ 10% safety margin for real-world procurement.", DIM))
    print(_c("  ► Simulation used HIGH FAN (0.78 kg/hr) throughout — conservative.", DIM))
    print(_c("=" * 72, ORG, BLD))
    print()


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

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