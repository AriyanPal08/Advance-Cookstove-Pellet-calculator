
# cp_source_note / water_source_note stripped to save ESP32 RAM.

#     sources — reworded as cross-references instead of inventing a source.

#     used instead and cited as [8] — see SOURCES.

CP_WATER_KJ_KGK = 4.184  
DELTA_T_K = 75.0   

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
                 qty_min=1.0, qty_max=50.0, qty_default=4.0,
                 allowed_utensils=None, recommended_utensils=None, forbidden_utensils=None,
                 max_fill_ratio=0.85):
        self.name = name
        self.food_mass_per_serving_kg = food_mass_per_serving_kg
        self.added_water_per_serving_kg = added_water_per_serving_kg
        self.cp_food_kj_kgk = cp_food_kj_kgk
        self.stages = stages
        self.category = category
        self.variable_water = variable_water

        self.qty_prompt = qty_prompt
        self.qty_unit = qty_unit
        self.qty_is_float = qty_is_float
        self.qty_min = qty_min
        self.qty_max = qty_max
        self.qty_default = qty_default
        self.allowed_utensils = allowed_utensils or ["CYLINDER", "PRESSURE_COOKER", "KADHAI"]
        self.recommended_utensils = recommended_utensils or ["CYLINDER"]
        self.forbidden_utensils = forbidden_utensils or ["TAWA"]
        self.max_fill_ratio = max_fill_ratio

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
FOOD_DB = {

    "Normal Rice": DishProfile(
        name="Normal Rice",
        food_mass_per_serving_kg=0.12,
        added_water_per_serving_kg=0.30,
        cp_food_kj_kgk=2.041,
        stages=(
            CookingStage("Heating", "heating"),
            CookingStage("Hydration", "kinetic", 300),
            CookingStage("Starch Gelatinization", "kinetic", 600),
        ),
        category="Staple Grain",
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

    "Dal Tadka": DishProfile(
        name="Dal Tadka",
        food_mass_per_serving_kg=0.04,
        added_water_per_serving_kg=0.24,
        cp_food_kj_kgk=2.030,
        stages=(
            CookingStage("Frying (Tadka)", "frying", 180),
            CookingStage("Heating", "heating"),
            CookingStage("Heat Penetration", "kinetic", 420),
            CookingStage("Hydration", "kinetic", 300),
            CookingStage("Softening", "kinetic", 900),
        ),
        category="Lentil Dish",
        allowed_utensils=["CYLINDER", "PRESSURE_COOKER", "KADHAI"],
        recommended_utensils=["PRESSURE_COOKER"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.6
    ),

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
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

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
        allowed_utensils=["TAWA"],
        recommended_utensils=["TAWA"],
        forbidden_utensils=["CYLINDER", "PRESSURE_COOKER", "KADHAI"],
        max_fill_ratio=0.1
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
        category="Beverage",
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

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
        allowed_utensils=["CYLINDER", "PRESSURE_COOKER", "KADHAI"],
        recommended_utensils=["PRESSURE_COOKER"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.6
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
        category="Beverage",
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

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
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

    "Egg Curry": DishProfile(
        name="Egg Curry",
        food_mass_per_serving_kg=0.150,
        added_water_per_serving_kg=0.28,
        cp_food_kj_kgk=3.723,
        stages=(
            CookingStage("Frying / Sauteing", "frying", 300),
            CookingStage("Heating", "heating"),
            CookingStage("Heat Penetration", "kinetic", 300),
            CookingStage("Protein Denaturation", "kinetic", 900),
        ),
        category="Non-Veg Curry",
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
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
        variable_water=True,
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

    "Chola (Soaked Chickpea)": DishProfile(
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
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

    "Rajma (Soaked Red Kidney Bean)": DishProfile(
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
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

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
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

    "Aloo Gobi": DishProfile(
        name="Aloo Gobi",
        food_mass_per_serving_kg=0.120,
        added_water_per_serving_kg=0.22,
        cp_food_kj_kgk=3.709,
        stages=(
            CookingStage("Frying / Sauteing", "frying", 300),
            CookingStage("Heating", "heating"),
            CookingStage("Heat Penetration", "kinetic", 300),
            CookingStage("Softening (Pectin)", "kinetic", 720),
        ),
        category="Vegetable Curry",
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

    "Aloo Matar": DishProfile(
        name="Aloo Matar",
        food_mass_per_serving_kg=0.110,
        added_water_per_serving_kg=0.22,
        cp_food_kj_kgk=3.602,
        stages=(
            CookingStage("Frying / Sauteing", "frying", 300),
            CookingStage("Heating", "heating"),
            CookingStage("Heat Penetration", "kinetic", 300),
            CookingStage("Softening (Pectin)", "kinetic", 600),
        ),
        category="Vegetable Curry",
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

    "Dal Fry": DishProfile(
        name="Dal Fry",
        food_mass_per_serving_kg=0.035,
        added_water_per_serving_kg=0.24,
        cp_food_kj_kgk=2.018,
        stages=(
            CookingStage("Frying (Tadka)", "frying", 180),
            CookingStage("Heating", "heating"),
            CookingStage("Heat Penetration", "kinetic", 360),
            CookingStage("Softening", "kinetic", 600),
        ),
        category="Lentil Dish",
        allowed_utensils=["CYLINDER", "PRESSURE_COOKER", "KADHAI"],
        recommended_utensils=["PRESSURE_COOKER"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.6
    ),

    "Fish Curry": DishProfile(
        name="Fish Curry",
        food_mass_per_serving_kg=0.180,
        added_water_per_serving_kg=0.28,
        cp_food_kj_kgk=3.791,
        stages=(
            CookingStage("Frying / Sauteing", "frying", 360),
            CookingStage("Heating", "heating"),
            CookingStage("Heat Penetration", "kinetic", 180),
            CookingStage("Protein Denaturation", "kinetic", 480),
        ),
        category="Non-Veg Curry",
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

    "Paneer Butter Masala": DishProfile(
        name="Paneer Butter Masala",
        food_mass_per_serving_kg=0.180,
        added_water_per_serving_kg=0.15,
        cp_food_kj_kgk=3.460,
        stages=(
            CookingStage("Frying / Tempering", "frying", 480),
            CookingStage("Heating", "heating"),
            CookingStage("Gravy Simmering", "kinetic", 900),
        ),
        category="Paneer Curry",
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

    "Khichdi": DishProfile(
        name="Khichdi",
        food_mass_per_serving_kg=0.080,
        added_water_per_serving_kg=0.30,
        cp_food_kj_kgk=1.937,
        stages=(
            CookingStage("Heating", "heating"),
            CookingStage("Hydration", "kinetic", 300),
            CookingStage("Gelatinization", "kinetic", 600),
        ),
        category="Staple Grain",
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

    "Poha": DishProfile(
        name="Poha",
        food_mass_per_serving_kg=0.060,
        added_water_per_serving_kg=0.04,
        cp_food_kj_kgk=1.998,
        stages=(
            CookingStage("Frying / Sauteing", "frying", 120),
            CookingStage("Heating", "heating"),
            CookingStage("Softening", "kinetic", 180),
        ),
        category="Snack / Breakfast",
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

    "Upma": DishProfile(
        name="Upma",
        food_mass_per_serving_kg=0.050,
        added_water_per_serving_kg=0.15,
        cp_food_kj_kgk=1.992,
        stages=(
            CookingStage("Frying (Dry Roast)", "frying", 240),
            CookingStage("Heating", "heating"),
            CookingStage("Gelatinization", "kinetic", 300),
        ),
        category="Snack / Breakfast",
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

    "Maggi": DishProfile(
        name="Maggi",
        food_mass_per_serving_kg=0.070,
        added_water_per_serving_kg=0.25,
        cp_food_kj_kgk=1.956,
        stages=(
            CookingStage("Heating", "heating"),
            CookingStage("Softening", "kinetic", 180),
        ),
        category="Snack / Breakfast",
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

    # Kinetic Stage Source (Dairy Physical Chemistry):

    "Boiling Milk": DishProfile(
        name="Boiling Milk",
        food_mass_per_serving_kg=0.130,
        added_water_per_serving_kg=0.870,
        cp_food_kj_kgk=1.851,
        stages=(
            CookingStage("Heating to Boil", "heating"),
            CookingStage("Foaming & Rising", "kinetic", 60),
        ),
        category="Beverage (Dairy)",
        variable_water=False,
        qty_prompt="Volume of Milk (Litres)",
        qty_unit="L",
        qty_is_float=True,
        qty_min=0.5,
        qty_max=10.0,
        qty_default=1.0,
        allowed_utensils=["CYLINDER", "PRESSURE_COOKER", "KADHAI"],
        recommended_utensils=["CYLINDER"],
        forbidden_utensils=["TAWA", "PRESSURE_COOKER"],
        max_fill_ratio=0.5
    ),

    # ===========================================================================

    # copied outright. Sources for new ingredient fractions are IFCT 2017 [2]

    # ===========================================================================

    "Butter Chicken": DishProfile(
        name="Butter Chicken",
        food_mass_per_serving_kg=0.20,
        added_water_per_serving_kg=0.10,
        cp_food_kj_kgk=3.603,
        stages=(
            CookingStage("Charring (Tandoor-style Sear)", "frying", 300),
            CookingStage("Heating", "heating"),
            CookingStage("Heat Penetration", "kinetic", 300),
            CookingStage("Protein Denaturation", "kinetic", 600),
            CookingStage("Cream Gravy Simmering", "kinetic", 1080),
        ),
        category="Non-Veg Curry",
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

    "Chicken Tikka Masala": DishProfile(
        name="Chicken Tikka Masala",
        food_mass_per_serving_kg=0.20,
        added_water_per_serving_kg=0.12,
        cp_food_kj_kgk=3.656,
        stages=(
            CookingStage("Marination & Grilling", "frying", 420),
            CookingStage("Heating", "heating"),
            CookingStage("Heat Penetration", "kinetic", 300),
            CookingStage("Protein Denaturation", "kinetic", 600),
            CookingStage("Gravy Simmering", "kinetic", 900),
        ),
        category="Non-Veg Curry",
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

    "Mutton Curry (Goat)": DishProfile(
        name="Mutton Curry (Goat)",
        food_mass_per_serving_kg=0.22,
        added_water_per_serving_kg=0.30,
        cp_food_kj_kgk=3.767,
        stages=(
            CookingStage("Frying / Sauteing", "frying", 480),
            CookingStage("Heating", "heating"),
            CookingStage("Heat Penetration", "kinetic", 360),
            CookingStage("Protein Denaturation", "kinetic", 720),
            CookingStage("Collagen Conversion", "kinetic", 2400),
        ),
        category="Non-Veg Curry",
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

    "Prawn Curry": DishProfile(
        name="Prawn Curry",
        food_mass_per_serving_kg=0.15,
        added_water_per_serving_kg=0.25,
        cp_food_kj_kgk=3.834,
        stages=(
            CookingStage("Frying / Sauteing", "frying", 240),
            CookingStage("Heating", "heating"),
            CookingStage("Heat Penetration", "kinetic", 120),
            CookingStage("Protein Denaturation", "kinetic", 180),
        ),
        category="Non-Veg Curry",
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

    "Palak Paneer": DishProfile(
        name="Palak Paneer",
        food_mass_per_serving_kg=0.18,
        added_water_per_serving_kg=0.10,
        cp_food_kj_kgk=3.609,
        stages=(
            CookingStage("Blanching (Spinach)", "kinetic", 180),
            CookingStage("Frying / Tempering", "frying", 300),
            CookingStage("Heating", "heating"),
            CookingStage("Gravy & Paneer Simmering", "kinetic", 600),
        ),
        category="Paneer Curry",
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

    # a short conductive-heating step before the simmer, cf. Aloo Matar.
    "Matar Paneer": DishProfile(
        name="Matar Paneer",
        food_mass_per_serving_kg=0.19,
        added_water_per_serving_kg=0.18,
        cp_food_kj_kgk=3.495,
        stages=(
            CookingStage("Frying / Tempering", "frying", 300),
            CookingStage("Heating", "heating"),
            CookingStage("Heat Penetration", "kinetic", 300),
            CookingStage("Gravy & Paneer Simmering", "kinetic", 720),
        ),
        category="Paneer Curry",
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

    "Chana Masala": DishProfile(
        name="Chana Masala",
        food_mass_per_serving_kg=0.20,
        added_water_per_serving_kg=0.20,
        cp_food_kj_kgk=3.438,
        stages=(
            CookingStage("Frying / Tempering", "frying", 300),
            CookingStage("Heating", "heating"),
            CookingStage("Heat Penetration", "kinetic", 300),
            CookingStage("Masala Simmering", "kinetic", 900),
        ),
        category="Legume (Boiled)",
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

    "Moong Dal": DishProfile(
        name="Moong Dal",
        food_mass_per_serving_kg=0.035,
        added_water_per_serving_kg=0.22,
        cp_food_kj_kgk=2.019,
        stages=(
            CookingStage("Frying (Light Tadka)", "frying", 120),
            CookingStage("Heating", "heating"),
            CookingStage("Heat Penetration", "kinetic", 300),
            CookingStage("Softening", "kinetic", 420),
        ),
        category="Lentil Dish",
        allowed_utensils=["CYLINDER", "PRESSURE_COOKER", "KADHAI"],
        recommended_utensils=["PRESSURE_COOKER"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.6
    ),

    "Methi Malai Matar": DishProfile(
        name="Methi Malai Matar",
        food_mass_per_serving_kg=0.15,
        added_water_per_serving_kg=0.10,
        cp_food_kj_kgk=3.591,
        stages=(
            CookingStage("Blanching (Methi)", "kinetic", 180),
            CookingStage("Frying / Tempering", "frying", 300),
            CookingStage("Heating", "heating"),
            CookingStage("Cream Gravy Simmering", "kinetic", 600),
        ),
        category="Vegetable Curry",
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

    "Cabbage Sabzi": DishProfile(
        name="Cabbage Sabzi",
        food_mass_per_serving_kg=0.12,
        added_water_per_serving_kg=0.02,
        cp_food_kj_kgk=3.978,
        stages=(
            CookingStage("Frying / Sauteing", "frying", 240),
            CookingStage("Heating", "heating"),
            CookingStage("Softening", "kinetic", 300),
        ),
        category="Dry Vegetable (Sabzi)",
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

    "Bhindi Masala": DishProfile(
        name="Bhindi Masala",
        food_mass_per_serving_kg=0.13,
        added_water_per_serving_kg=0.01,
        cp_food_kj_kgk=3.931,
        stages=(
            CookingStage("Frying / Sauteing", "frying", 420),
            CookingStage("Heating", "heating"),
            CookingStage("Softening", "kinetic", 240),
        ),
        category="Dry Vegetable (Sabzi)",
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

    # grain itself is the rate-limiting kinetic step either way.
    "Jeera Rice": DishProfile(
        name="Jeera Rice",
        food_mass_per_serving_kg=0.12,
        added_water_per_serving_kg=0.30,
        cp_food_kj_kgk=2.041,
        stages=(
            CookingStage("Tempering (Whole Cumin)", "frying", 90),
            CookingStage("Heating", "heating"),
            CookingStage("Hydration", "kinetic", 300),
            CookingStage("Starch Gelatinization", "kinetic", 600),
        ),
        category="Staple Grain",
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),

    "Vegetable Pulao": DishProfile(
        name="Vegetable Pulao",
        food_mass_per_serving_kg=0.16,
        added_water_per_serving_kg=0.28,
        cp_food_kj_kgk=2.557,
        stages=(
            CookingStage("Frying / Tempering (Veg + Whole Spices)", "frying", 240),
            CookingStage("Heating", "heating"),
            CookingStage("Hydration", "kinetic", 300),
            CookingStage("Starch Gelatinization", "kinetic", 600),
        ),
        category="Staple Grain",
        allowed_utensils=["CYLINDER", "KADHAI", "PRESSURE_COOKER"],
        recommended_utensils=["KADHAI"],
        forbidden_utensils=["TAWA"],
        max_fill_ratio=0.8
    ),
}

def get_dish_names():
    return sorted(FOOD_DB.keys())

def get_dish(dish_name):
    if dish_name not in FOOD_DB:
        raise KeyError("Unknown dish: " + dish_name)
    return FOOD_DB[dish_name]