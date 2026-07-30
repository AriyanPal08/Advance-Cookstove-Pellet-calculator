def compute_vessel_geometry(m_water_kg, utensil_name, lid_factor, m_food_kg=0.0):
    utensil = get_utensil(utensil_name)
    r_inner = utensil.get_inner_radius()
    h_total = utensil.get_total_height()
    V_m3 = m_water_kg / 1000.0
    if utensil.geometry_type in (GeometryType.CYLINDER, GeometryType.PRESSURE_COOKER):
        h_fill = V_m3 / (math.pi * r_inner ** 2)
        A_bottom = math.pi * r_inner ** 2
        A_side_wetted = 2 * math.pi * r_inner * h_fill
        A_side_dry = 2 * math.pi * r_inner * max(0.0, h_total - h_fill)
        A_top = A_bottom
    elif utensil.geometry_type == GeometryType.KADHAI:
        R = r_inner
        h_fill = R / 2.0
        for _ in range(15):
            f = math.pi / 3.0 * h_fill ** 2 * (3 * R - h_fill) - V_m3
            f_prime = math.pi * h_fill * (2 * R - h_fill)
            if abs(f_prime) < 1e-09:
                break
            h_new = h_fill - f / f_prime
            if abs(h_new - h_fill) < 1e-06:
                break
            h_fill = h_new
        h_fill = max(0.0, min(h_total, h_fill))
        A_bottom = 0.0
        A_side_wetted = 2 * math.pi * R * h_fill
        A_side_dry = 2 * math.pi * R * max(0.0, h_total - h_fill)
        A_top = math.pi * r_inner ** 2
    else:
        h_fill = 0.0
        A_bottom = math.pi * r_inner ** 2
        A_side_wetted = 0.0
        A_side_dry = 0.0
        A_top = A_bottom
    A_bottom_loss = 0.0
    A_top_loss = A_top
    A_m2 = A_side_wetted + A_side_dry + A_top_loss + A_bottom_loss
    return {'V_m3': V_m3, 'd_m': r_inner * 2, 'h_m': h_fill, 'A_m2': A_m2, 'A_top': A_top, 'eta_geom': STOVE_THERMAL_EFFICIENCY}

def evaporation_loss_w(T_pot_c, T_amb_c, A_evap_m2, k_conv):
    """
    Mass-transfer analogy for pre-boil evaporation (Chilton-Colburn J-factor).
    h_m = h_c / (rho_air * Cp_air * Le^(2/3))
    """
    if A_evap_m2 <= 0.0 or T_pot_c <= T_amb_c:
        return 0.0
    h_m = k_conv / 1200.0
    import math
    P_sat_pot = 610.78 * math.exp(17.27 * T_pot_c / (T_pot_c + 237.3))
    P_sat_amb = 610.78 * math.exp(17.27 * T_amb_c / (T_amb_c + 237.3)) * 0.5
    rho_v_pot = P_sat_pot * 0.018 / (8.314 * (T_pot_c + 273.15))
    rho_v_amb = P_sat_amb * 0.018 / (8.314 * (T_amb_c + 273.15))
    m_evap_rate_kg_s = h_m * A_evap_m2 * max(0.0, rho_v_pot - rho_v_amb)
    return m_evap_rate_kg_s * (L_V * 1000.0)

def heat_loss_w(T_pot_c, T_amb_c, A_m2, k_conv, emissivity, lid_factor=1.0):
    """Total convective + radiative heat bleed (W)."""
    T_pot_K = T_pot_c + 273.15
    T_amb_K = T_amb_c + 273.15
    P_conv = k_conv * A_m2 * (T_pot_K - T_amb_K)
    P_rad = emissivity * SIGMA * A_m2 * (T_pot_K ** 4 - T_amb_K ** 4)
    return P_conv + P_rad

def heat_loss_kw(T_pot_c, T_amb_c, A_m2, k_conv, emissivity, lid_factor=1.0):
    """Heat bleed in kW (convenience wrapper)."""
    return heat_loss_w(T_pot_c, T_amb_c, A_m2, k_conv, emissivity, lid_factor) / 1000.0

