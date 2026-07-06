"""
food_db.py — Biomass Cookstove Food & Dish Database (MicroPython Native)
"""

CP_WATER_KJ_KGK = 4.171
DELTA_T_K = 75.0 

class CookingStage:
    def __init__(self, name, stage_type, duration_s=0):
        self.name = name
        self.stage_type = stage_type
        self.duration_s = duration_s

        if self.stage_type not in ("heating", "kinetic", "frying"):
            raise ValueError(f"Unknown stage_type: {self.stage_type!r}")
        if self.duration_s < 0:
            raise ValueError(f"CookingStage.{self.name} duration_s must be >= 0")
        if self.stage_type in ("kinetic", "frying") and self.duration_s <= 0:
            raise ValueError(f"Stage '{self.name}' requires positive duration")

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
                 cp_food_kj_kgk, stages, category, variable_water=False,
                 cp_source_note="", water_source_note=""):
        self.name = name
        self.food_mass_per_serving_kg = food_mass_per_serving_kg
        self.added_water_per_serving_kg = added_water_per_serving_kg
        self.cp_food_kj_kgk = cp_food_kj_kgk
        self.stages = stages
        self.category = category
        self.variable_water = variable_water
        self.cp_source_note = cp_source_note
        self.water_source_note = water_source_note

        if not self.name.strip():
            raise ValueError("DishProfile.name must not be empty.")
        if self.food_mass_per_serving_kg < 0:
            raise ValueError("food_mass_per_serving_kg must be >= 0")
        if self.added_water_per_serving_kg < 0:
            raise ValueError("added_water_per_serving_kg must be >= 0")
        if self.cp_food_kj_kgk <= 0:
            raise ValueError("cp_food_kj_kgk must be > 0")
        if not self.stages:
            raise ValueError("Must have at least one CookingStage.")

    def total_food_mass_kg(self, n):
        return self.food_mass_per_serving_kg * n

    def total_water_mass_kg(self, n):
        return self.added_water_per_serving_kg * n

    @property
    def phases(self):
        frying_s = sum(stage.duration_s for stage in self.stages if stage.stage_type == "frying")
        kinetic_s = sum(stage.duration_s for stage in self.stages if stage.stage_type == "kinetic")
        return LegacyPhaseDurations(frying_s=frying_s, boiling_s=kinetic_s, simmering_s=0)

FOOD_DB = {
    "Normal Rice": DishProfile(
        name="Normal Rice",
        food_mass_per_serving_kg=0.12,
        added_water_per_serving_kg=0.30,
        cp_food_kj_kgk=2.04,
        stages=(
            CookingStage("Heating", "heating"),
            CookingStage("Hydration", "kinetic", 300),
            CookingStage("Starch Gelatinization", "kinetic", 600),
        ),
        category="Staple Grain"
    ),
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
        category="Lentil Dish"
    ),
    "Chicken Curry": DishProfile(
        name="Chicken Curry",
        food_mass_per_serving_kg=0.22,
        added_water_per_serving_kg=0.35,
        cp_food_kj_kgk=3.74,
        stages=(
            CookingStage("Frying / Sautéing", "frying", 480),
            CookingStage("Heating", "heating"),
            CookingStage("Heat Penetration", "kinetic", 300),
            CookingStage("Protein Denaturation", "kinetic", 600),
            CookingStage("Collagen Conversion", "kinetic", 1200),
        ),
        category="Non-Veg Curry"
    ),
    "Roti": DishProfile(
        name="Roti",
        food_mass_per_serving_kg=0.09,
        added_water_per_serving_kg=0.036,
        cp_food_kj_kgk=2.66,
        stages=(
            CookingStage("Dry Cooking (Tawa)", "frying", 360),
        ),
        category="Staple Bread"
    ),
    "Tea (Chai)": DishProfile(
        name="Tea (Chai)",
        food_mass_per_serving_kg=0.020,
        added_water_per_serving_kg=0.20,
        cp_food_kj_kgk=2.86,
        stages=(
            CookingStage("Heating", "heating"),
            CookingStage("Extraction", "kinetic", 300),
        ),
        category="Beverage"
    ),
    "Sambar": DishProfile(
        name="Sambar",
        food_mass_per_serving_kg=0.110,
        added_water_per_serving_kg=0.40,
        cp_food_kj_kgk=3.34,
        stages=(
            CookingStage("Frying / Sautéing", "frying", 240),
            CookingStage("Heating", "heating"),
            CookingStage("Heat Penetration", "kinetic", 300),
            CookingStage("Hydration", "kinetic", 300),
            CookingStage("Softening", "kinetic", 720),
        ),
        category="Lentil-Vegetable Stew"
    ),
    "Coffee": DishProfile(
        name="Coffee",
        food_mass_per_serving_kg=0.012,
        added_water_per_serving_kg=0.20,
        cp_food_kj_kgk=1.70,
        stages=(
            CookingStage("Heating", "heating"),
            CookingStage("Extraction", "kinetic", 300),
        ),
        category="Beverage"
    ),
    "Mix Veg Curry": DishProfile(
        name="Mix Veg Curry",
        food_mass_per_serving_kg=0.100,
        added_water_per_serving_kg=0.22,
        cp_food_kj_kgk=3.76,
        stages=(
            CookingStage("Frying / Sautéing", "frying", 360),
            CookingStage("Heating", "heating"),
            CookingStage("Heat Penetration", "kinetic", 300),
            CookingStage("Softening", "kinetic", 900),
        ),
        category="Vegetable Curry"
    ),
    "Egg Curry": DishProfile(
        name="Egg Curry",
        food_mass_per_serving_kg=0.150,
        added_water_per_serving_kg=0.28,
        cp_food_kj_kgk=3.67,
        stages=(
            CookingStage("Frying / Sautéing", "frying", 300),
            CookingStage("Heating", "heating"),
            CookingStage("Heat Penetration", "kinetic", 300),
            CookingStage("Protein Denaturation", "kinetic", 900),
        ),
        category="Non-Veg Curry"
    ),
    "Plain Water Boiling": DishProfile(
        name="Plain Water Boiling",
        food_mass_per_serving_kg=0.001,
        added_water_per_serving_kg=0.0,
        cp_food_kj_kgk=4.171,
        stages=(
            CookingStage("Heating", "heating"),
        ),
        category="Utility / WBT Reference",
        variable_water=True
    ),
}

def get_dish_names():
    return sorted(FOOD_DB.keys())

def get_dish(dish_name):
    if dish_name not in FOOD_DB:
        raise KeyError(f"Unknown dish: {dish_name!r}")
    return FOOD_DB[dish_name]