# =============================================================================
# hardware/main_logic.py — MicroPython Port (ESP32)
# 1Hz Discrete Transient Biomass Cookstove Simulator
# IIT Delhi - Department of Energy Studies
#
# ALL PHYSICS FUNCTIONS AND CONSTANTS PRESERVED BYTE-FOR-BYTE.
# Terminal UI (ANSI codes, prompts, menus, print_receipt) REMOVED.
# Only pure computation functions remain for hardware/main.py to call.
#
# SOURCES:
# [1] MacCarty et al. (2010). Energy Sustain. Dev., 14(3), 214-222.
# [2] NIST WebBook — Aluminium thermophysical properties.
# [3] Incropera et al. (2007). Fundamentals of Heat and Mass Transfer, 7e.
# [4] WBT v4.2.3 (2017). Clean Cooking Alliance.
# [5] Choi & Okos (1986); ICMR-NIN (2017).
# =============================================================================
#
# ── MODEL SCOPE ──────────────────────────────────────────────────────────────
# This model is designed for constant-feed, forced-draft pellet stoves
# operating at a fixed HIGH fan setting. There is no closed-loop pellet
# control: the feed rate is mechanically fixed. The model serves as a
# decision-support tool for hopper loading — it tells the user how many
# grams of pellets to load before cooking, not during.
# ─────────────────────────────────────────────────────────────────────────────

import math

from food_db    import FOOD_DB, DishProfile, get_dish_names
from pellet_db  import PELLET_DB, PelletType, get_pellet_names
from utensil_db import UTENSIL_DB, Utensil, get_utensil_names, get_utensil

# =============================================================================
# SECTION 3 — IMMOVABLE PHYSICAL CONSTANTS  (unchanged from v1)
# =============================================================================

# FAN_HIGH is experimentally measured on the target stove at HIGH fan
# setting. The model assumes this feed rate is constant for the entire
# cook — there is no closed-loop or variable-rate pellet control.
FAN_HIGH         = 0.78      # kg/hr — experimentally measured pellet feed rate at HIGH fan
MAX_EFFICIENCY   = 0.45      # — maximum combustion efficiency
L_V              = 2257.0    # kJ/kg — latent heat of vaporisation at 100 C
SIGMA            = 5.67e-8   # W/m2-K4 — Stefan-Boltzmann constant
dt               = 1.0       # s — simulation time step (1 Hz)
EMISSIVITY_DEFAULT = 0.35    # — oxidised aluminium [Incropera Table 7.1]

CP_WATER         = 4.184     # kJ/kg-K — specific heat of water (NIST, ~60 C)

# Wind Factor tiers — convection coefficient h (W/m2-K)  [source: 3]
WIND_TIERS = {
    "Indoors / Still Air":        10.0,
    "Outdoors (Low Wind)":        20.0,
    "Outdoors (Medium Wind)":     35.0,
    "Outdoors (High Wind)":       50.0,
}

# Safety thresholds
T_OVERHEAT_C     = 150.0     # C — critical vessel overheat threshold
M_WATER_DRY      = 0.0       # kg — dry-boil threshold

# Lid factors  [WBT v4.2.3, source: 4]
LID_FACTOR_ON    = 0.15
LID_FACTOR_OFF   = 1.00

# Loop safety cap (prevents infinite loop on pathological inputs)
MAX_SIMULATION_TIME = 6 * 3600.0  # 6 hours in seconds

# Procurement margin on physics-based pellet recommendation
PELLET_PROCUREMENT_MARGIN = 0.08  # 8 %


# =============================================================================
# SECTION 3b — SHARED PHYSICS HELPERS
# =============================================================================

def _emissivity_for_utensil(utensil):
    """Material-aware surface emissivity [Incropera Table 7.1]."""
    if utensil.cp_kj_kgk < 0.55:
        return 0.55   # cast iron / tawa
    if utensil.is_pressure:
        return 0.32   # polished Al body, minimal oxidation
    return EMISSIVITY_DEFAULT


def _geometry_profile(utensil_name):
    """Return (height/diameter ratio, surface-area multiplier) for utensil type."""
    if "Kadhai" in utensil_name or "Wok" in utensil_name:
        return (0.45, 1.12)
    if "Tawa" in utensil_name or "Pan" in utensil_name:
        return (0.28, 1.30)
    return (0.65, 1.00)


