# =============================================================================
# hardware/food_db.py — MicroPython Port (ESP32)
# Biomass Cookstove Food & Dish Database — v10
# Converted from @dataclass(frozen=True) to plain __init__ classes.
# All Cp, mass, stage duration, and Smart Unit values preserved exactly.
# cp_source_note / water_source_note stripped to save ESP32 RAM.
#
# SOURCES:
# [1] Choi & Okos (1986). Food Eng. Process Appl., 1, 93-101.
# [2] ICMR-NIN (2017). Indian Food Composition Tables (IFCT 2017).
# [3] CSIR-CFTRI (2020). Processing Profiles for Indigenous Grains.
# [4] CCT Protocol v2.0 (2014). Clean Cooking Alliance / Aprovecho.
# [5] Singh (2007). Hydration kinetics of chickpea and blackgram.
# =============================================================================

# Cp of water at T=60 C midpoint [Choi & Okos 1986]
CP_WATER_KJ_KGK = 4.171
DELTA_T_K = 75.0   # 100 C - 25 C ambient


class CookingStage:
    def __init__(self, name, stage_type, duration_s=0):
        self.name = name
        self.stage_type = stage_type
        self.duration_s = duration_s


class LegacyPhaseDurations:
    def __init__(self, frying_s=0, boiling_s=0, simmering_s=0):
        self.frying_s = frying_s
        self.boiling_s = boiling_s
        self.simmering_s = simmering_s

    @property
    def total_s(self):
        return self.frying_s + self.boiling_s + self.simmering_s


class DishProfile:
    def __init__(self, name, food_mass_per_serving_kg, added_water_per_serving_kg,
                 cp_food_kj_kgk, stages, category,
                 variable_water=False,
                 qty_prompt="", qty_unit="", qty_is_float=False,
                 qty_min=1.0, qty_max=50.0, qty_default=4.0):
        self.name = name
        self.food_mass_per_serving_kg = food_mass_per_serving_kg
        self.added_water_per_serving_kg = added_water_per_serving_kg
        self.cp_food_kj_kgk = cp_food_kj_kgk
        self.stages = stages
        self.category = category
        self.variable_water = variable_water
        # Smart Serving Unit fields (v10)
        self.qty_prompt = qty_prompt
        self.qty_unit = qty_unit
        self.qty_is_float = qty_is_float
        self.qty_min = qty_min
        self.qty_max = qty_max
        self.qty_default = qty_default

    def total_food_mass_kg(self, n):
        return self.food_mass_per_serving_kg * n

    def total_water_mass_kg(self, n):
        return self.added_water_per_serving_kg * n

    def q_sensible_food(self, n):
        return self.total_food_mass_kg(n) * self.cp_food_kj_kgk * DELTA_T_K

    def q_sensible_water(self, n):
        return self.total_water_mass_kg(n) * CP_WATER_KJ_KGK * DELTA_T_K

    @property
    def phases(self):
        frying_s = 0
        kinetic_s = 0
        for stage in self.stages:
            if stage.stage_type == "frying":
                frying_s += stage.duration_s
            elif stage.stage_type == "kinetic":
                kinetic_s += stage.duration_s
        return LegacyPhaseDurations(
            frying_s=frying_s,
            boiling_s=kinetic_s,
            simmering_s=0,
        )


# ===========================================================================
# MASTER FOOD DATABASE — 14 dishes
# All Cp values: Choi & Okos (1986) at T=60 C, ICMR-NIN IFCT 2017.
# Component Cp at 60 C: Water=4.1707, Protein=2.0807, Fat=2.0726,
#                        Carb=1.6665, Ash=1.2060  kJ/kg-K
# ===========================================================================

