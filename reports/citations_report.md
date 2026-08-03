# Cookstove Simulator: Exact Sources and Usage Report

This document outlines the exact citation for every scientific claim, standard, and manufacturer specification made in the four core simulator files (`food_db.py`, `pellet_db.py`, `utensil_db.py`, and `main_logic.py`). It strictly details the source and exactly how it is applied in the physics models.

---

## 1. Thermodynamic Food Database (`food_db.py`)

**1. Choi, Y., & Okos, M. R. (1986). Effects of temperature and composition on the thermal properties of foods. In Food Engineering and Process Applications, Vol. 1 (pp. 93–101).**
*   **How we have used it:** This is the core mathematical model for the database. We use their additive mixture equations to calculate the specific heat capacity (Cp) of all 36 dishes based on the sum of their individual mass fractions of water, protein, fat, carbohydrates, and ash.

**2. ICMR-NIN (2017). Indian Food Composition Tables (IFCT 2017).**
*   **How we have used it:** This is the primary source for the precise mass fractions (water, protein, fat, carb, ash) of standard Indian ingredients (e.g., rice, dal, spices, dairy) that are fed into the Choi & Okos model to compute thermal properties.

**3. USDA FoodData Central (2019). SR Legacy / Foundation Foods releases.**
*   **How we have used it:** This serves as the secondary source for ingredient mass fractions for items not specifically covered or isolated in IFCT 2017 (e.g., chicken, goat meat, prawn, cabbage, okra, tomato).

**4. McGee, H. (2004). On Food and Cooking: The Science and Lore of the Kitchen (2nd ed.). Scribner.**
*   **How we have used it:** We use this to determine the thermal degradation times of complex carbohydrates (like pectin in vegetables) and starches. This data dictates the duration of the "kinetic" (boiling) stages for vegetable and lentil dishes.

**5. Ofstad, R., et al. (1996). Ultramicroscopic structures and liquid loss in heated cod and salmon muscle. Journal of the Science of Food and Agriculture, 72, 337–347.**
*   **How we have used it:** This study establishes that fish myosin denatures at 39-50°C. We use this exact temperature range to set the low-temperature kinetic cooking threshold for the Fish Curry model, skipping the standard 100°C collagen-breakdown stage.

**6. CCT Protocol v2.0 (2014). Clean Cooking Alliance / Aprovecho.**
*   **How we have used it:** We extracted the standardized water boiling test (WBT) parameters, specifically using it to define the lid exposure factors (Lid ON = 0.2 exposed area, Lid OFF = 1.0) and baseline convection metrics in our time estimator.

**7. Prasad, Vairagar & Bera (2010). J. Food Eng., 97, 56–61.**
*   **How we have used it:** Used for cross-verifying the specific heat capacities and cooking kinetics of traditional Indian multi-component foods.

**8. CSIR-CFTRI Mysuru — Technology transfer profiles for grain processing.**
*   **How we have used it:** Used to determine standard baseline water absorption ratios and volumetric expansion kinetics for Indian grains and legumes during boiling.

---

## 2. Biomass Fuel Properties (`pellet_db.py`)

**9. ISO 17225-2:2021. Solid biofuels — Fuel specifications and classes — Part 2: Graded wood pellets.**
*   **How we have used it:** Defines the baseline Gross Calorific Value (GCV) lower bounds (≈3943 kcal/kg NCV) to set the ranges for premium softwood pellets in the simulator.

**10. ENplus A1/A2 Certification Standard. European Pellet Council.**
*   **How we have used it:** Supplements the ISO standards to establish the maximum permissible ash content and realistic upper GCV boundaries for certified wood and hardwood pellets.

**11. Napier Grass India GCV database (2024). https://napiergrass.in.**
*   **How we have used it:** This is the primary empirical source for the Gross Calorific Values of Indian agricultural waste pellets (e.g., corncob, cotton stalk, mustard husk, wheat straw).

**12. Ríos-Badrán, I.M., et al. (2020). Production and characterisation of fuel pellets from rice husk and wheat straw. Renewable Energy, 145, 500-507. DOI: 10.1016/j.renene.2019.06.048.**
*   **How we have used it:** We used this peer-reviewed study to confirm the lower GCV limits and high ash constraints specifically for rice husk and wheat straw pellets, verifying the Napier Grass database values.

**13. Almeida, L.F.P., et al. (2017). Sugarcane bagasse pellets: characterization and comparative analysis. Acta Scientiarum. Technology, 39(4), 461-468.**
*   **How we have used it:** This study establishes the correct GCV of dried, pelletized sugarcane bagasse (3800-4200 kcal/kg). It was used to correct a previous error that mistakenly used the GCV of wet, raw bagasse.

**14. Cansee, S., et al. (2024). Performance optimization of natural updraft gasifier stoves. Energy Nexus.**
*   **How we have used it:** Used as a reference for typical combustion constraints, airflow, and realistic burn rates for natural/forced draft gasifier stoves processing these pellets.

---

## 3. Core Physics Engine & Utensils (`main_logic.py` & `utensil_db.py`)

**15. Himanshu; Pal, K.; Jain, Sanjeev; et al. (2022). Energy and exergy analysis and emission reduction from forced draft gasifier cookstove models: a comparative study. Journal of Thermal Analysis & Calorimetry, 147(15), 8509. doi:10.1007/s10973-021-11137-**
*   **How we have used it:** This paper is the explicit, direct source for the calibrated maximum thermal efficiency constant (`STOVE_THERMAL_EFFICIENCY = 0.47`) of the IIT Delhi Tadka Chulha stove modeled in the transient physics loop.

**16. Incropera, F.P., et al. (2007). Fundamentals of Heat and Mass Transfer (7th ed.).**
*   **How we have used it:** Sourced for the standard heat transfer coefficients (Table A.11). We use these exact ranges to calculate convection losses based on wind tiers (Still air = 10 W/m²·K, High wind = 50 W/m²·K), as well as setting thermal radiation emissivity limits for oxidized metals.

**17. MacCarty, N., Still, D., & Ogle, D. (2010). Fuel use and emissions performance of fifty cooking stoves in the laboratory and related benchmarks of performance. Energy for Sustainable Development, 14(3), 161-171.**
*   **How we have used it:** Provides the foundational cookstove laboratory benchmarking. It validates our approach to modeling sensible and latent heat energy balances over the burn cycle.

**18. NIST Chemistry WebBook (National Institute of Standards and Technology).**
*   **How we have used it:** Sourced for the exact thermophysical constants of materials and water used in the 1Hz transient loop (e.g., the specific heat capacity of aluminium, latent heat of vaporization).

**19. Hawkins Cookers Limited & TTK Prestige Limited (2023-2024 Product Catalogs).**
*   **How we have used it:** Sourced for the exact geometric and physical measurements (capacity in liters, inner diameter in meters, empty mass in kg, and pressure ratings) of standard Indian cooking vessels (pressure cookers, kadhais, pots, tawas) to build the physical dimensions in `utensil_db.py`.