def compute_vessel_geometry(m_water_kg, utensil_name, lid_factor, m_food_kg=0.0):
    """
    Reverse-engineer pot dimensions from water mass.
    Cylinder model: V = pi*r^2*h with utensil-specific h/d ratio.
    Exposed loss area = side wall + partial top (bottom insulated by stove).

    m_food_kg: total food mass (excluding water). Used to detect liquid-heavy
    loads where added water is low but the pot is full — in those cases the
    flame coupling (eta_geom) is slightly under-estimated by the water-volume
    proxy, so a small conservative correction is applied.
    """
    V_m3 = m_water_kg / 1000.0
    h_over_d, surface_mult = _geometry_profile(utensil_name)
    d_m = (4.0 * V_m3 / (math.pi * h_over_d)) ** (1.0 / 3.0)
    h_m = h_over_d * d_m
    r_m = d_m / 2.0
    A_side = math.pi * d_m * h_m
    A_top  = math.pi * r_m ** 2
    if lid_factor <= LID_FACTOR_ON:
        top_exposure = 0.30
    else:
        top_exposure = 0.85
    A_m2 = surface_mult * (A_side + top_exposure * A_top)
    # eta_geom scaling -- ORIGINAL formula (reference mass 5.0 kg, exponent 0.35):
    #   eta_geom = MAX_EFFICIENCY * max(0.38, min(1.0, (m_water_kg / 5.0) ** 0.35))
    # Problem: the formula caps at MAX_EFFICIENCY exactly at 5.0 kg. For a 5-litre
    # load in an 8L pot the pot is only 62% full, yet eta_geom hits its ceiling
    # while A_m2 (heat loss area) grows with volume -- making the model overly
    # pessimistic for large-volume cooks.
    #
    # FIX: raise the reference mass to 8.0 kg (the largest common pot in the DB)
    # and soften the exponent to 0.30. This spreads the scaling across the full
    # realistic range so that eta_geom only reaches MAX_EFFICIENCY when the pot
    # is truly full (~8 kg water). For small masses (1-3 kg) the new formula
    # gives a slightly lower (more conservative) value than the old one, so
    # small-dish estimates are not made optimistic -- they are unchanged or safer.
    eta_geom = MAX_EFFICIENCY * max(0.38, min(1.0, (m_water_kg / 8.0) ** 0.30))

    # ── Liquid-heavy load correction ─────────────────────────────────────────
    # When added water is very low (<0.3 kg) but total thermal mass is
    # significant (food + water > 1.5 kg), the pot is likely full of
    # liquid-heavy food (e.g. dal, curry). The water-volume proxy under-
    # estimates flame coupling, so we apply a small upward correction
    # (max +0.08, capped at MAX_EFFICIENCY) to eta_geom.
    total_mass = m_water_kg + m_food_kg
    if m_water_kg < 0.3 and total_mass > 1.5:
        correction = min(0.08, 0.08 * (total_mass - 1.5) / 3.0)
        eta_geom = min(MAX_EFFICIENCY, eta_geom + correction)
    # ─────────────────────────────────────────────────────────────────────────

    return {"V_m3": V_m3, "d_m": d_m, "h_m": h_m, "A_m2": A_m2, "eta_geom": eta_geom}


def heat_loss_w(T_pot_c, T_amb_c, A_m2, k_conv, emissivity,
                lid_factor=1.00):
    """Total convective + radiative heat bleed (W). Used by estimator and loop."""
    T_pot_K = T_pot_c + 273.15
    T_amb_K = T_amb_c + 273.15
    conv_factor = 0.85 + 0.15 * lid_factor
    P_conv = k_conv * A_m2 * (T_pot_K - T_amb_K) * conv_factor
    P_rad  = emissivity * SIGMA * A_m2 * (T_pot_K ** 4 - T_amb_K ** 4)
    return P_conv + P_rad


def heat_loss_kw(T_pot_c, T_amb_c, A_m2, k_conv, emissivity,
                 lid_factor=1.00):
    """Heat bleed in kW (convenience wrapper)."""
    return heat_loss_w(T_pot_c, T_amb_c, A_m2, k_conv, emissivity, lid_factor) / 1000.0


def compute_safety_buffer_s(t_heat_s, k_conv, m_water_kg):
    """
    Justified post-estimate safety margin (60-120 s).
    Components:
      60 s base — 1 Hz discretisation lag
      up to 30 s — accumulated per-minute step error
      up to 20 s — outdoor wind tiers
      up to 10 s — large batches (>8 kg)
    """
    buffer = 60.0
    buffer += min(30.0, 0.04 * t_heat_s)
    buffer += min(20.0, 5.0 * max(0.0, k_conv / 10.0 - 1.0))
    buffer += min(10.0, max(0.0, (m_water_kg - 8.0) * 1.5))
    return min(120.0, max(60.0, buffer))


