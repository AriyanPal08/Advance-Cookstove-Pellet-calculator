import main_logic
from food_db import FOOD_DB
from utensil_db import UTENSIL_DB
from pellet_db import PELLET_DB

T_amb = 25.0
k_conv = 10.0  # Indoor (Still air)
pellet = PELLET_DB['Mustard Husk Pellets']
gcv = pellet.conservative_gcv_kj

def run_sim(name, dish_key, utensil_key, lid_factor, is_pc, m_water, m_food, cp_food, cp_pot):
    utensil = UTENSIL_DB[utensil_key]
    geom = main_logic.compute_vessel_geometry(m_water, utensil_key, lid_factor, m_food)
    P_in_kw = (0.78 / 3600.0) * gcv * geom["eta_geom"]
    
    t_kinetic_s = 0.0
    dish = FOOD_DB[dish_key]
    if not dish.variable_water:
        for stage in dish.stages:
            if stage.stage_type == "kinetic":
                t_kinetic_s += stage.duration_s * (0.20 if is_pc else 1.0)
    
    diag = main_logic.estimate_cook_time(
        m_food=m_food, cp_food=cp_food, m_water=m_water,
        m_pot=utensil.empty_mass_kg, cp_pot=cp_pot,
        t_kinetic_s=t_kinetic_s, P_in_kw=P_in_kw,
        A_m2=geom["A_m2"], A_top=geom["A_top"], k_conv=k_conv,
        emissivity=utensil.emissivity, T_amb=T_amb, lid_fac=0.0 if is_pc else lid_factor
    )
    
    total_time_min = diag['t_preview_s'] / 60.0
    heat_time_min = diag['t_heat_s'] / 60.0
    print(f"--- {name} ---")
    print(f"Heat up: {heat_time_min:.1f} min | Total: {total_time_min:.1f} min | Water left: {diag['m_water_end_kg']:.2f} kg")

# 1. water boiling for 5 litre with lid ON in AL POT
d = FOOD_DB['Plain Water Boiling']
run_sim("1. Water Boiling (5L, Lid ON, Al Pot 5L)", 'Plain Water Boiling', 'Aluminium Pot 5L', 0.15, False, 5.0, 0.0, d.cp_food_kj_kgk, UTENSIL_DB['Aluminium Pot 5L'].cp_kj_kgk)

# 2. water boiling for 5 litre with lid OFF in AL POT
run_sim("2. Water Boiling (5L, Lid OFF, Al Pot 5L)", 'Plain Water Boiling', 'Aluminium Pot 5L', 1.0, False, 5.0, 0.0, d.cp_food_kj_kgk, UTENSIL_DB['Aluminium Pot 5L'].cp_kj_kgk)

# 3. dal tadka for 4 people in kadhai
d = FOOD_DB['Dal Tadka']
n = 4
m_food = d.food_mass_per_serving_kg * n
m_water = d.added_water_per_serving_kg * n
run_sim("3. Dal Tadka (4 people, Kadhai 2.5L, Lid ON)", 'Dal Tadka', 'Kadhai / Wok 2.5L', 0.15, False, m_water, m_food, d.cp_food_kj_kgk, UTENSIL_DB['Kadhai / Wok 2.5L'].cp_kj_kgk)

# 4. rice for 4 people in cooker
d = FOOD_DB['Normal Rice']
n = 4
m_food = d.food_mass_per_serving_kg * n
m_water = d.added_water_per_serving_kg * n
run_sim("4. Rice (4 people, Pressure Cooker 3L, PC Lid)", 'Normal Rice', 'Pressure Cooker 3L', 0.0, True, m_water, m_food, d.cp_food_kj_kgk, UTENSIL_DB['Pressure Cooker 3L'].cp_kj_kgk)

# 5. tea for 5 people in khadhai
d = FOOD_DB['Tea (Chai)']
n = 5
m_food = d.food_mass_per_serving_kg * n
m_water = d.added_water_per_serving_kg * n
run_sim("5. Tea (5 people, Kadhai 2.5L, Lid OFF)", 'Tea (Chai)', 'Kadhai / Wok 2.5L', 1.0, False, m_water, m_food, d.cp_food_kj_kgk, UTENSIL_DB['Kadhai / Wok 2.5L'].cp_kj_kgk)

# 6. milk boiling for 0.5 l in kadhai
d = FOOD_DB['Boiling Milk']
n = 0.5
m_food = d.food_mass_per_serving_kg * n
m_water = d.added_water_per_serving_kg * n
run_sim("6. Boiling Milk (0.5L, Kadhai 1.5L, Lid OFF)", 'Boiling Milk', 'Kadhai / Wok 1.5L', 1.0, False, m_water, m_food, d.cp_food_kj_kgk, UTENSIL_DB['Kadhai / Wok 1.5L'].cp_kj_kgk)