def _transient_preview_tick(T_pot, m_water, m_food, cp_food, m_pot, cp_pot, P_in_kw, A_m2, A_top, k_conv, emissivity, T_amb, lid_fac):
    """Execute one 1 Hz physics tick (Steps 2A–2D)."""
    Q_in = P_in_kw * dt
    MCp_total = m_food * cp_food + m_water * CP_WATER + m_pot * cp_pot
    Q_out_dry = heat_loss_kw(T_pot, T_amb, A_m2, k_conv, emissivity, lid_fac) * dt
    m_evap_pre_boil = 0.0
    P_evap_pre_boil = 0.0
    if T_pot < 100.0 and m_water > 0.0:
        P_evap_pre_boil = evaporation_loss_w(T_pot, T_amb, A_top * lid_fac, k_conv) / 1000.0
        m_evap_pre_boil = P_evap_pre_boil * dt / L_V
        if m_evap_pre_boil > m_water:
            m_evap_pre_boil = m_water
            P_evap_pre_boil = m_evap_pre_boil * L_V / dt
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
                T_pot += Q_avail / MCp_total
                Q_avail = 0.0
            else:
                T_pot = 100.0
                Q_avail -= Q_to_100
        if Q_avail > 0 and m_water > 0:
            m_evap_boil = Q_avail / L_V if lid_fac > 0.0 else 0.0
            if m_evap_boil <= m_water:
                m_water -= m_evap_boil
                Q_avail -= m_evap_boil * L_V
            else:
                Q_boil = m_water * L_V
                m_water = 0.0
                Q_avail -= Q_boil
        if Q_avail > 0 and m_water <= 0:
            MCp_dry = m_food * cp_food + m_pot * cp_pot
            if MCp_dry > 0:
                T_pot += Q_avail / MCp_dry
            Q_avail = 0.0
    return (T_pot, m_water, Q_out)

def estimate_cook_time(m_food, cp_food, m_water, m_pot, cp_pot, t_kinetic_s, P_in_kw, A_m2, A_top, k_conv, emissivity, T_amb, lid_fac):
    """
    Shadow 1 Hz transient preview: heat-up to 100 °C, then kinetic simmer.
    Returns timing diagnostics used for the Total Time Estimator.
    """
    T_pot = T_amb
    m_w = m_water
    t_elapsed = 0.0
    t_boil: float | None = None
    Q_out_accum = 0.0
    heat_cannot_rise = False
    while T_pot < 100.0 and t_elapsed < MAX_SIMULATION_TIME:
        T_prev = T_pot
        T_pot, m_w, Q_out = _transient_preview_tick(T_pot, m_w, m_food, cp_food, m_pot, cp_pot, P_in_kw, A_m2, A_top, k_conv, emissivity, T_amb, lid_fac)
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
            T_pot, m_w, Q_out = _transient_preview_tick(T_pot, m_w, m_food, cp_food, m_pot, cp_pot, P_in_kw, A_m2, A_top, k_conv, emissivity, T_amb, lid_fac)
            t_elapsed += dt
            Q_out_accum += Q_out
    return {'t_heat_s': t_heat_s, 't_boil_s': t_boil if t_boil is not None else 0.0, 't_preview_s': t_elapsed, 'Q_out_accum_kj': Q_out_accum, 'heat_cannot_rise': float(heat_cannot_rise), 'm_water_end_kg': m_w}

