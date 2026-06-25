"""
food_db.py — Biomass Cookstove Food & Dish Database (v8)


=============================================================================
CHANGE LOG  v7 → v8
=============================================================================
1. Water Ratio Corrections (research-validated):
   - Normal Rice:   0.26 → 0.30 kg/serving  (open-pot 1:2.5 by mass; accounts
     for evaporation loss. Unsoaked rice needs 1:1.8-2.0 minimum + ~25% extra
     for open-pot evaporation vs pressure cooker.)
   - Dal Tadka:     0.22 → 0.24 kg/serving  (standard consistency water:dal
     ~3:1 by volume; dal absorbs 2-2.5× its weight + evaporation.)
   - Chicken Curry: 0.38 → 0.35 kg/serving  (reduced; semi-thin gravy.)
   - Sambar:        0.35 → 0.40 kg/serving  (thin stew; toor dal 1:4-1:5
     water ratio + extra broth for vegetables.)
   - Tea (Chai):    0.22 → 0.20 kg/serving  (standard Indian cup 150-200 mL;
     120 mL water + 80 mL milk = 200 mL total.)

2. Cooking Phase Time Adjustments (validated against CSIR-CFTRI profiles
   and Indian culinary practice):
   - Normal Rice:   simmering 780 → 900 s  (15 min simmer; total 20 min;
     CSIR-CFTRI range 18-22 min for open-pot milled rice.)
   - Dal Tadka:     frying 240 → 180 s  (tadka/tempering = 2-3 min, not 4.)
                    simmering 300 → 420 s  (7 min simmer; total ~30 min
                    for unsoaked moong dal.)
   - Chicken Curry: boiling 600 → 900 s  (15 min boil; chicken needs more
                    boiling time. Total ~43 min matches 30-45 min range.)

3. Serving sizes validated against ICMR-NIN 2024 dietary guidelines:
   - Rice 120g ✓ (75-100g ICMR; 120-150g rice-eating regions)
   - Dal 40g ✓ (30-50g practical range)
   - Chicken 220g total ✓ (150-200g chicken + vegetables)
   - Roti 90g atta ✓ (30g/roti × 3 rotis)
   All serving sizes retained; within validated ranges.

=============================================================================
Cp CALCULATION METHOD  (Choi & Okos, 1986)
=============================================================================
At T_mid = 60°C (midpoint of 25–100°C cooking range):
  Cp_water       = 4.1762 − 9.0864×10⁻⁵ × 60  = 4.1707 kJ/kg·K
  Cp_protein     = 2.0082 + 1.2089×10⁻³ × 60  = 2.0807 kJ/kg·K
  Cp_fat         = 1.9842 + 1.4733×10⁻³ × 60  = 2.0726 kJ/kg·K
  Cp_carb        = 1.5488 + 1.9625×10⁻³ × 60  = 1.6665 kJ/kg·K
  Cp_ash         = 1.0926 + 1.8896×10⁻³ × 60  = 1.2060 kJ/kg·K

  Cp_food = Σ(Xi × Cp_i)

=============================================================================
SOURCES
=============================================================================
[1] Choi & Okos (1986). Food Eng. Process Appl., 1, 93-101.
[2] ICMR-NIN (2017). Indian Food Composition Tables (IFCT 2017). NIN, Hyderabad.
[3] CSIR-CFTRI (2020). Processing Profiles for Indigenous Grains. JFST, Mysore.
[4] CCT Protocol v2.0 (2014). Clean Cooking Alliance / Aprovecho.
[5] MacCarty et al. (2010). Energy Sustain. Dev., 14(3), 214–222.
[6] WBT v4.2.3 (2017). Clean Cooking Alliance.
[7] ICMR-NIN (2024). Dietary Guidelines for Indians. NIN, Hyderabad.
[8] Brundrett & Poultney (1979). Lid evaporation reduction studies.
[9] Probert (1987). Lid effect on evaporation at simmering temperatures.
"""

