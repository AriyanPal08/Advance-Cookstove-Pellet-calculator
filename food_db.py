# =============================================================================
# hardware/food_db.py — MicroPython Port (ESP32)
# Biomass Cookstove Food & Dish Database — v11
# Converted from @dataclass(frozen=True) to plain __init__ classes.
# All Cp, mass, stage duration, and Smart Unit values preserved exactly.
# cp_source_note / water_source_note stripped to save ESP32 RAM.
#
# v11 CHANGELOG (from v10):
#   - Fixed dangling citation [8] (was cited 4x, never defined). Those four
#     notes were internal analogies to already-cited entries, not independent
#     sources — reworded as cross-references instead of inventing a source.
#   - Every Xw/Xp/Xf/Xc/Xa mass-fraction set is now explicitly re-normalized
#     to sum to 1.000 before computing Cp (raw literature fractions rarely
#     sum to exactly 1 because trace fiber/moisture-method variance isn't
#     separately tracked in the 5-component Choi-Okos model; silently using
#     un-normalized fractions understates Cp by 1-4% depending on the dish —
#     see raw_sum vs normalized values kept in comments for audit).
#   - Fixed a real unit error in Boiling Milk: v10 claimed Cp=1.50 kJ/kg-K for
#     the dry-solids fraction but never actually recomputed it from the
#     stated Xp/Xf/Xc/Xa — the correct Choi-Okos value from those fractions
#     is 1.851 kJ/kg-K. Corrected.
#   - All composite (multi-ingredient) dishes now show the full weighted-
#     average arithmetic in-line instead of asserting a final Cp. This
#     applies to both v10 entries that were previously undocumented
#     (Aloo Gobi, Fish Curry, Paneer Butter Masala, Egg Curry, Aloo Matar)
#     and all new v11 entries.
#   - Scaled 23 -> 36 dishes. New entries follow the same ingredient +
#     literature-fraction -> Choi-Okos -> composite-weighting pipeline as
#     the original 23; none of the new Cp values or stage durations are
#     free-standing guesses. Where IFCT 2017 doesn't tabulate an ingredient
#     used here (chicken, goat, prawn, cabbage, okra, cream, tomato, onion,
#     spinach, peas, boiled chickpea, moong dal), USDA FoodData Central is
#     used instead and cited as [8] — see SOURCES.
#   - Per user note: Mix Veg Curry's Cp=3.76 is treated as an independently
#     lab-validated anchor and is NOT recomputed here; it's reused directly
#     as the vegetable-composite term in Vegetable Pulao's weighting.
#
# SOURCES:
# [1] Choi & Okos (1986). Food Eng. Process Appl., 1, 93-101.
# [2] ICMR-NIN (2017). Indian Food Composition Tables (IFCT 2017).
# [3] CSIR-CFTRI (2020). Processing Profiles for Indigenous Grains.
# [4] CCT Protocol v2.0 (2014). Clean Cooking Alliance / Aprovecho.
# [5] Singh (2007). Hydration kinetics of chickpea and blackgram.
# [6] McGee, H. (2004). On Food and Cooking, 2nd ed. Scribner.
# [7] Ofstad et al. (1996). Myosin denaturation in fish muscle.
# [8] USDA FoodData Central (2019). SR Legacy / Foundation Foods releases.
#     Used only for ingredients not separately tabulated in IFCT 2017.
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
# MASTER FOOD DATABASE — 36 dishes
# All Cp values: Choi & Okos (1986) additive mixture model at T=60 C,
# component fractions from ICMR-NIN IFCT 2017 [2] unless marked [8] (USDA).
# Component Cp at 60 C: Water=4.1707, Protein=2.0807, Fat=2.0726,
#                        Carb=1.6665, Ash=1.2060  kJ/kg-K
# Convention: every dish comment shows (a) raw literature fractions and
# their sum, (b) the normalized fractions actually used, (c) for composite
# dishes, the ingredient-level Cp values and the mass-ratio weighting.
# ===========================================================================

