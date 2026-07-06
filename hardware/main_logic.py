"""
main_logic.py
1Hz Discrete Transient Biomass Cookstove Simulator
MicroPython Native Version (No external libraries required)
"""

import math
import sys

from food_db    import FOOD_DB, get_dish_names
from pellet_db  import PELLET_DB, get_pellet_names
from utensil_db import UTENSIL_DB, get_utensil_names

FAN_HIGH = 0.78
MAX_EFFICIENCY = 0.45
L_V = 2257.0
SIGMA = 5.67e-8
dt = 1.0
EMISSIVITY_DEFAULT = 0.35
CP_WATER = 4.184

WIND_TIERS = {
    "Indoors / Still Air":        10.0,
    "Outdoors (Low Wind)":        20.0,
    "Outdoors (Medium Wind)":     35.0,
    "Outdoors (High Wind)":       50.0,
}

T_OVERHEAT_C = 150.0
M_WATER_DRY = 0.0
LID_FACTOR_ON = 0.15
LID_FACTOR_OFF = 1.00
MAX_SIMULATION_TIME = 6 * 3600.0

def _emissivity_for_utensil(utensil):
    if utensil.cp_kj_kgk < 0.55:
        return 0.55
    if utensil.is_pressure:
        return 0.32
    return EMISSIVITY_DEFAULT

def _geometry_profile(utensil_name):
    if "Kadhai" in utensil_name or "Wok" in utensil_name:
        return 0.45, 1.12
    if "Tawa" in utensil_name or "Pan" in utensil_name:
        return 0.28, 1.30
    return 0.65, 1.00

def compute_vessel_geometry(m_water_kg, utensil_name, lid_factor):
    V_m3 = m_water_kg / 1000.0
    h_over_d, surface_mult = _geometry_profile(utensil_name)
    d_m = (4.0 * V_m3 / (math.pi * h_over_d)) ** (1.0 / 3.0)
    h_m = h_over_d * d_m
    r_m = d_m / 2.0
    A_side = math.pi * d_m * h_m
    A_top  = math.pi * r_m ** 2
    top_exposure = 0.30 if lid_factor <= LID_FACTOR_ON else 0.85
    A_m2 = surface_mult * (A_side + top_exposure * A_top)
    eta_geom = MAX_EFFICIENCY * max(0.38, min(1.0, (m_water_kg / 5.0) ** 0.35))
    return {"V_m3": V_m3, "d_m": d_m, "h_m": h_m, "A_m2": A_m2, "eta_geom": eta_geom}

def heat_loss_w(T_pot_c, T_amb_c, A_m2, k_conv, emissivity, lid_factor=LID_FACTOR_OFF):
    T_pot_K = T_pot_c + 273.15
    T_amb_K = T_amb_c + 273.15
    conv_factor = 0.85 + 0.15 * lid_factor
    P_conv = k_conv * A_m2 * (T_pot_K - T_amb_K) * conv_factor
    P_rad  = emissivity * SIGMA * A_m2 * (T_pot_K ** 4 - T_amb_K ** 4)
    return P_conv + P_rad

def heat_loss_kw(T_pot_c, T_amb_c, A_m2, k_conv, emissivity, lid_factor=LID_FACTOR_OFF):
    return heat_loss_w(T_pot_c, T_amb_c, A_m2, k_conv, emissivity, lid_factor) / 1000.0

def compute_safety_buffer_s(t_heat_s, k_conv, m_water_kg):
    buffer = 60.0
    buffer += min(30.0, 0.04 * t_heat_s)
    buffer += min(20.0, 5.0 * max(0.0, k_conv / 10.0 - 1.0))
    buffer += min(10.0, max(0.0, (m_water_kg - 8.0) * 1.5))
    return min(120.0, max(60.0, buffer))

def _transient_preview_tick(T_pot, m_water, m_food, cp_food, m_pot, cp_pot, P_in_kw, A_m2, k_conv, emissivity, T_amb, lid_fac):
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

def estimate_cook_time(m_food, cp_food, m_water, m_pot, cp_pot, t_kinetic_s, P_in_kw, A_m2, k_conv, emissivity, T_amb, lid_fac):
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
        "heat_cannot_rise": float(heat_cannot_rise),
        "m_water_end_kg": m_w,
    }

def zero_state(inp):
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

def run_1hz_loop(inp):
    m_food = inp["m_food"]
    cp_food = inp["cp_food"]
    m_pot = inp["m_pot"]
    cp_pot = inp["cp_pot"]
    A = inp["A_m2"]
    eta_geom = inp["eta_geom"]
    gcv = inp["gcv_kj_kg"]
    lid_fac = inp["lid_factor"]
    T_amb = inp["t_ambient_c"]
    t_total_s = inp["t_total_s"]
    k_conv = inp["k_conv_current"]
    emissivity = inp.get("emissivity", EMISSIVITY_DEFAULT)

    P_in_kw = (FAN_HIGH / 3600.0) * gcv * eta_geom

    T_pot = inp["T_pot_c"]
    m_water = inp["m_water_current"]
    t_elapsed = inp["t_elapsed_s"]
    flag_dry = False
    flag_over = False
    t_boil_reached = None

    Q_in_kj = 0.0
    Q_out_kj = 0.0
    Q_sensible_kj = 0.0
    Q_evap_kj = 0.0

    log_interval = 60
    tick_log = []
    tick = 0

    while t_elapsed < t_total_s:
        T_before = T_pot
        m_w_before = m_water

        Q_in = P_in_kw * dt
        MCp_total = (m_food * cp_food) + (m_water * CP_WATER) + (m_pot * cp_pot)
        Q_out = heat_loss_kw(T_pot, T_amb, A, k_conv, emissivity, lid_fac) * dt
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
                    if t_boil_reached is None:
                        t_boil_reached = t_elapsed + dt

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

        if t_elapsed > MAX_SIMULATION_TIME:
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

def post_process(inp):
    t_elapsed = inp["t_elapsed_s"]
    Q_demand_kj = inp["Q_sensible_kj"] + inp["Q_evap_kj"] + inp["Q_out_kj"]
    pellets_time_g = (t_elapsed / 3600.0) * FAN_HIGH * 1000.0

    inp["Q_demand_kj"] = Q_demand_kj
    inp["pellets_required_g"] = pellets_time_g
    inp["pellets_required_kg"] = pellets_time_g / 1000.0
    inp["pellets_time_based_g"] = pellets_time_g

    inp["t_phase1_s"] = 0.15 * t_elapsed
    inp["t_phase2_s"] = 0.65 * t_elapsed
    inp["t_phase3_s"] = 0.20 * t_elapsed

    return inp

def print_receipt(inp):
    now_str = "SYSTEM LIVE"
    print("\n========================================================================")
    print(f"  IIT DELHI  |  1Hz Transient Biomass Cookstove Simulator")
    print(f"  Status: {now_str}")
    print("========================================================================\n")
    print(f"  Dish: {inp['dish_name']}")
    print(f"  Suggested Total Time: {inp['t_total_s']/60:.1f} min")
    print(f"  Pellets Required: {inp['pellets_required_g']:.1f} g")
    print("========================================================================")