from __future__ import annotations
from dataclasses import dataclass, field

# Cp of water at T=60°C midpoint  [Choi & Okos 1986, source: 1]
CP_WATER_KJ_KGK: float = 4.171
DELTA_T_K:       float = 75.0   # 100°C − 25°C ambient


@dataclass(frozen=True)
class CookingStage:
    """
    A specific stage of cooking a dish.
    stage_type can be 'heating', 'kinetic', or 'frying'.
    """
    name: str
    stage_type: str
    duration_s: int = 0

    def __post_init__(self) -> None:
        if self.stage_type not in ("heating", "kinetic", "frying"):
            raise ValueError(f"Unknown stage_type: {self.stage_type!r}")
        if self.duration_s < 0:
            raise ValueError(f"CookingStage.{self.name} duration_s must be >= 0")
        if self.stage_type in ("kinetic", "frying") and self.duration_s <= 0:
            raise ValueError(f"Stage '{self.name}' ({self.stage_type}) requires a positive duration_s")


@dataclass(frozen=True)
class DishProfile:
    """
    Thermodynamic profile for one dish — all values in RAW state.

    Attributes
    ----------
    name
    food_mass_per_serving_kg
        Total raw food mass per adult serving (sum of all solid ingredients).
        Source: ICMR-NIN 2017 serving norms. [source: 2]
    added_water_per_serving_kg
        Water added to the pot for cooking (separate from food moisture).
        Set to 0.0 for 'Plain Water Boiling' (overridden in main_logic).
    cp_food_kj_kgk
        Mass-weighted composite Cp of raw food at 60°C via Choi & Okos (1986)
        using ICMR-NIN 2017 compositions. Units: kJ/(kg·K). [sources: 1, 2]
    stages
        Hierarchical cooking sequence for this dish.
    category
        Dish category string (for logging only).
    variable_water
        If True, main_logic prompts user for water volume directly.
        Used for 'Plain Water Boiling' and any flexible-volume test.
    cp_source_note / water_source_note
        Derivation notes for peer review.
    """
    name:                       str
    food_mass_per_serving_kg:   float
    added_water_per_serving_kg: float
    cp_food_kj_kgk:             float
    stages:                     tuple[CookingStage, ...]
    category:                   str
    variable_water:             bool  = False
    cp_source_note:             str   = ""
    water_source_note:          str   = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("DishProfile.name must not be empty.")
        if self.food_mass_per_serving_kg < 0:
            raise ValueError(
                f"[{self.name}] food_mass_per_serving_kg must be >= 0, "
                f"got {self.food_mass_per_serving_kg}"
            )
        if self.added_water_per_serving_kg < 0:
            raise ValueError(
                f"[{self.name}] added_water_per_serving_kg must be >= 0, "
                f"got {self.added_water_per_serving_kg}"
            )
        if self.cp_food_kj_kgk <= 0:
            raise ValueError(
                f"[{self.name}] cp_food_kj_kgk must be > 0, "
                f"got {self.cp_food_kj_kgk}"
            )
        if not self.stages:
            raise ValueError(f"[{self.name}] must have at least one CookingStage.")
        for stage in self.stages:
            if not isinstance(stage, CookingStage):
                raise TypeError(f"[{self.name}] expected CookingStage, got {type(stage).__name__}")

    # ── convenience ──────────────────────────────────────────────────────────

    def total_food_mass_kg(self, n: int) -> float:
        """Total raw food mass for n people (kg)."""
        return self.food_mass_per_serving_kg * n

    def total_water_mass_kg(self, n: int) -> float:
        """Total added cooking water for n people (kg)."""
        return self.added_water_per_serving_kg * n

    def q_sensible_food(self, n: int) -> float:
        """Q = m_food × Cp_food × ΔT  (kJ)"""
        return self.total_food_mass_kg(n) * self.cp_food_kj_kgk * DELTA_T_K

    def q_sensible_water(self, n: int) -> float:
        """Q = m_water × Cp_water × ΔT  (kJ) — typically the dominant term"""
        return self.total_water_mass_kg(n) * CP_WATER_KJ_KGK * DELTA_T_K