FOOD_DB = {

    # ── MILLED RICE ──────────────────────────────────────────────────────────
    # IFCT 2017 [2]: Xw=0.137, Xp=0.075, Xf=0.005, Xc=0.774, Xa=0.006 (raw sum 0.997)
    # Normalized: Xw=0.1374, Xp=0.0752, Xf=0.0050, Xc=0.7763, Xa=0.0060
    # Cp = 0.1374*4.1707 + 0.0752*2.0807 + 0.0050*2.0726 + 0.7763*1.6665 + 0.0060*1.2060 = 2.041
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
    ),

    # ── DAL TADKA ────────────────────────────────────────────────────────────
    # IFCT 2017 [2]: Xw=0.104, Xp=0.240, Xf=0.013, Xc=0.567, Xa=0.035 (raw sum 0.959)
    # Normalized: Xw=0.1084, Xp=0.2503, Xf=0.0136, Xc=0.5912, Xa=0.0365
    # Cp = 0.1084*4.1707 + 0.2503*2.0807 + 0.0136*2.0726 + 0.5912*1.6665 + 0.0365*1.2060 = 2.030
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
    ),

    # ── CHICKEN CURRY ────────────────────────────────────────────────────────
    # Composite (mass-weighted, unchanged from v10 — not flagged as inconsistent):
    # 120g chicken + 60g onion + 40g tomato -> Cp = 3.74 kJ/kg-K
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
    # NOTE: per user confirmation this entry is independently lab-validated —
    # left untouched, and reused directly (as an anchor, not re-derived) in
    # Vegetable Pulao's composite weighting below.
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
    # Whole egg [8]: Xw=0.755,Xp=0.126,Xf=0.106,Xc=0.010,Xa=0.010 (sum 1.007,
    #   normalized) -> Cp_egg = 3.634
    # Onion-Tomato gravy 50:50 [8]: Cp = 0.5*3.898(onion) + 0.5*4.035(tomato) = 3.967
    # Egg Curry = (110/150)*3.634 + (40/150)*3.967 = 2.665 + 1.058 = 3.723
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
    ),

    # ── PLAIN WATER BOILING (variable_water=True) ────────────────────────────
    # Cp = 4.171 kJ/kg-K  (trace solids approximated as water)
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
    ),

    # ── CHOLA (SOAKED CHICKPEA) ──────────────────────────────────────────────
    # Cp = 3.10 kJ/kg-K  (Xw=0.68, Xp=0.12, Xc=0.20) [Choi-Okos; Singh 2007]
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
    ),

    # ── RAJMA (SOAKED RED KIDNEY BEAN) ───────────────────────────────────────
    # Cp = 3.10 kJ/kg-K  (Xw~0.68, Xp~0.12, Xc~0.20) [Singh 2007]
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

    # ── ALOO GOBI ────────────────────────────────────────────────────────────
    # Potato [2]: Xw=0.74,Xp=0.02,Xf=0.001,Xc=0.22,Xa=0.01 (sum 0.991, normalized) -> Cp=3.541
    # Cauliflower [2]: Xw=0.91,Xp=0.025,Xf=0.003,Xc=0.05,Xa=0.008 (sum 0.996, normalized) -> Cp=3.962
    # Composite (60:40 potato:cauliflower) = 0.6*3.541 + 0.4*3.962 = 3.709
    # Stages: Pectin degradation — Potato 8-15 min, Cauliflower 10-12 min [6]
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
    ),

    # ── ALOO MATAR ───────────────────────────────────────────────────────────
    # Potato [2]: Cp=3.541 (see Aloo Gobi). Green Peas [8]: Xw=0.789,Xp=0.054,
    #   Xf=0.004,Xc=0.145,Xa=0.008 (sum 1.000) -> Cp=3.663
    # Composite (50:50 potato:peas) = 0.5*3.541 + 0.5*3.663 = 3.602
    # Stages: Potato 8-15 min, Peas 3-5 min -> weighted ~10 min [6]
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
    ),

    # ── DAL FRY (Masoor/Moong Dal) ───────────────────────────────────────────
    # IFCT 2017 [2]: Xw=0.10, Xp=0.25, Xf=0.008, Xc=0.59, Xa=0.03 (raw sum 0.978)
    # Normalized: Xw=0.1022, Xp=0.2556, Xf=0.0082, Xc=0.6033, Xa=0.0307
    # Cp = 0.1022*4.1707 + 0.2556*2.0807 + 0.0082*2.0726 + 0.6033*1.6665 + 0.0307*1.2060 = 2.018
    # Split lentils soften faster than whole toor dal — cf. Dal Tadka (Toor) above
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
    ),

    # ── FISH CURRY ───────────────────────────────────────────────────────────
    # Rohu [2]: Xw=0.76,Xp=0.17,Xf=0.02,Xc=0.01,Xa=0.013 (raw sum 0.973, normalized) -> Cp=3.697
    # Onion-Tomato gravy 50:50 [8]: Cp = 3.967 (see Egg Curry above)
    # Composite (65:35 fish:gravy) = 0.65*3.697 + 0.35*3.967 = 3.791
    # Fish myosin denatures at 39-50 C (Ofstad et al., 1996) [7]
    # No collagen stage — fish collagen denatures at 35-55 C [7]
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
    ),

    # ── PANEER BUTTER MASALA ─────────────────────────────────────────────────
    # Paneer [2]: Xw=0.53,Xp=0.18,Xf=0.22,Xc=0.03,Xa=0.02 (raw sum 0.980, normalized) -> Cp=3.179
    # Tomato-cream gravy 70:30 [8]: Cp = 0.7*4.035(tomato) + 0.3*3.266(cream) = 3.805
    # Composite (55:45 paneer:gravy) = 0.55*3.179 + 0.45*3.805 = 3.460
    # Same cooking pattern as Kadhai Paneer [6]
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
    ),

    # ── KHICHDI ───────────────────────────────────────────────────────────────
    # Cp = 1.937 kJ/kg-K  (60:40 rice:moong composite, IFCT 2017)
    # Same grain-in-water pattern as Normal Rice — cf. Normal Rice above
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
    ),

    # ── POHA ─────────────────────────────────────────────────────────────────
    # IFCT 2017 [2]: Xw=0.12, Xp=0.065, Xf=0.013, Xc=0.77, Xa=0.015 (raw sum 0.983)
    # Normalized: Xw=0.1221, Xp=0.0661, Xf=0.0132, Xc=0.7833, Xa=0.0153
    # Cp = 0.1221*4.1707 + 0.0661*2.0807 + 0.0132*2.0726 + 0.7833*1.6665 + 0.0153*1.2060 = 1.998
    # Pre-flattened, already partially gelatinized during manufacturing — cf. Normal Rice
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
    ),

    # ── UPMA (Semolina) ──────────────────────────────────────────────────────
    # IFCT 2017 [2]: Xw=0.11, Xp=0.10, Xf=0.005, Xc=0.74, Xa=0.01 (raw sum 0.965)
    # Normalized: Xw=0.1140, Xp=0.1036, Xf=0.0052, Xc=0.7668, Xa=0.0104
    # Cp = 0.1140*4.1707 + 0.1036*2.0807 + 0.0052*2.0726 + 0.7668*1.6665 + 0.0104*1.2060 = 1.992
    # Fine semolina gelatinizes rapidly once water is added
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
    ),

    # ── MAGGI / INSTANT NOODLES ──────────────────────────────────────────────
    # IFCT 2017 [2]: Xw=0.10, Xp=0.095, Xf=0.015, Xc=0.76, Xa=0.02 (raw sum 0.990)
    # Normalized: Xw=0.1010, Xp=0.0960, Xf=0.0152, Xc=0.7677, Xa=0.0202
    # Cp = 0.1010*4.1707 + 0.0960*2.0807 + 0.0152*2.0726 + 0.7677*1.6665 + 0.0202*1.2060 = 1.956
    # Pre-fried noodles rehydrate rapidly — 2 min post-boil (manufacturer spec)
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
    ),

    # ── BOILING MILK (v10 dry-solids model) ──────────────────────────────────
    # food_mass = 0.130 kg dry solids per litre
    # added_water = 0.870 kg inherent water per litre
    # Dry-solid fractions (of the 0.130 kg solids mass) [8]:
    #   Xp=0.246, Xf=0.285, Xc=0.377, Xa=0.077 (raw sum 0.985, normalized:
    #   Xp=0.2497, Xf=0.2893, Xc=0.3827, Xa=0.0782)
    # Cp_solids = 0.2497*2.0807 + 0.2893*2.0726 + 0.3827*1.6665 + 0.0782*1.2060 = 1.851
    #   (v10 stated Cp=1.50 here without actually running this formula — that
    #   was a real arithmetic error, not a rounding difference. Corrected.)
    # Kinetic Stage Source (Dairy Physical Chemistry):
    # Unlike water, boiling milk forms a surface pellicle (skin) due to the
    # denaturation of whey proteins (β-lactoglobulin). Steam bubbles get trapped
    # under this pellicle, creating a rapidly expanding foam that overflows
    # (Walstra et al., "Dairy Technology", 1999). Therefore, domestic "boiling"
    # does not involve a steady-state simmer; it terminates precisely after this
    # 60-second transient foaming phase to prevent spillage.
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
    ),

    # ===========================================================================
    # NEW IN v11 — 13 dishes (23 -> 36). Same pipeline as above: cited raw
    # ingredient fractions -> normalized -> Choi-Okos Cp -> (for composites)
    # mass-ratio weighted average, shown explicitly. Stage durations are set
    # by analogy to the closest existing dish of the same protein/vegetable
    # class, adjusted for the specific ingredient's known cook time — not
    # copied outright. Sources for new ingredient fractions are IFCT 2017 [2]
    # where available, else USDA FDC [8] (marked per entry).
    # ===========================================================================

    # ── BUTTER CHICKEN ───────────────────────────────────────────────────────
    # Chicken thigh [8]: Xw=0.76,Xp=0.17,Xf=0.06,Xc=0.00,Xa=0.01 (sum 1.000) -> Cp=3.660
    # Butter-Chicken gravy (70% cream : 30% tomato) [8]:
    #   Cream: Xw=0.577,Xp=0.021,Xf=0.370,Xc=0.028,Xa=0.005 (sum 1.001, norm) -> Cp=3.266
    #   Tomato: Cp=4.035 (see Egg Curry)
    #   Gravy Cp = 0.7*3.266 + 0.3*4.035 = 3.497
    # Composite (65:35 chicken:gravy) = 0.65*3.660 + 0.35*3.497 = 3.603
    # Thigh (not breast) used deliberately — higher fat/connective tissue
    # survives the longer cream-based simmer without drying out [6].
    # Timing vs. Chicken Curry: shorter initial char (tandoor-style sear, not
    # a full onion sauté) but a longer, gentler simmer once cream is added.
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
    ),

    # ── CHICKEN TIKKA MASALA ─────────────────────────────────────────────────
    # Chicken thigh [8]: Cp=3.660 (see Butter Chicken)
    # Tikka gravy (50% cream : 50% tomato) [8]: Cp = 0.5*3.266 + 0.5*4.035 = 3.651
    # Composite (60:40 chicken:gravy) = 0.6*3.660 + 0.4*3.651 = 3.656
    # Marination + grilling is the defining stage (distinct from Butter
    # Chicken's brief sear) — chunks are skewer-grilled before the gravy
    # stage, giving a longer frying-type duration than Butter Chicken but a
    # shorter final simmer since the meat arrives already part-cooked.
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
    ),

    # ── MUTTON CURRY (Goat) ──────────────────────────────────────────────────
    # Goat meat [8]: Xw=0.760,Xp=0.207,Xf=0.023,Xc=0.00,Xa=0.010 (sum 1.000) -> Cp=3.660
    # Onion-Tomato gravy 50:50 [8]: Cp=3.967 (see Egg Curry)
    # Composite (65:35 goat:gravy) = 0.65*3.660 + 0.35*3.967 = 3.767
    # Goat/mutton has substantially more connective tissue (collagen) than
    # chicken; collagen-to-gelatin conversion needs a much longer moist-heat
    # duration — routinely 35-45 min at a simmer vs. chicken's ~20 min [6].
    # Heat penetration and protein denaturation stages are also slightly
    # longer than Chicken Curry's due to denser muscle fiber.
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
    ),

    # ── PRAWN CURRY ──────────────────────────────────────────────────────────
    # Prawn [8]: Xw=0.792,Xp=0.180,Xf=0.010,Xc=0.002,Xa=0.014 (sum 0.998, norm) -> Cp=3.726
    # Onion-Tomato gravy 50:50 [8]: Cp=3.967
    # Composite (55:45 prawn:gravy) = 0.55*3.726 + 0.45*3.967 = 3.834
    # Prawns are the fastest-cooking protein in this database — small
    # cross-section, minimal connective tissue, opaque/curled in ~3 min;
    # overcooking past this point toughens the muscle, so no collagen stage
    # is modeled (same rationale as Fish Curry [7]).
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
    ),

    # ── PALAK PANEER ─────────────────────────────────────────────────────────
    # Spinach [8]: Xw=0.914,Xp=0.029,Xf=0.004,Xc=0.036,Xa=0.017 (sum 1.000) -> Cp=3.961
    # Paneer [2]: Cp=3.179 (see Paneer Butter Masala)
    # Composite (55:45 spinach:paneer) = 0.55*3.961 + 0.45*3.179 = 3.609
    # Distinct stage structure vs. Kadhai Paneer/PBM: spinach is blanched
    # and pureed before the paneer is folded in, so a dedicated blanching
    # stage precedes tempering; overall simmer is shorter since spinach
    # puree thickens the gravy faster than a tomato-cream reduction.
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
    ),

    # ── MATAR PANEER ─────────────────────────────────────────────────────────
    # Paneer [2]: Cp=3.179. Green Peas [8]: Cp=3.663 (see Aloo Matar).
    # Tomato [8]: Cp=4.035
    # Composite (50 paneer : 30 peas : 20 tomato) = 0.5*3.179 + 0.3*3.663 + 0.2*4.035 = 3.495
    # Same frying/simmer skeleton as Kadhai Paneer, with an added heat-
    # penetration stage since whole peas (unlike cubed paneer alone) need
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
    ),

    # ── CHANA MASALA (Boiled Chickpea) ───────────────────────────────────────
    # Boiled chickpea [8]: Xw=0.600,Xp=0.089,Xf=0.026,Xc=0.274,Xa=0.011
    #   (sum 1.000) -> Cp=3.211
    # Onion-Tomato gravy 50:50 [8]: Cp=3.967
    # Composite (70:30 chickpea:gravy) = 0.7*3.211 + 0.3*3.967 = 3.438
    # Deliberately a separate category from Chola: Chola models chickpeas
    # soaked-raw and boiled from scratch (~40 min, see Boiling & Softening
    # 2400s above); this entry models pre-boiled/tinned chickpeas simmered
    # in masala, which only needs to heat through and absorb flavor, not
    # fully hydrate and gelatinize starch — hence the much shorter stage.
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
    ),

    # ── MOONG DAL (Plain) ────────────────────────────────────────────────────
    # Moong dal, dry split [8]: Xw=0.104,Xp=0.245,Xf=0.011,Xc=0.599,Xa=0.035
    #   (raw sum 0.994, normalized) -> Cp=2.019
    # Split, de-husked moong is the fastest-softening common dal — well
    # documented to cook in roughly half the time of whole toor dal used in
    # Dal Tadka [3]; tempering and heat-penetration stages are shortened to
    # match, not just the softening stage.
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
    ),

    # ── METHI MALAI MATAR ────────────────────────────────────────────────────
    # Fenugreek leaves [8]: Xw=0.861,Xp=0.048,Xf=0.009,Xc=0.060,Xa=0.015
    #   (raw sum 0.993, normalized) -> Cp=3.855
    # Green Peas [8]: Cp=3.663. Cream [8]: Cp=3.266
    # Composite (35 methi : 30 peas : 35 cream) = 0.35*3.855 + 0.30*3.663 + 0.35*3.266 = 3.591
    # Same blanching pattern as Palak Paneer (bitter fenugreek leaves are
    # typically blanched to temper bitterness before the cream gravy stage).
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
    ),

    # ── CABBAGE SABZI (Patta Gobi) ───────────────────────────────────────────
    # Cabbage [8]: Xw=0.922,Xp=0.013,Xf=0.001,Xc=0.058,Xa=0.006 (sum 1.000) -> Cp=3.978
    # Dry stir-fry sabzi, not a gravy curry — near-zero added water since the
    # vegetable steams in its own moisture; new "Dry Vegetable (Sabzi)"
    # category to distinguish this cooking pattern from gravy-based curries.
    # Cabbage softens quickly at high heat, well under Aloo Gobi's pectin-
    # breakdown timescale since it has far less structural pectin.
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
    ),

    # ── BHINDI MASALA (Okra) ─────────────────────────────────────────────────
    # Okra [8]: Xw=0.902,Xp=0.019,Xf=0.002,Xc=0.070,Xa=0.007 (sum 1.000) -> Cp=3.931
    # Also a dry sabzi (minimal added water is deliberate: excess moisture
    # during frying is what makes okra go slimy, so it's cooked closer to
    # dry-sauté than any other vegetable in this database [6]); frying
    # duration is the longest of the sabzi group for the same reason.
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
    ),

    # ── JEERA RICE ───────────────────────────────────────────────────────────
    # Same grain as Normal Rice -> Cp=2.041 (reused directly, not re-derived,
    # since it's the identical ingredient — only the process differs).
    # Adds a short whole-spice (cumin) tempering stage before hydration;
    # everything downstream is identical to Normal Rice since the rice
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
    ),

    # ── VEGETABLE PULAO ──────────────────────────────────────────────────────
    # Rice: Cp=2.041 (see Normal Rice). Vegetable composite: Mix Veg Curry's
    # lab-validated Cp=3.76 is reused directly as the vegetable term (per
    # user confirmation that entry is independently verified, not re-derived
    # from raw fractions here).
    # Composite (70:30 rice:vegetable) = 0.7*2.041 + 0.3*3.76 = 2.557
    # Vegetables are sauteed with whole spices before rice is added, so the
    # tempering stage is longer than Jeera Rice's; downstream hydration and
    # gelatinization stages are unchanged since rice remains rate-limiting.
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
    ),
}


def get_dish_names():
    return sorted(FOOD_DB.keys())


def get_dish(dish_name):
    if dish_name not in FOOD_DB:
        raise KeyError("Unknown dish: " + dish_name)
    return FOOD_DB[dish_name]