FOOD_DB = {

    # ── MILLED RICE ──────────────────────────────────────────────────────────
    # Cp = 2.04 kJ/kg-K  (Xw=0.137, Xp=0.075, Xf=0.005, Xc=0.774, Xa=0.006)
    "Milled Rice": DishProfile(
        name="Normal Rice",
        food_mass_per_serving_kg=0.12,
        added_water_per_serving_kg=0.30,
        cp_food_kj_kgk=2.04,
        stages=(
            CookingStage("Heating", "heating"),
            CookingStage("Hydration", "kinetic", 300),
            CookingStage("Starch Gelatinization", "kinetic", 600),
        ),
        category="Staple Grain",
    ),

    # ── DAL TADKA ────────────────────────────────────────────────────────────
    # Cp = 1.95 kJ/kg-K  (Xw=0.104, Xp=0.240, Xf=0.013, Xc=0.567, Xa=0.035)
    "Dal Tadka": DishProfile(
        name="Dal Tadka",
        food_mass_per_serving_kg=0.04,
        added_water_per_serving_kg=0.24,
        cp_food_kj_kgk=1.95,
        stages=(
            CookingStage("Frying (Tadka)", "frying", 180),
            CookingStage("Heating", "heating"),
            CookingStage("Heat Penetration", "kinetic", 420),
            CookingStage("Hydration", "kinetic", 300),
            CookingStage("Softening", "kinetic", 900),
        ),
        category="Lentil Dish",
    ),

    # ── CHICKEN CURRY ────────────────────────────────────────────────────────
    # Cp = 3.74 kJ/kg-K  (mass-weighted: 120g chicken + 60g onion + 40g tomato)
    "Chicken Curry": DishProfile(
        name="Chicken Curry",
        food_mass_per_serving_kg=0.22,
        added_water_per_serving_kg=0.35,
        cp_food_kj_kgk=3.74,
        stages=(
            CookingStage("Frying / Sauteing", "frying", 480),
            CookingStage("Heating", "heating"),
            CookingStage("Heat Penetration", "kinetic", 300),
            CookingStage("Protein Denaturation", "kinetic", 600),
            CookingStage("Collagen Conversion", "kinetic", 1200),
        ),
        category="Non-Veg Curry",
    ),

    # ── ROTI (per single roti — v10 Smart Units) ────────────────────────────
    # Cp = 2.66 kJ/kg-K  (dough: (90/126)*2.05 + (36/126)*4.171)
    "Roti": DishProfile(
        name="Roti",
        food_mass_per_serving_kg=0.030,
        added_water_per_serving_kg=0.012,
        cp_food_kj_kgk=2.66,
        stages=(
            CookingStage("Dry Cooking (Tawa)", "frying", 360),
        ),
        category="Staple Bread",
        qty_prompt="Number of Rotis",
        qty_unit="rotis",
        qty_is_float=False,
        qty_min=2.0,
        qty_max=30.0,
        qty_default=4.0,
    ),

    # ── TEA (CHAI) ───────────────────────────────────────────────────────────
    # Cp = 2.86 kJ/kg-K  (solids proxy: Xp~0.05, Xf~0.06, Xc~0.87, Xa~0.02)
    "Tea": DishProfile(
        name="Tea (Chai)",
        food_mass_per_serving_kg=0.020,
        added_water_per_serving_kg=0.20,
        cp_food_kj_kgk=2.86,
        stages=(
            CookingStage("Heating", "heating"),
            CookingStage("Extraction", "kinetic", 300),
        ),
        category="Beverage",
    ),

    # ── SAMBAR ───────────────────────────────────────────────────────────────
    # Cp = 3.34 kJ/kg-K  (composite: toor dal + vegetables)
    "Sambar": DishProfile(
        name="Sambar",
        food_mass_per_serving_kg=0.110,
        added_water_per_serving_kg=0.40,
        cp_food_kj_kgk=3.34,
        stages=(
            CookingStage("Frying / Sauteing", "frying", 240),
            CookingStage("Heating", "heating"),
            CookingStage("Heat Penetration", "kinetic", 300),
            CookingStage("Hydration", "kinetic", 300),
            CookingStage("Softening", "kinetic", 720),
        ),
        category="Lentil-Vegetable Stew",
    ),

    # ── COFFEE ───────────────────────────────────────────────────────────────
    # Cp = 1.70 kJ/kg-K  (proxy: Xc~0.80, Xp~0.12, Xf~0.02, Xa~0.06)
    "Coffee": DishProfile(
        name="Coffee",
        food_mass_per_serving_kg=0.012,
        added_water_per_serving_kg=0.20,
        cp_food_kj_kgk=1.70,
        stages=(
            CookingStage("Heating", "heating"),
            CookingStage("Extraction", "kinetic", 300),
        ),
        category="Beverage",
    ),

    # ── MIX VEG CURRY ────────────────────────────────────────────────────────
    # Cp = 3.76 kJ/kg-K  (composite: potato, carrot, beans, peas)
    "Mix Veg Curry": DishProfile(
        name="Mix Veg Curry",
        food_mass_per_serving_kg=0.100,
        added_water_per_serving_kg=0.22,
        cp_food_kj_kgk=3.76,
        stages=(
            CookingStage("Frying / Sauteing", "frying", 360),
            CookingStage("Heating", "heating"),
            CookingStage("Heat Penetration", "kinetic", 300),
            CookingStage("Softening", "kinetic", 900),
        ),
        category="Vegetable Curry",
    ),

    # ── EGG CURRY ────────────────────────────────────────────────────────────
    # Cp = 3.67 kJ/kg-K  (composite: (110/150)*3.60 + (40/150)*3.85)
    "Egg Curry": DishProfile(
        name="Egg Curry",
        food_mass_per_serving_kg=0.150,
        added_water_per_serving_kg=0.28,
        cp_food_kj_kgk=3.67,
        stages=(
            CookingStage("Frying / Sauteing", "frying", 300),
            CookingStage("Heating", "heating"),
            CookingStage("Heat Penetration", "kinetic", 300),
            CookingStage("Protein Denaturation", "kinetic", 900),
        ),
        category="Non-Veg Curry",
    ),

    # ── PLAIN WATER BOILING (variable_water=True) ────────────────────────────
    # Cp = 4.171 kJ/kg-K  (trace solids approximated as water)
    "Water Boil": DishProfile(
        name="Plain Water Boiling",
        food_mass_per_serving_kg=0.001,
        added_water_per_serving_kg=0.0,
        cp_food_kj_kgk=4.171,
        stages=(
            CookingStage("Heating", "heating"),
        ),
        category="Utility / WBT Reference",
        variable_water=True,
    ),

    # ── CHOLA (SOAKED CHICKPEA) ──────────────────────────────────────────────
    # Cp = 3.10 kJ/kg-K  (Xw=0.68, Xp=0.12, Xc=0.20) [Choi-Okos; Singh 2007]
    "Chola (Chickpea)": DishProfile(
        name="Chola (Soaked Chickpea)",
        food_mass_per_serving_kg=0.20,
        added_water_per_serving_kg=0.25,
        cp_food_kj_kgk=3.10,
        stages=(
            CookingStage("Frying / Tempering", "frying", 300),
            CookingStage("Heating", "heating"),
            CookingStage("Boiling & Softening", "kinetic", 2400),
        ),
        category="Legume (Soaked)",
    ),

    # ── RAJMA (SOAKED RED KIDNEY BEAN) ───────────────────────────────────────
    # Cp = 3.10 kJ/kg-K  (Xw~0.68, Xp~0.12, Xc~0.20) [Singh 2007]
    "Rajma": DishProfile(
        name="Rajma (Soaked Red Kidney Bean)",
        food_mass_per_serving_kg=0.20,
        added_water_per_serving_kg=0.25,
        cp_food_kj_kgk=3.10,
        stages=(
            CookingStage("Frying / Tempering", "frying", 300),
            CookingStage("Heating", "heating"),
            CookingStage("Boiling & Softening", "kinetic", 2700),
        ),
        category="Legume (Soaked)",
    ),

    # ── KADHAI PANEER ────────────────────────────────────────────────────────
    # Cp = 3.25 kJ/kg-K  (composite: 50% paneer + 50% gravy)
    "Kadhai Paneer": DishProfile(
        name="Kadhai Paneer",
        food_mass_per_serving_kg=0.20,
        added_water_per_serving_kg=0.15,
        cp_food_kj_kgk=3.25,
        stages=(
            CookingStage("Frying / Tempering", "frying", 480),
            CookingStage("Heating", "heating"),
            CookingStage("Gravy & Paneer Simmering", "kinetic", 900),
        ),
        category="Paneer Curry",
    ),

    # ── BOILING MILK (v10 dry-solids model) ──────────────────────────────────
    # Cp = 1.50 kJ/kg-K (solids-only: Xp=0.246, Xf=0.285, Xc=0.377, Xa=0.077)
    # food_mass = 0.130 kg dry solids per litre
    # added_water = 0.870 kg inherent water per litre
    "Milk": DishProfile(
        name="Boiling Milk",
        food_mass_per_serving_kg=0.130,
        added_water_per_serving_kg=0.870,
        cp_food_kj_kgk=1.50,
        stages=(
            CookingStage("Heating to Boil", "heating"),
            CookingStage("Gentle Boiling", "kinetic", 180),
        ),
        category="Beverage (Dairy)",
        variable_water=False,
        qty_prompt="Volume of Milk (Litres)",
        qty_unit="L",
        qty_is_float=True,
        qty_min=0.5,
        qty_max=10.0,
        qty_default=1.0,
    ),
}


def get_dish_names():
    return sorted(FOOD_DB.keys())


def get_dish(dish_name):
    if dish_name not in FOOD_DB:
        raise KeyError("Unknown dish: " + dish_name)
    return FOOD_DB[dish_name]
