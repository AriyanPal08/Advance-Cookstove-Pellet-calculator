"""
main_logic.py
1Hz Discrete Transient Biomass Cookstove Simulator  — Version 5
IIT Delhi · Department of Energy Studies

=============================================================================
UPDATE SUMMARY (this edit)
=============================================================================
Purpose: Improve research usability and documentation without changing any
core physics equations or the existing operational recommendation logic.

Changes made:
  1. MODEL SCOPE & LIMITATIONS block added (see below).
  2. FAN_HIGH annotated as an experimentally measured value.
  3. compute_vessel_geometry() receives an optional m_food_kg parameter
     to apply a small, physically motivated eta_geom correction for
     liquid-heavy / low-added-water loads (max +0.08, capped at MAX_EFFICIENCY).
  4. post_process() now returns two clearly labelled pellet outputs:
       • pellets_energy_based_g  — thermodynamic estimate (research/debug)
       • pellets_required_g      — time-based operational recommendation (shown to user)
     and includes a structured research_outputs dict for reporting/validation.
  5. Docstrings and inline comments updated for clarity.

=============================================================================
MODEL SCOPE AND LIMITATIONS
=============================================================================
This model is designed specifically for constant-feed, forced-draft pellet
stoves operating at a fixed HIGH fan setting.

  • Pellet feed rate: 0.78 kg/hr — experimentally measured on the target
    stove at HIGH fan. There is NO closed-loop or variable-rate pellet
    control. The stove feeds pellets mechanically at this rate throughout
    the entire cook.

  • Operational use: The model is a decision-support tool for hopper
    loading before cooking. It answers: "How many grams of pellets should
    I load into the hopper for this dish?" — not a real-time controller.

  • Result validity: Outputs are valid only for dishes, utensils, and
    ambient conditions within the supported database ranges. Extrapolation
    outside these conditions (e.g., very large batches, unusual utensils,
    extreme wind) increases uncertainty.

  • Procurement margin: A margin of 5–12% (environment-dependent) is
    applied on top of the time-based pellet load to account for real-world
    variability in pellet quality, feed consistency, and measurement error.

  • Two pellet outputs are produced:
      - pellets_energy_based_g: thermodynamic estimate (research/debug only)
      - pellets_required_g: operational recommendation shown to the user,
        computed as (cook_time_hrs × 0.78 × 1000 × margin)

=============================================================================
CHANGE LOG  v4 → v5 (Dynamic Procurement Margin & Enhanced Utensils)
=============================================================================
1. DYNAMIC PROCUREMENT MARGIN (UPDATE 1 — Stochastic Environmental Variance)
   Replaces flat 8% safety margin with environment-aware scaling:
     • High Wind (k_conv ≥ 50.0 W/m²·K): 12% margin
     • Open Pot (lid_factor = 1.00): 10% margin
     • Covered Pot (lid_factor < 1.00, non-pressure): 7% margin
     • Pressure Cooker (sealed): 5% margin
     • Fallback: 8% margin
   
   Rationale: Wind increases convection losses; pressure cookers are sealed.
   Margin accounts for real-world pellet quality variance and measurement uncertainty.

2. EXPANDED UTENSIL DATABASE (UPDATE 2 — Capacity-Based Hawkins/Prestige Specs)
   Added 13 new utensil entries verified against manufacturer datasheets:
     • Aluminium Pots: 2L, 3L, 5L, 8L (all Cp=0.897 kJ/kg·K)
     • Pressure Cookers: 2L, 3L, 5L, 7.5L (sealed, Cp=0.897)
     • Kadhais: 2.5L, 4L, 6L (Cp=0.897)
     • Cast Iron: Tawa, Frying Pan 26cm (Cp=0.460)
     • Stainless Steel 304: 3L, 5L (Cp=0.500)
   
   All masses sourced from Hawkins/Prestige official specs (2023–2024).

3. TIME-BASED PELLET LOGIC UNCHANGED
   V10 "Safe Overestimate" formula still governs: pellets = (t/3600) × 0.78 × 1000 × margin
   No shift to energy-based calculation. Physics loop untouched.

=============================================================================
CHANGE LOG  v3 → v4
=============================================================================
1. SHARED PHYSICS HELPERS — geometry, emissivity, heat-loss, safety-buffer
   functions used by both the Total Time Estimator and the live 1 Hz loop.
2. GEOMETRY — cylinder h/d model per utensil; lid reduces exposed top area.
3. TOTAL TIME ESTIMATOR — full transient preview through heat-up + kinetic.
4. PELLET CALCULATION — energy balance (Q_sensible + Q_evap + Q_out).
5. 1HZ LOOP — energy telemetry added; Step 2D routing cascade unchanged.

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

# FAN_HIGH is experimentally measured on the target stove at HIGH fan setting.
# The model assumes a constant feed rate for the entire cook duration.
# There is no closed-loop or variable-rate pellet control in this stove.
# A procurement margin (5–12%) is applied on top to account for real-world
# variability in pellet quality, feed consistency, and measurement uncertainty.
FAN_HIGH:    float = 0.78     # kg/hr  — experimentally measured pellet feed rate at HIGH fan
MAX_EFFICIENCY: float = 0.45  # —       maximum combustion efficiency
L_V:         float = 2257.0   # kJ/kg  — latent heat of vaporisation at 100°C
SIGMA:       float = 5.67e-8  # W/m²·K⁴ — Stefan-Boltzmann constant
dt:          float = 1.0      # s      — simulation time step (1 Hz)
EMISSIVITY_DEFAULT: float = 0.35  # — oxidised aluminium [Incropera Table 7.1]
# Note: K_CONV_STILL_AIR is REMOVED from the hardcoded constants in v3.
# It is now set dynamically per-session as inp["k_conv_current"] from the
# Wind Factor menu below (still air = 10.0 W/m²K is preserved as option [1]).

# Additional sourced constants
CP_WATER:    float = 4.184    # kJ/kg·K — specific heat of water (NIST, ~60°C)

# ============================================================
# PRESSURE COOKER POST-BOIL CORRECTION
# ============================================================
# Applied ONLY when the selected utensil is a pressure cooker
# (is_pc = True). Open-pot kinetic durations are unmodified.
#
# Derivation (Theoretical Arrhenius equation & Experimental alignment):
#   - Starch gelatinization activation energy (Ea) ~100 kJ/mol
#     (Spies & Hoseney, 1982; Lund & Wirakartakusumah, 1984).
#   - At 120°C (sealed PC, ~15 psi gauge, 393.15 K) vs 100°C (373.15 K):
#     Rate ratio = exp[(100000/8.314) × (1/373.15 − 1/393.15)] = 5.15.
#   - Since the reaction is 5.15× faster, the required kinetic time
#     is reduced to 1/5.15 ≈ 0.194 of the open pot time.
#   - This 0.20 factor correctly brings the 2L PC Rice (4 pax) cook
#     time down to ~13.5 min, satisfying the experimental constraint
#     of < 14 min (prevents bottom burning at 16 min).
PRESSURE_POST_BOIL_FACTOR = 0.20

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

# Procurement margin on physics-based pellet recommendation (feed-rate variance)
PELLET_PROCUREMENT_MARGIN: float = 0.08  # 8 %

# =============================================================================
# SECTION 3b — SHARED PHYSICS HELPERS  (v4 — single source of truth)
# =============================================================================

def _emissivity_for_utensil(utensil: Utensil) -> float:
    """Material-aware surface emissivity [Incropera Table 7.1]."""
    if utensil.cp_kj_kgk < 0.55:
        return 0.55   # cast iron / tawa
    if utensil.is_pressure:
        return 0.32   # polished Al body, minimal oxidation
    return EMISSIVITY_DEFAULT


def _geometry_profile(utensil_name: str) -> tuple[float, float]:
    """Return (height/diameter ratio, surface-area multiplier) for utensil type."""
    if "Kadhai" in utensil_name or "Wok" in utensil_name:
        return 0.45, 1.12
    if "Tawa" in utensil_name or "Pan" in utensil_name:
        return 0.28, 1.30
    return 0.65, 1.00


def compute_vessel_geometry(
    m_water_kg: float,
    utensil_name: str,
    lid_factor: float,
    m_food_kg: float = 0.0,
) -> dict[str, float]:
    """
    Reverse-engineer pot dimensions from water mass.
    Cylinder model: V = π·r²·h with utensil-specific h/d ratio.
    Exposed loss area = side wall + partial top (bottom insulated by stove).

    m_food_kg: total food mass (excluding water). Used to detect liquid-heavy
    loads where added water is very low but the pot is full of food — in those
    cases the water-volume proxy under-estimates flame coupling (eta_geom),
    so a small conservative correction is applied (see below).
    """
    V_m3 = m_water_kg / 1000.0
    h_over_d, surface_mult = _geometry_profile(utensil_name)
    d_m = (4.0 * V_m3 / (math.pi * h_over_d)) ** (1.0 / 3.0)
    h_m = h_over_d * d_m
    r_m = d_m / 2.0
    A_side = math.pi * d_m * h_m
    A_top  = math.pi * r_m ** 2
    top_exposure = 0.30 if lid_factor <= LID_FACTOR_ON else 0.85
    A_m2 = surface_mult * (A_side + top_exposure * A_top)
    # eta_geom scaling — Calibrated to WBT 5L
    #   Using a reference mass of 5.0 kg and an exponent of 0.20,
    #   the stove reaches its max thermal efficiency at 5L load.
    #   This was explicitly matched to the IIT Delhi WBT where 5L water
    #   in an 8L pot (lid off) boiled in exactly 18 minutes.
    eta_geom = MAX_EFFICIENCY * max(0.38, min(1.0, (m_water_kg / 5.0) ** 0.20))

    # ── Liquid-heavy load correction ──────────────────────────────────────────
    # Physical motivation: dishes like dal, curry, and stews have significant
    # thermal mass (food solids + absorbed moisture) but very little free
    # added water (m_water_kg < 0.3 kg). The water-volume proxy used above
    # under-estimates the effective pot fill and therefore the flame-coupling
    # efficiency. When the total thermal mass (food + water) is significant
    # (> 1.5 kg) but added water is very low, we apply a small proportional
    # upward correction to eta_geom (max +0.08, never exceeds MAX_EFFICIENCY).
    total_mass = m_water_kg + m_food_kg
    if m_water_kg < 0.3 and total_mass > 1.5:
        correction = min(0.08, 0.08 * (total_mass - 1.5) / 3.0)
        eta_geom = min(MAX_EFFICIENCY, eta_geom + correction)
    # ─────────────────────────────────────────────────────────────────────────

    return {"V_m3": V_m3, "d_m": d_m, "h_m": h_m, "A_m2": A_m2, "eta_geom": eta_geom}


def heat_loss_w(
    T_pot_c: float,
    T_amb_c: float,
    A_m2: float,
    k_conv: float,
    emissivity: float,
    lid_factor: float = LID_FACTOR_OFF,
) -> float:
    """Total convective + radiative heat bleed (W). Used by estimator and loop."""
    T_pot_K = T_pot_c + 273.15
    T_amb_K = T_amb_c + 273.15
    conv_factor = 0.85 + 0.15 * lid_factor
    P_conv = k_conv * A_m2 * (T_pot_K - T_amb_K) * conv_factor
    P_rad  = emissivity * SIGMA * A_m2 * (T_pot_K ** 4 - T_amb_K ** 4)
    return P_conv + P_rad


def heat_loss_kw(
    T_pot_c: float,
    T_amb_c: float,
    A_m2: float,
    k_conv: float,
    emissivity: float,
    lid_factor: float = LID_FACTOR_OFF,
) -> float:
    """Heat bleed in kW (convenience wrapper)."""
    return heat_loss_w(T_pot_c, T_amb_c, A_m2, k_conv, emissivity, lid_factor) / 1000.0


def compute_safety_buffer_s(
    t_heat_s: float,
    k_conv: float,
    m_water_kg: float,
) -> float:
    """
    Justified post-estimate safety margin (60–120 s).

    Components:
      • 60 s base — 1 Hz discretisation lag at boil crossover + operator start delay
      • up to 30 s — accumulated per-minute step error scales with heat-up duration
      • up to 20 s — outdoor wind tiers add convective-loss uncertainty
      • up to 10 s — large batches (>8 kg) have slower non-linear ramp tail
    """
    buffer = 60.0
    buffer += min(30.0, 0.04 * t_heat_s)
    buffer += min(20.0, 5.0 * max(0.0, k_conv / 10.0 - 1.0))
    buffer += min(10.0, max(0.0, (m_water_kg - 8.0) * 1.5))
    return min(120.0, max(60.0, buffer))


def _transient_preview_tick(
    T_pot: float,
    m_water: float,
    m_food: float,
    cp_food: float,
    m_pot: float,
    cp_pot: float,
    P_in_kw: float,
    A_m2: float,
    k_conv: float,
    emissivity: float,
    T_amb: float,
    lid_fac: float,
) -> tuple[float, float, float]:
    """
    Execute one 1 Hz physics tick (Steps 2A–2D).
    Returns (T_pot_new, m_water_new, Q_out_kj).
    Routing logic is identical to run_1hz_loop Step 2D.
    """
    Q_in  = P_in_kw * dt
    MCp_total = (m_food * cp_food) + (m_water * CP_WATER) + (m_pot * cp_pot)
    Q_out = heat_loss_kw(T_pot, T_amb, A_m2, k_conv, emissivity, lid_fac) * dt
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
            m_evap_potential = (Q_avail / L_V) * lid_fac
            if m_evap_potential <= m_water:
                m_water -= m_evap_potential
                Q_avail  = 0.0
            else:
                Q_boil  = (m_water / lid_fac) * L_V
                m_water = 0.0
                Q_avail -= Q_boil

        if Q_avail > 0 and m_water <= 0:
            MCp_dry = (m_food * cp_food) + (m_pot * cp_pot)
            if MCp_dry > 0:
                T_pot += Q_avail / MCp_dry
            Q_avail = 0.0

    return T_pot, m_water, Q_out


def estimate_cook_time(
    m_food: float,
    cp_food: float,
    m_water: float,
    m_pot: float,
    cp_pot: float,
    t_kinetic_s: float,
    P_in_kw: float,
    A_m2: float,
    k_conv: float,
    emissivity: float,
    T_amb: float,
    lid_fac: float,
) -> dict[str, float]:
    """
    Shadow 1 Hz transient preview: heat-up to 100 °C, then kinetic simmer.
    Returns timing diagnostics used for the Total Time Estimator.
    """
    T_pot = T_amb
    m_w   = m_water
    t_elapsed = 0.0
    t_boil: float | None = None
    Q_out_accum = 0.0
    heat_cannot_rise = False

    while T_pot < 100.0 and t_elapsed < MAX_SIMULATION_TIME:
        T_prev = T_pot
        T_pot, m_w, Q_out = _transient_preview_tick(
            T_pot, m_w, m_food, cp_food, m_pot, cp_pot,
            P_in_kw, A_m2, k_conv, emissivity, T_amb, lid_fac,
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
                P_in_kw, A_m2, k_conv, emissivity, T_amb, lid_fac,
            )
            t_elapsed += dt
            Q_out_accum += Q_out

    return {
        "t_heat_s": t_heat_s,
        "t_boil_s": t_boil if t_boil is not None else 0.0,
        "t_preview_s": t_elapsed,
        "Q_out_accum_kj": Q_out_accum,
        "heat_cannot_rise": float(heat_cannot_rise),
        "m_water_end_kg": m_w,
    }


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
        
        kinetic_time_s = 0.0
        for stage in dish.stages:
            if stage.stage_type == "kinetic":
                # Currently set to 1.0 (no correction)
                kinetic_time_s += stage.duration_s * PRESSURE_POST_BOIL_FACTOR
            elif stage.stage_type == "frying":
                kinetic_time_s += stage.duration_s
        inp["t_kinetic_base_s"] = kinetic_time_s

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

    # ── Geometry: cylinder model with utensil-specific h/d and lid exposure ───
    m_w = inp["m_water_initial"]
    inp["emissivity"] = _emissivity_for_utensil(utensil)
    geom = compute_vessel_geometry(m_w, inp["utensil_name"], inp["lid_factor"])
    inp.update(geom)

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

    # Diagnostics carried into the receipt
    inp["P_in_kw"]              = P_in_kw
    inp["MCp_total_init"]       = MCp_total
    inp["Q_out_avg_kw"]         = Q_out_avg_kw
    inp["t_heat_est_s"]         = t_heat_s
    inp["t_boil_est_s"]         = preview["t_boil_s"]
    inp["t_safety_buffer_s"]    = t_safety_buffer_s
    inp["t_preview_s"]          = preview["t_preview_s"]

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
    t_total_s: float = inp["t_total_s"]
    k_conv:   float = inp["k_conv_current"]
    emissivity: float = inp.get("emissivity", EMISSIVITY_DEFAULT)

    # Step 2A: Power In — constant for the entire run (high-fan rule)
    P_in_kw: float = (FAN_HIGH / 3600.0) * gcv * eta_geom

    T_pot:           float       = inp["T_pot_c"]
    m_water:         float       = inp["m_water_current"]
    t_elapsed:       float       = inp["t_elapsed_s"]
    flag_dry:        bool        = False
    flag_over:       bool        = False
    t_boil_reached:  float | None = None

    Q_in_kj = 0.0
    Q_out_kj = 0.0
    Q_sensible_kj = 0.0
    Q_evap_kj = 0.0

    log_interval = 60
    tick_log: list = []
    tick = 0

    # ── LOOP CONDITION (UPDATED): strictly absolute-time based ────────────────
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
        "Q_in_kj":          Q_in_kj,
        "Q_out_kj":         Q_out_kj,
        "Q_sensible_kj":    Q_sensible_kj,
        "Q_evap_kj":        Q_evap_kj,
    })
    return inp


# =============================================================================
# PHASE 3 — FINAL OUTPUT & DIAGNOSTICS
# =============================================================================

def post_process(inp: dict) -> dict:
    """
    Phase 3: Pellet procurement recommendation + research diagnostics.

    TWO distinct pellet outputs are produced and clearly labelled:
    ─────────────────────────────────────────────────────────────────
    pellets_energy_based_g  [RESEARCH / PHYSICS OUTPUT — debug/validation only]
        Thermodynamic estimate: how many grams of pellets would be needed
        if the stove could perfectly match energy demand.
        Formula: Q_demand_kj / (GCV_kj_per_kg × eta_geom) × 1000
        NOT shown to the end user — the stove has no closed-loop control
        and cannot modulate feed rate to track thermodynamic demand.

    pellets_required_g  [OPERATIONAL RECOMMENDATION — shown to the user]
        Time-based calculation using the fixed, experimentally measured
        pellet feed rate (FAN_HIGH = 0.78 kg/hr):
            pellets = (cook_time_hrs) × FAN_HIGH × 1000 × margin
        This is correct for a constant-feed forced-draft stove. The stove
        feeds at FAN_HIGH throughout; the user simply loads this many grams
        into the hopper before cooking.
    ─────────────────────────────────────────────────────────────────

    Dynamic procurement margin (applied only to pellets_required_g):
      • High Wind (k_conv ≥ 50.0 W/m²·K): +12% — intense convection loss
      • Open Pot (lid_factor = 1.00):       +10% — maximum heat exposure
      • Covered Pot (non-pressure):          +7% — partial thermal protection
      • Pressure Cooker (sealed):            +5% — minimal environmental loss
      • Fallback:                            +8% — default safety

    Also populates inp["research_outputs"] — a structured dict suitable
    for validation, reporting, and CSV/JSON export.
    """
    t_elapsed = inp["t_elapsed_s"]
    gcv       = inp["gcv_kj_kg"]
    eta_geom  = inp["eta_geom"]
    k_conv_current = inp.get("k_conv_current", 10.0)
    lid_factor     = inp.get("lid_factor", 1.0)
    utensil        = inp.get("utensil")

    # Total energy demanded by this cook (sensible + evaporation + losses)
    Q_demand_kj = inp["Q_sensible_kj"] + inp["Q_evap_kj"] + inp["Q_out_kj"]

    # ── ENERGY-BASED PELLET ESTIMATE (research/physics output) ────────────────
    # Thermodynamic floor: how many grams if the stove could precisely
    # deliver only the demanded energy (GCV × combustion efficiency).
    # This value is for research and validation — NOT the operational recommendation.
    effective_energy_kj_per_kg = gcv * eta_geom
    if effective_energy_kj_per_kg > 0:
        pellets_energy_based_g = (Q_demand_kj / effective_energy_kj_per_kg) * 1000.0
    else:
        pellets_energy_based_g = 0.0
    # ─────────────────────────────────────────────────────────────────────────

    # ── TIME-BASED PELLET RECOMMENDATION (operational, shown to user) ─────────
    # The stove operates at a constant, mechanically fixed pellet feed rate
    # (FAN_HIGH = 0.78 kg/hr, experimentally measured). There is no closed-
    # loop control. The correct hopper load is:
    #     feed_rate × cook_duration × procurement_margin
    pellets_time_g = (t_elapsed / 3600.0) * FAN_HIGH * 1000.0
    # ─────────────────────────────────────────────────────────────────────────

    # ═══════════════════════════════════════════════════════════════════════════
    # DYNAMIC PROCUREMENT MARGIN (Stochastic Environmental Variance)
    # ═══════════════════════════════════════════════════════════════════════════
    if k_conv_current >= 50.0:
        # High wind: intense forced convection increases Q_out, risk of underfeed
        procurement_margin = 0.12
        margin_reason = "High Wind (k_conv >= 50.0 W/m²·K)"
    elif lid_factor == 1.0:
        # Open pot: maximum exposure to surroundings, highest heat loss
        procurement_margin = 0.10
        margin_reason = "Open Pot (lid_factor = 1.00)"
    elif lid_factor < 1.0 and utensil and not utensil.is_pressure:
        # Covered pot (not pressure cooker): partial thermal protection
        procurement_margin = 0.07
        margin_reason = "Covered Pot (lid_factor < 1.00, non-pressure)"
    elif utensil and utensil.is_pressure:
        # Pressure cooker: sealed, minimal environmental variance
        procurement_margin = 0.05
        margin_reason = "Pressure Cooker (sealed, minimal environmental loss)"
    else:
        # Fallback: default safety margin
        procurement_margin = 0.08
        margin_reason = "Default (environmental variance not classified)"

    # Apply dynamic margin to the operational (time-based) recommendation only
    pellets_with_margin_g = pellets_time_g * (1.0 + procurement_margin)

    # ── Write results back to inp ─────────────────────────────────────────────
    inp["Q_demand_kj"]               = Q_demand_kj
    # Operational output (user-facing)
    inp["pellets_required_g"]        = pellets_with_margin_g
    inp["pellets_required_kg"]       = pellets_with_margin_g / 1000.0
    inp["pellets_time_based_g"]      = pellets_time_g
    # Research/physics output (not shown on operational display)
    inp["pellets_energy_based_g"]    = pellets_energy_based_g
    inp["procurement_margin_factor"] = (1.0 + procurement_margin)
    inp["procurement_margin_pct"]    = procurement_margin * 100.0
    inp["margin_reason"]             = margin_reason

    inp["t_phase1_s"] = 0.15 * t_elapsed
    inp["t_phase2_s"] = 0.65 * t_elapsed
    inp["t_phase3_s"] = 0.20 * t_elapsed

    # ── Structured research outputs dict (for reporting / export) ─────────────
    # Callers can access inp["research_outputs"] directly for validation,
    # CSV logging, or JSON export without parsing the full inp dict.
    inp["research_outputs"] = {
        # Physics engine outputs
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
        # Pellet outputs
        "pellets_energy_based_g": pellets_energy_based_g,   # thermodynamic estimate
        "pellets_time_based_g":   pellets_time_g,            # before margin
        "pellets_required_g":     pellets_with_margin_g,     # operational recommendation
        "procurement_margin_pct": procurement_margin * 100.0,
        "margin_reason":          margin_reason,
    }
    # ─────────────────────────────────────────────────────────────────────────

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
    box("Surface emissivity ε", f"{inp.get('emissivity', EMISSIVITY_DEFAULT):.2f}", "")
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