def run_1hz_loop(inp):
    """
    Phase 2: Execute the 1Hz transient loop.

    Loop condition (UPDATED): while t_elapsed < inp["t_total_s"].
    No t_kinetic_remaining, no 99°C hysteresis gate.

    Physics cascade (Steps 2A-2D) is UNCHANGED / PROTECTED — identical to
    the previously verified Route A / Route B / Route B2 / Route B3 logic.
    """
    m_food: float = inp['m_food']
    cp_food: float = inp['cp_food']
    m_pot: float = inp['m_pot']
    cp_pot: float = inp['cp_pot']
    A: float = inp['A_m2']
    eta_geom: float = inp['eta_geom']
    gcv: float = inp['gcv_kj_kg']
    lid_fac: float = inp['lid_factor']
    T_amb: float = inp['t_ambient_c']
    t_total_s: float = inp['t_total_s']
    k_conv: float = inp['k_conv_current']
    emissivity: float = inp.get('emissivity', 0.35)
    P_in_kw: float = FAN_HIGH / 3600.0 * gcv * eta_geom
    T_pot: float = inp['T_pot_c']
    m_water: float = inp['m_water_current']
    t_elapsed: float = inp['t_elapsed_s']
    flag_dry: bool = False
    flag_over: bool = False
    t_boil_reached: float | None = None
    Q_in_kj = 0.0
    Q_out_kj = 0.0
    Q_sensible_kj = 0.0
    Q_evap_kj = 0.0
    log_interval = 60
    tick_log: list = []
    tick = 0
    while t_elapsed < t_total_s:
        T_before = T_pot
        m_w_before = m_water
        Q_in = P_in_kw * dt
        MCp_total = m_food * cp_food + m_water * CP_WATER + m_pot * cp_pot
        Q_out = heat_loss_kw(T_pot, T_amb, A, k_conv, emissivity, lid_fac) * dt
        Q_avail = Q_in - Q_out
        if Q_avail <= 0.0:
            if MCp_total > 0:
                T_pot += Q_avail / MCp_total
        else:
            if T_pot < 100.0:
                Q_to_100 = MCp_total * (100.0 - T_pot)
                if Q_avail <= Q_to_100:
                    T_pot += Q_avail / MCp_total
                    Q_avail = 0.0
                else:
                    T_pot = 100.0
                    Q_avail -= Q_to_100
                    if t_boil_reached is None:
                        t_boil_reached = t_elapsed + dt
            if Q_avail > 0 and m_water > 0:
                m_evap_potential = Q_avail / L_V * lid_fac
                if m_evap_potential <= m_water:
                    m_water -= m_evap_potential
                    Q_avail = 0.0
                else:
                    Q_boil = m_water / lid_fac * L_V
                    m_water = 0.0
                    Q_avail -= Q_boil
            if Q_avail > 0 and m_water <= 0:
                MCp_dry = m_food * cp_food + m_pot * cp_pot
                if MCp_dry > 0:
                    T_pot += Q_avail / MCp_dry
                Q_avail = 0.0
        Q_in_kj += Q_in
        Q_out_kj += Q_out
        dT = T_pot - T_before
        if dT != 0.0:
            if m_w_before > 0.0:
                MCp_track = m_food * cp_food + m_w_before * CP_WATER + m_pot * cp_pot
            else:
                MCp_track = m_food * cp_food + m_pot * cp_pot
            Q_sensible_kj += MCp_track * dT
        dm_evap = m_w_before - m_water
        if dm_evap > 0.0 and lid_fac > 0.0:
            Q_evap_kj += dm_evap / lid_fac * L_V
        t_elapsed += dt
        if t_elapsed > MAX_SIMULATION_TIME:
            _warn(f'MAX_SIMULATION_TIME ({MAX_SIMULATION_TIME / 3600:.1f} h) exceeded — loop terminated early for safety.')
            break
        if m_water <= M_WATER_DRY and (not flag_dry):
            flag_dry = True
        if T_pot > T_OVERHEAT_C and (not flag_over):
            flag_over = True
        tick += 1
        if tick % log_interval == 0 or t_elapsed >= t_total_s:
            tick_log.append({'t_s': t_elapsed, 'T_c': T_pot, 'm_w_kg': m_water, 't_remaining_s': max(0.0, t_total_s - t_elapsed)})
    inp.update({'t_elapsed_s': t_elapsed, 'T_pot_c': T_pot, 'm_water_current': m_water, 'flag_dry_boil': flag_dry, 'flag_overheat': flag_over, 't_boil_reached_s': t_boil_reached, 'tick_log': tick_log, 'P_in_kw': P_in_kw, 'Q_in_kj': Q_in_kj, 'Q_out_kj': Q_out_kj, 'Q_sensible_kj': Q_sensible_kj, 'Q_evap_kj': Q_evap_kj})
    return inp

