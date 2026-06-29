import math

# 3. Immovable Physical Constants
FAN_HIGH = 0.78 # (kg/hr)
MAX_EFFICIENCY = 0.45
K_CONV_STILL_AIR = 10.0 # (W/m²K)
L_V = 2257 # (kJ/kg)
SIGMA = 5.67e-8 # (W/m²K⁴)
dt = 1.0 # (s)
EMISSIVITY = 0.3

def simulate_cookstove(
    gcv, # Gross Calorific Value (kJ/kg)
    m_base_food, # Base Food Mass (kg)
    m_base_water, # Base Water Mass (kg)
    cp_food, # Food Specific Heat (kJ/kgK)
    t_kinetic_base, # Kinetic Timer (seconds)
    portions, # Portions (n)
    m_pot, # Vessel Mass (kg)
    cp_pot, # Vessel Specific Heat (kJ/kgK)
    lid_factor, # Lid Factor (0.15 for ON, 1.0 for OFF)
    t_amb, # Ambient Temperature (°C)
    cp_water=4.184, # Water Specific Heat (kJ/kgK) - standard value assumed as it's not in constants
    t_kinetic_override=None # Time Override: Manual user input overrides t_kinetic_base (s)
):
    """
    1Hz Discrete Transient Biomass Cookstove Simulator
    """
    # 4. Pre-Simulation Logic (User Inputs & Hidden Geometry)
    
    # A. Inputs & Database Lookups
    # Time Override: Manual user input overrides t_kinetic_base.
    if t_kinetic_override is not None:
        t_kinetic_base = t_kinetic_override
        
    n = portions

    # B. Initial Setup & Hidden Geometry
    m_food = m_base_food * n
    m_water_initial = m_base_water * n
    
    # Assume standard cylinder (height = diameter) to calculate surface area A silently.
    v_m3 = m_water_initial / 1000.0
    # Guard against zero water mass causing mathematical domain error
    if v_m3 > 0:
        d = (4.0 * v_m3 / math.pi)**(1.0/3.0)
    else:
        d = 0
    a = 1.25 * math.pi * (d**2)
    
    # C. Empirical Geometric Coupling (η_geom)
    # η_geom = MAX_EFFICIENCY × max(0.25, min(1.0, √(m_water_initial / 5.0)))
    eta_geom = MAX_EFFICIENCY * max(0.25, min(1.0, math.sqrt(m_water_initial / 5.0)))
    
    # D. Zero State
    t_elapsed = 0.0 # s
    t_pot = t_amb
    m_water_current = m_water_initial
    t_kinetic_remaining = t_kinetic_base
    
    # 5. The 1Hz Transient Physics Loop (Core Engine)
    # Execute a while loop that iterates exactly dt (1.0) per cycle until t_kinetic_remaining <= 0.
    while t_kinetic_remaining > 0:
        # Step 5.1: Power Generation
        p_in = (FAN_HIGH / 3600.0) * gcv * eta_geom
        q_in = p_in * dt
        
        # Step 5.2: Dynamic Thermal Mass
        mcp_total = (m_food * cp_food) + (m_water_current * cp_water) + (m_pot * cp_pot)
        
        # Step 5.3: Heat Bleed
        # Convert to Kelvin (T_K = T_°C + 273.15).
        t_pot_k = t_pot + 273.15
        t_amb_k = t_amb + 273.15
        
        p_conv = K_CONV_STILL_AIR * a * (t_pot_k - t_amb_k)
        p_rad = EMISSIVITY * SIGMA * a * ((t_pot_k**4) - (t_amb_k**4))
        q_out = ((p_conv + p_rad) / 1000.0) * dt
        
        # Step 5.4: Net Energy & State Routing (Conservation of Energy)
        q_avail = q_in - q_out
        
        if q_avail <= 0: # (Cooling)
            delta_t = q_avail / mcp_total
            t_pot = t_pot + delta_t
        else: # If Q_avail > 0 (Heating & Boiling Sequence)
            # Sensible Heating to 100°C:
            q_to_100 = mcp_total * (100.0 - t_pot)
            
            if q_avail <= q_to_100:
                t_pot = t_pot + (q_avail / mcp_total)
                q_avail = 0
            else: # If Q_avail > Q_to_100
                t_pot = 100.0
                q_avail = q_avail - q_to_100
                
                # Evaporation (Latent Heat):
                m_evap_potential = (q_avail / L_V) * lid_factor
                
                if m_evap_potential <= m_water_current:
                    m_water_current = m_water_current - m_evap_potential
                    q_avail = 0
                else: # If m_evap_potential > m_water_current
                    q_boil = (m_water_current / lid_factor) * L_V
                    m_water_current = 0
                    q_avail = q_avail - q_boil
                    
                    # Dry Runaway Heating:
                    mcp_dry = (m_food * cp_food) + (m_pot * cp_pot)
                    t_pot = t_pot + (q_avail / mcp_dry)
                    
        # Step 5.5: Advance the Clock & Timer Hysteresis
        t_elapsed = t_elapsed + dt
        
        # Condition:
        if t_pot >= 99.0:
            # t_kinetic_remaining = t_kinetic_remaining − dt (Hysteresis boundary to prevent numerical oscillation).
            t_kinetic_remaining = t_kinetic_remaining - dt

    # 6. Post-Processing Outputs
    # When t_kinetic_remaining <= 0, break loop and generate output.
    
    # A. Ultimate Fuel Output
    total_pellets_required = (t_elapsed / 3600.0) * FAN_HIGH * 1000.0 # grams
    
    # B. Safety Diagnostics
    diagnostics = []
    # Dry-Boil:
    if m_water_current <= 0:
        diagnostics.append("FATAL WARNING: Pot boiled dry. Food burnt.")
        
    # Overheat:
    if t_pot > 150.0:
        diagnostics.append("CRITICAL: Vessel temperature exceeded safe limits.")
        
    # C. Academic 3-Phase Receipt (UI Only)
    # Disclaimer: Illustrative timeline only. Not used in governing physics.
    phase_1 = "Phase 1 (Ignition): First 15% of t_elapsed.\n\"Stove reaching operating temperature. Expect initial smoke.\""
    phase_2 = "Phase 2 (Steady State): Middle 65% of t_elapsed.\n\"Optimal clean combustion and rapid boiling.\""
    phase_3 = "Phase 3 (Char/Coals): Final 20% of t_elapsed.\n\"Fresh wood exhausted. Simmer finishing on highly efficient radiant char.\""
    
    receipt = f"{phase_1}\n\n{phase_2}\n\n{phase_3}"

    return {
        "Total_Pellets_Required_grams": total_pellets_required,
        "Safety_Diagnostics": diagnostics,
        "Academic_3_Phase_Receipt": receipt
    }