def _transient_preview_tick(T_pot, m_water, m_food, cp_food, m_pot, cp_pot,
                            P_in_kw, A_m2, k_conv, emissivity, T_amb, lid_fac):
    """
    Execute one 1 Hz physics tick (Steps 2A-2D).
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

    return (T_pot, m_water, Q_out)


def estimate_cook_time(m_food, cp_food, m_water, m_pot, cp_pot,
                       t_kinetic_s, P_in_kw, A_m2, k_conv, emissivity,
                       T_amb, lid_fac):
    """
    Shadow 1 Hz transient preview: heat-up to 100 C, then kinetic simmer.
    Returns timing diagnostics used for the Total Time Estimator.
    """
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
        "heat_cannot_rise": 1.0 if heat_cannot_rise else 0.0,
        "m_water_end_kg": m_w,
    }


# =============================================================================
# ZERO STATE  (Phase 1 continued)
# =============================================================================

def zero_state(inp):
    inp["t_elapsed_s"]      = 0.0
    inp["T_pot_c"]          = inp["t_ambient_c"]
    inp["m_water_current"]  = inp["m_water_initial"]
    inp["flag_dry_boil"]    = False
    inp["flag_overheat"]    = False
    inp["t_boil_reached_s"] = None
    inp["tick_log"]         = []
    return inp


# =============================================================================
# PHASE 2 — 1Hz TRANSIENT LOOP (The Core Engine) — UNTOUCHED
# =============================================================================

def run_1hz_loop(inp):
    """
    Phase 2: Execute the 1Hz transient loop.
    Loop condition: while t_elapsed < inp["t_total_s"].
    Physics cascade (Steps 2A-2D) is UNCHANGED / PROTECTED.
    """
    m_food    = inp["m_food"]
    cp_food   = inp["cp_food"]
    m_pot     = inp["m_pot"]
    cp_pot    = inp["cp_pot"]
    A         = inp["A_m2"]
    eta_geom  = inp["eta_geom"]
    gcv       = inp["gcv_kj_kg"]
    lid_fac   = inp["lid_factor"]
    T_amb     = inp["t_ambient_c"]
    t_total_s = inp["t_total_s"]
    k_conv    = inp["k_conv_current"]
    emissivity = inp.get("emissivity", EMISSIVITY_DEFAULT)

    # Step 2A: Power In — constant for the entire run (high-fan rule)
    P_in_kw = (FAN_HIGH / 3600.0) * gcv * eta_geom

    T_pot            = inp["T_pot_c"]
    m_water          = inp["m_water_current"]
    t_elapsed        = inp["t_elapsed_s"]
    flag_dry         = False
    flag_over        = False
    t_boil_reached   = None

    Q_in_kj = 0.0
    Q_out_kj = 0.0
    Q_sensible_kj = 0.0
    Q_evap_kj = 0.0

    log_interval = 60
    tick_log = []
    tick = 0

    # ── LOOP CONDITION: strictly absolute-time based ──────────────────────────
    while t_elapsed < t_total_s:

        T_before = T_pot
        m_w_before = m_water

        # Step 2A: Power In
        Q_in = P_in_kw * dt

        # Step 2B: Dynamic Mass (UNCHANGED)
        MCp_total = (m_food * cp_food) + (m_water * CP_WATER) + (m_pot * cp_pot)

        # Step 2C: Heat Bleed (shared helper)
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

        # ── Advance Clock ─────────────────────────────────────────────────────
        t_elapsed += dt

        # Safety break
        if t_elapsed > MAX_SIMULATION_TIME:
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

    inp["t_elapsed_s"]      = t_elapsed
    inp["T_pot_c"]          = T_pot
    inp["m_water_current"]  = m_water
    inp["flag_dry_boil"]    = flag_dry
    inp["flag_overheat"]    = flag_over
    inp["t_boil_reached_s"] = t_boil_reached
    inp["tick_log"]         = tick_log
    inp["P_in_kw"]          = P_in_kw
    inp["Q_in_kj"]          = Q_in_kj
    inp["Q_out_kj"]         = Q_out_kj
    inp["Q_sensible_kj"]    = Q_sensible_kj
    inp["Q_evap_kj"]        = Q_evap_kj
    return inp


# =============================================================================
# PHASE 3 — POST PROCESS (Dynamic Procurement Margin — V5/V10 logic)
# =============================================================================

def post_process(inp):
    """
    Phase 3: Pellet procurement recommendation + diagnostics.

    TWO pellet outputs are produced:

    pellets_energy_based_g  [RESEARCH / DEBUG ONLY]
        Calculated from total energy demand (Q_demand_kj) divided by the
        effective pellet energy delivery rate (GCV * eta_geom). Represents
        what thermodynamics alone would suggest. NOT shown to the villager
        because the stove has no closed-loop control — it cannot modulate
        feed rate to match energy demand.

    pellets_required_g  [OPERATIONAL — shown to the villager]
        Calculated from elapsed cook time and the fixed pellet feed rate:
            pellets = (cook_time_hrs) x FAN_HIGH x 1000 x margin
        This is the correct recommendation for a constant-feed forced-draft
        stove. FAN_HIGH = 0.78 kg/hr is the experimentally measured feed
        rate at HIGH fan setting; the stove runs at this rate for the full
        cook duration regardless of dish or load.
    """
    t_elapsed = inp["t_elapsed_s"]
    gcv = inp["gcv_kj_kg"]
    eta_geom = inp["eta_geom"]
    k_conv_current = inp.get("k_conv_current", 10.0)
    lid_factor = inp.get("lid_factor", 1.0)
    utensil = inp.get("utensil", None)

    # Total energy demanded by the cook (sensible heat + evaporation + losses)
    Q_demand_kj = (
        inp["Q_sensible_kj"] + inp["Q_evap_kj"] + inp["Q_out_kj"]
    )

    # ── ENERGY-BASED PELLET ESTIMATE (research/debug only) ────────────────────
    # How many grams of pellets would thermodynamics alone require?
    # Effective delivery = GCV (kJ/kg) * combustion efficiency (eta_geom)
    effective_energy_kj_per_kg = gcv * eta_geom
    if effective_energy_kj_per_kg > 0:
        pellets_energy_based_g = (Q_demand_kj / effective_energy_kj_per_kg) * 1000.0
    else:
        pellets_energy_based_g = 0.0
    # ─────────────────────────────────────────────────────────────────────────

    # ── TIME-BASED PELLET RECOMMENDATION (operational, shown to villager) ─────
    # The stove operates at a constant, mechanically fixed pellet feed rate
    # (FAN_HIGH kg/hr). There is no closed-loop control. The correct hopper
    # load is simply: feed_rate x cook_duration x procurement_margin.
    pellets_time_g = (t_elapsed / 3600.0) * FAN_HIGH * 1000.0
    # ─────────────────────────────────────────────────────────────────────────

    # ═══════════════════════════════════════════════════════════════════════════
    # DYNAMIC PROCUREMENT MARGIN (Stochastic Environmental Variance)
    # ═══════════════════════════════════════════════════════════════════════════

    if k_conv_current >= 50.0:
        # High wind: intense forced convection
        procurement_margin = 0.12
        margin_reason = "High Wind (k_conv >= 50.0)"
    elif lid_factor == 1.0:
        # Open pot: maximum exposure
        procurement_margin = 0.10
        margin_reason = "Open Pot (lid_factor = 1.00)"
    elif lid_factor < 1.0 and utensil and not utensil.is_pressure:
        # Covered pot (not pressure cooker)
        procurement_margin = 0.07
        margin_reason = "Covered Pot (non-pressure)"
    elif utensil and utensil.is_pressure:
        # Pressure cooker: sealed, minimal loss
        procurement_margin = 0.05
        margin_reason = "Pressure Cooker (sealed)"
    else:
        # Fallback
        procurement_margin = 0.08
        margin_reason = "Default"

    # Apply dynamic margin to the operational (time-based) recommendation
    pellets_with_margin_g = pellets_time_g * (1.0 + procurement_margin)

    inp["Q_demand_kj"]              = Q_demand_kj
    # Operational output (villager-facing)
    inp["pellets_required_g"]       = pellets_with_margin_g
    inp["pellets_required_kg"]      = pellets_with_margin_g / 1000.0
    inp["pellets_time_based_g"]     = pellets_time_g
    # Research/debug output (not shown on LCD)
    inp["pellets_energy_based_g"]   = pellets_energy_based_g
    inp["procurement_margin_factor"] = (1.0 + procurement_margin)
    inp["procurement_margin_pct"]   = procurement_margin * 100.0
    inp["margin_reason"]            = margin_reason

    inp["t_phase1_s"] = 0.15 * t_elapsed
    inp["t_phase2_s"] = 0.65 * t_elapsed
    inp["t_phase3_s"] = 0.20 * t_elapsed

    return inp