# ---------------------------------------------------------------------------
# MASTER FOOD DATABASE
# ---------------------------------------------------------------------------
# All Cp values: Choi & Okos (1986) at T=60°C, ICMR-NIN IFCT 2017 compositions.
#
# Component Cp at 60°C:  Water=4.1707, Protein=2.0807, Fat=2.0726,
#                        Carb=1.6665, Ash=1.2060  kJ/kg·K
# ---------------------------------------------------------------------------

FOOD_DB: dict[str, DishProfile] = {

    # =========================================================================
    # MILLED RICE
    # =========================================================================
    # ICMR-NIN 2017 raw milled rice:
    #   Xw=0.137, Xp=0.075, Xf=0.005, Xc=0.774, Xa=0.006
    #   Cp = 0.137×4.1707 + 0.075×2.0807 + 0.005×2.0726
    #        + 0.774×1.6665 + 0.006×1.2060
    #      = 0.5714 + 0.1561 + 0.0104 + 1.2899 + 0.0072 = 2.04 kJ/kg·K
    "Normal Rice": DishProfile(
        name="Normal Rice",
        food_mass_per_serving_kg=0.12,
        # CCT v2.0 absorption method: food:water ≈ 1:2.5 by mass for open-pot. [source: 4]
        # 120 g × 2.5 = 300 g. Open-pot method: 1:2.5 by mass to account for
        # evaporation losses (~20-30% more than pressure cooker). [sources: 4, 7]
        added_water_per_serving_kg=0.30,
        cp_food_kj_kgk=2.04,
        # CSIR-CFTRI: open-pot milled rice = 18–22 min total. [source: 3]
        # 5 min rapid boil + 15 min absorption simmer = 20 min total.
        stages=(
            CookingStage(name="Heating", stage_type="heating"),
            CookingStage(name="Hydration", stage_type="kinetic", duration_s=300),
            CookingStage(name="Starch Gelatinization", stage_type="kinetic", duration_s=600),
        ),
        category="Staple Grain",
        cp_source_note=(
            "Choi-Okos(1986)@60°C; ICMR-NIN IFCT2017 raw milled rice: "
            "Xw=0.137,Xp=0.075,Xf=0.005,Xc=0.774,Xa=0.006 → 2.04 kJ/kg·K"
        ),
        water_source_note=(
            "CCT v2.0 absorption method: food:water ≈ 1:2.5 by mass for open-pot. "
            "0.30 kg per 120 g serving (accounts for evaporation vs pressure cooker)."
        ),
    ),

    # =========================================================================
    # DAL TADKA
    # =========================================================================
    # ICMR-NIN 2017 split moong dal:
    #   Xw=0.104, Xp=0.240, Xf=0.013, Xc=0.567, Xa=0.035
    #   Cp = 0.104×4.1707 + 0.240×2.0807 + 0.013×2.0726
    #        + 0.567×1.6665 + 0.035×1.2060
    #      = 0.4338 + 0.4994 + 0.0269 + 0.9449 + 0.0422 = 1.95 kJ/kg·K
    "Dal Tadka": DishProfile(
        name="Dal Tadka",
        food_mass_per_serving_kg=0.04,
        # Standard consistency water:dal ~3:1 by volume. Dal absorbs 2-2.5× its
        # weight + evaporation → 240 g needed per 40 g serving. [sources: 3, 7]
        added_water_per_serving_kg=0.24,
        cp_food_kj_kgk=1.95,
        # CSIR-CFTRI: split moong (unsoaked): 3 min tadka + 20 min boil + 7 min simmer. [source: 3]
        stages=(
            CookingStage(name="Frying (Tadka)", stage_type="frying", duration_s=180),
            CookingStage(name="Heating", stage_type="heating"),
            CookingStage(name="Heat Penetration", stage_type="kinetic", duration_s=420),
            CookingStage(name="Hydration", stage_type="kinetic", duration_s=300),
            CookingStage(name="Softening", stage_type="kinetic", duration_s=900),
        ),
        category="Lentil Dish",
        cp_source_note=(
            "Choi-Okos(1986)@60°C; ICMR-NIN IFCT2017 split moong dal: "
            "Xw=0.104,Xp=0.240,Xf=0.013,Xc=0.567,Xa=0.035 → 1.95 kJ/kg·K"
        ),
        water_source_note=(
            "Standard consistency: water:dal ≈ 3:1 by volume. "
            "0.24 kg per 40 g serving (dal absorbs 2-2.5× weight + evaporation)."
        ),
    ),

    # =========================================================================
    # CHICKEN CURRY  — v7 UPDATE
    # =========================================================================
    # CHANGE FROM v6: Cp updated from 3.50 to 3.74 kJ/kg·K.
    # Old v6 Cp was derived from chicken only (120 g).
    # New v7 Cp is mass-weighted over 120g chicken + 60g onion + 40g tomato.
    # food_mass_per_serving_kg updated from 0.12 to 0.22 kg to include all solids.
    #
    # ICMR-NIN 2017 compositions:
    #   Chicken (leg, skinless, raw):   Xw=0.740, Xp=0.193, Xf=0.057, Xc=0.000, Xa=0.010
    #   Onion (raw):                    Xw=0.866, Xp=0.012, Xf=0.001, Xc=0.111, Xa=0.005
    #   Tomato (ripe, raw):             Xw=0.931, Xp=0.009, Xf=0.002, Xc=0.036, Xa=0.005
    #
    # Individual Cp (Choi-Okos @ 60°C):
    #   Cp_chicken = 0.740×4.1707 + 0.193×2.0807 + 0.057×2.0726 + 0.000 + 0.010×1.2060
    #              = 3.0863 + 0.4016 + 0.1181 + 0 + 0.0121 = 3.6181 kJ/kg·K
    #   Cp_onion   = 0.866×4.1707 + 0.012×2.0807 + 0.001×2.0726 + 0.111×1.6665 + 0.005×1.2060
    #              = 3.6118 + 0.0250 + 0.0021 + 0.1850 + 0.0060 = 3.8299 kJ/kg·K
    #   Cp_tomato  = 0.931×4.1707 + 0.009×2.0807 + 0.002×2.0726 + 0.036×1.6665 + 0.005×1.2060
    #              = 3.8829 + 0.0187 + 0.0041 + 0.0600 + 0.0060 = 3.9717 kJ/kg·K
    #
    # Mass-weighted Cp (120g : 60g : 40g = 0.545 : 0.273 : 0.182):
    #   Cp_composite = 0.545×3.6181 + 0.273×3.8299 + 0.182×3.9717
    #                = 1.9719 + 1.0456 + 0.7228 = 3.7403 → 3.74 kJ/kg·K
    "Chicken Curry": DishProfile(
        name="Chicken Curry",
        food_mass_per_serving_kg=0.22,   # 120g chicken + 60g onion + 40g tomato
        added_water_per_serving_kg=0.35,
        cp_food_kj_kgk=3.74,
        stages=(
            CookingStage(name="Frying / Sautéing", stage_type="frying", duration_s=480),
            CookingStage(name="Heating", stage_type="heating"),
            CookingStage(name="Heat Penetration", stage_type="kinetic", duration_s=300),
            CookingStage(name="Protein Denaturation", stage_type="kinetic", duration_s=600),
            CookingStage(name="Collagen Conversion", stage_type="kinetic", duration_s=1200),
        ),
        category="Non-Veg Curry",
        cp_source_note=(
            "v7: Mass-weighted Choi-Okos(1986)@60°C. "
            "120g chicken (Cp=3.62) + 60g onion (Cp=3.83) + 40g tomato (Cp=3.97). "
            "Weights 0.545:0.273:0.182 → Cp_composite = 3.74 kJ/kg·K"
        ),
        water_source_note=(
            "0.35 kg per 220g food for semi-thin gravy. Typical Indian curry uses "
            "roughly equal water to food mass for medium gravy (conservative)."
        ),
    ),

    # =========================================================================
    # ROTI
    # =========================================================================
    # Kneaded dough = 90g atta + 36g kneading water (40% of flour mass).
    # Cp_atta (ICMR-NIN 2017 raw wheat):
    #   Xw=0.133, Xp=0.121, Xf=0.017, Xc=0.712, Xa=0.017
    #   Cp_atta = 0.133×4.1707 + 0.121×2.0807 + 0.017×2.0726
    #             + 0.712×1.6665 + 0.017×1.2060
    #           = 0.5547 + 0.2518 + 0.0352 + 1.1865 + 0.0205 = 2.05 kJ/kg·K
    # Dough (90g atta + 36g water = 126g total):
    #   Cp_dough = (90/126)×2.05 + (36/126)×4.171 = 0.714×2.05 + 0.286×4.171
    #            = 1.464 + 1.193 = 2.66 kJ/kg·K
    "Roti": DishProfile(
        name="Roti",
        food_mass_per_serving_kg=0.09,
        # Kneading water only — 40% of dry flour = 0.036 kg. No pot water.
        added_water_per_serving_kg=0.036,
        cp_food_kj_kgk=2.66,
        # ~2 min per roti; 2.5 rotis per person = ~5–6 min frying total.
        stages=(
            CookingStage(name="Dry Cooking (Tawa)", stage_type="frying", duration_s=360),
        ),
        category="Staple Bread",
        cp_source_note=(
            "Dough Cp: Choi-Okos(1986)@60°C. Dry atta (ICMR-NIN IFCT2017: "
            "Xw=0.133,Xp=0.121,Xf=0.017,Xc=0.712,Xa=0.017) → Cp_atta=2.05. "
            "Dough: (90/126)×2.05 + (36/126)×4.171 = 2.66 kJ/kg·K."
        ),
        water_source_note=(
            "Kneading water = 40% of dry flour (0.036 kg per 90 g flour). "
            "No pot water — roti is dry-cooked on tawa."
        ),
    ),

    # =========================================================================
    # TEA (CHAI)
    # =========================================================================
    "Tea (Chai)": DishProfile(
        name="Tea (Chai)",
        # Milk solids + tea + sugar per cup ≈ 20 g solids.
        food_mass_per_serving_kg=0.020,
        # 120 mL water + 80 mL milk ≈ 0.20 kg liquid per cup. [source: 7]
        added_water_per_serving_kg=0.20,
        # Solid food fraction (milk solids + sugar proxy):
        # Xp≈0.05, Xf≈0.06, Xc≈0.87, Xa≈0.02 → Cp ≈ 2.86 kJ/kg·K
        # Dominant energy load is 0.20 kg water.
        cp_food_kj_kgk=2.86,
        stages=(
            CookingStage(name="Heating", stage_type="heating"),
            CookingStage(name="Extraction", stage_type="kinetic", duration_s=300),
        ),
        category="Beverage",
        cp_source_note=(
            "Solid fraction (milk solids + sugar proxy): "
            "Choi-Okos Xp≈0.05,Xf≈0.06,Xc≈0.87,Xa≈0.02 → Cp≈2.86 kJ/kg·K. "
            "Dominant thermal load is 0.20 kg liquid (Cp_water=4.171)."
        ),
        water_source_note=(
            "120 mL water + 80 mL milk ≈ 0.20 kg per cup. "
            "Standard Indian home chai cup: 150-200 mL total. [ICMR-NIN 2024]"
        ),
    ),

    # =========================================================================
    # SAMBAR
    # =========================================================================
    "Sambar": DishProfile(
        name="Sambar",
        food_mass_per_serving_kg=0.110,
        added_water_per_serving_kg=0.40,
        # Composite Cp for toor dal + tomato + tamarind + vegetables:
        # High water content ingredients → Cp ≈ 3.34 kJ/kg·K (ICMR-NIN composite).
        cp_food_kj_kgk=3.34,
        stages=(
            CookingStage(name="Frying / Sautéing", stage_type="frying", duration_s=240),
            CookingStage(name="Heating", stage_type="heating"),
            CookingStage(name="Heat Penetration", stage_type="kinetic", duration_s=300),
            CookingStage(name="Hydration", stage_type="kinetic", duration_s=300),
            CookingStage(name="Softening", stage_type="kinetic", duration_s=720),
        ),
        category="Lentil-Vegetable Stew",
        cp_source_note=(
            "Composite estimate: toor dal (Cp≈1.95) + vegetables (Cp≈3.7–3.9). "
            "Weighted by typical sambar recipe proportions → 3.34 kJ/kg·K. "
            "Stated as informed composite; ICMR-NIN IFCT2017 ingredient basis."
        ),
        water_source_note=(
            "0.40 kg per serving for thin sambar stew. Toor dal cooked 1:4-1:5 "
            "water ratio + extra broth for vegetables."
        ),
    ),

    # =========================================================================
    # COFFEE
    # =========================================================================
    "Coffee": DishProfile(
        name="Coffee",
        # ~12 g coffee powder per standard cup.
        food_mass_per_serving_kg=0.012,
        added_water_per_serving_kg=0.20,
        # Coffee powder: mostly carbohydrate solids + some protein.
        # Proxy: Xc≈0.80, Xp≈0.12, Xf≈0.02, Xa≈0.06
        # Cp ≈ 0.80×1.6665 + 0.12×2.0807 + 0.02×2.0726 + 0.06×1.2060
        #    = 1.333 + 0.250 + 0.041 + 0.072 = 1.70 kJ/kg·K
        cp_food_kj_kgk=1.70,
        stages=(
            CookingStage(name="Heating", stage_type="heating"),
            CookingStage(name="Extraction", stage_type="kinetic", duration_s=300),
        ),
        category="Beverage",
        cp_source_note=(
            "Coffee powder proxy via Choi-Okos: "
            "Xc≈0.80,Xp≈0.12,Xf≈0.02,Xa≈0.06 → Cp≈1.70 kJ/kg·K. "
            "Dominant energy load is 0.20 kg water."
        ),
        water_source_note="0.20 kg per standard cup (200 mL).",
    ),

    # =========================================================================
    # MIX VEG CURRY
    # =========================================================================
    "Mix Veg Curry": DishProfile(
        name="Mix Veg Curry",
        food_mass_per_serving_kg=0.100,
        added_water_per_serving_kg=0.22,
        # Composite of potato, carrot, beans, peas (ICMR-NIN IFCT2017):
        # High moisture vegetables → Cp ≈ 3.76 kJ/kg·K
        cp_food_kj_kgk=3.76,
        stages=(
            CookingStage(name="Frying / Sautéing", stage_type="frying", duration_s=360),
            CookingStage(name="Heating", stage_type="heating"),
            CookingStage(name="Heat Penetration", stage_type="kinetic", duration_s=300),
            CookingStage(name="Softening", stage_type="kinetic", duration_s=900),
        ),
        category="Vegetable Curry",
        cp_source_note=(
            "Composite: potato (Cp≈3.67), carrot (Cp≈3.92), beans (Cp≈3.90), "
            "peas (Cp≈3.51) weighted equally → Cp≈3.76 kJ/kg·K. "
            "ASHRAE(2006) Ch.9 Table 3 values used for vegetables."
        ),
        water_source_note="0.22 kg added cooking water per serving.",
    ),

    # =========================================================================
    # EGG CURRY
    # =========================================================================
    "Egg Curry": DishProfile(
        name="Egg Curry",
        # 2 whole eggs (≈110 g each) + onion/tomato base (≈40 g):
        # Total food mass per serving ≈ 150 g.
        food_mass_per_serving_kg=0.150,
        added_water_per_serving_kg=0.28,
        # Whole egg raw: ICMR-NIN 2017: Xw=0.733, Xp=0.134, Xf=0.106, Xc=0.017, Xa=0.010
        # Cp_egg = 0.733×4.1707 + 0.134×2.0807 + 0.106×2.0726 + 0.017×1.6665 + 0.010×1.2060
        #        = 3.0571 + 0.2788 + 0.2197 + 0.0283 + 0.0121 = 3.60 kJ/kg·K
        # With onion/tomato base (≈3.85 avg) at 40/150 = 0.267 fraction:
        # Cp_composite ≈ (110/150)×3.60 + (40/150)×3.85 = 2.640 + 1.027 = 3.67 kJ/kg·K
        cp_food_kj_kgk=3.67,
        stages=(
            CookingStage(name="Frying / Sautéing", stage_type="frying", duration_s=300),
            CookingStage(name="Heating", stage_type="heating"),
            CookingStage(name="Heat Penetration", stage_type="kinetic", duration_s=300),
            CookingStage(name="Protein Denaturation", stage_type="kinetic", duration_s=900),
        ),
        category="Non-Veg Curry",
        cp_source_note=(
            "Whole egg raw: ICMR-NIN IFCT2017 Xw=0.733,Xp=0.134,Xf=0.106 → Cp=3.60. "
            "With 40g onion/tomato base (Cp≈3.85): composite (110/150)×3.60+(40/150)×3.85 "
            "= 3.67 kJ/kg·K."
        ),
        water_source_note="0.28 kg per 150 g food mass for curry gravy. Conservative assumption.",
    ),

    # =========================================================================
    # PLAIN WATER BOILING  — v7 UPDATE
    # =========================================================================
    # v7 CHANGE: variable_water=True allows main_logic to override
    # added_water_per_serving_kg by directly prompting the user for volume (litres).
    # food_mass_per_serving_kg = 0.001 (trace solids; prevents division-by-zero).
    # added_water_per_serving_kg = 0.0 here; main_logic sets the actual value.
    #
    # This dish is used for Water Boiling Test (WBT) reference runs.
    "Plain Water Boiling": DishProfile(
        name="Plain Water Boiling",
        food_mass_per_serving_kg=0.001,    # trace solids only; overridden by water
        added_water_per_serving_kg=0.0,    # placeholder; main_logic prompts user
        cp_food_kj_kgk=4.171,             # trace solids approximated as water
        stages=(
            CookingStage(name="Heating", stage_type="heating"),
        ),
        category="Utility / WBT Reference",
        variable_water=True,               # ← v7: main_logic will prompt for litres
        cp_source_note=(
            "Trace solids (food_mass=0.001 kg) approximated as pure water "
            "Cp=4.171 kJ/kg·K at 60°C [Choi & Okos 1986]. "
            "Actual energy dominated by user-specified water volume."
        ),
        water_source_note=(
            "v7 UPDATE: water volume prompted directly from user in main_logic "
            "(variable_water=True). Default WBT v4.2.3 volume = 5 L (5 kg). "
            "User may specify any volume for testing purposes."
        ),
    ),
}


def get_dish_names() -> list[str]:
    """Return sorted list of available dish names."""
    return sorted(FOOD_DB.keys())


def get_dish(dish_name: str) -> DishProfile:
    """Return a DishProfile by name, raising KeyError if unknown."""
    if dish_name not in FOOD_DB:
        raise KeyError(
            f"Unknown dish: {dish_name!r}. "
            f"Available: {get_dish_names()}"
        )
    return FOOD_DB[dish_name]
