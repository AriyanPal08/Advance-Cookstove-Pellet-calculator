Biomass Cookstove Pellet Calculator — v11 Change Documentation

Version: 11.0

Scope: Complete architectural transformation from a local CLI utility to a Production-Ready Web Application, Automated Open-Meteo Environmental APIs, Comprehensive Hardware MicroPython Refinements, and Full Docker Containerization.

1. Summary of Major Changes
Version 11 represents a massive evolutionary leap for the Tadka Chulha project. Over the past 3 weeks, the system was entirely overhauled, migrating the core 1Hz transient physics engine to a scalable Flask backend, introducing a highly polished, GPU-accelerated frontend UI, automating complex environmental inputs via zero-billing external APIs, and significantly upgrading the ESP32 hardware code.

2. Full-Stack Web Application Architecture
- **Frontend Modernization (`index.html`, `script.js`, `style.css`)**: Built a fully responsive, state-driven wizard interface that entirely replaces the CLI inputs. Implemented a sleek, GPU-accelerated Glassmorphism design system featuring dynamic Dark Mode toggles, transparent cards, and smooth CSS keyframe animations (including a Ken Burns effect on the hero background).
- **Backend API (`app.py`)**: Engineered a robust Flask backend that securely encapsulates the `main_logic.py` and database systems (`food_db.py`, `pellet_db.py`, `utensil_db.py`). The frontend asynchronously communicates with the `/api/simulate` endpoint to run the intensive 1Hz physics simulation loop and return structured JSON receipts.
- **Credits & Documentation**: Fully updated the website footer, UI structure, and `README.md` to properly credit Yash Tyagi as Co-Developer alongside Ariyan Pal (Lead).

3. Automated Zero-Billing Weather & Wind Integration
- **Open-Meteo Server Integration**: Implemented an automated, server-side `/api/weather` endpoint that interfaces with the Open-Meteo API.
- **Dynamic Physics Mapping**: The backend automatically resolves the user's location via IP (or uses a standard reference), fetches live ambient temperatures, and maps real-time wind speeds directly to the stove's internal convective tiers (e.g., mapping gentle breezes to "Outdoors (Low Wind)"). This allows users to bypass manual environmental data entry completely, while guaranteeing zero API billing costs forever.

4. ESP32 Hardware LCD & MicroPython Upgrades (`hardware/main.py`)
- **LCD Rendering Refactor**: Completely rewrote the `lcd_show` and prompt handling logic. Implemented strict buffer tracking and overflow checks to guarantee that dynamic string formatting never exceeds the strict 16-character limit of 16x2 LCD displays, preventing screen artifacting.
- **Dynamic Pellet Range Recommendation**: The hardware now dynamically formats and displays an advanced min-max pellet load range (e.g., `56m 721-779g`) directly on the LCD, elegantly bridging the theoretical time-based load with the procurement-margined load while safely respecting the 16-character boundary.
- **Audio Polish**: Upgraded the standard startup sequence by leveraging PWM duty cycles to play a "Tokyo Drift" synth riff boot jingle on the piezoelectric buzzer.

5. Rigorous UI/UX Refinements & Translation Hardening
- **Seamless Background Translation**: Re-engineered the Google Translate integration. Used aggressive CSS overrides (`left: -9999px`, `opacity: 0`, `.skiptranslate display: none !important`) to forcefully hide the intrusive Google top banner frame, tooltips, and body-shifting artifacts. Fixed an infinite looping bug by forcing `selectedIndex = 0` (Original Language) on toggle, ensuring translation is instantaneous, entirely silent, and bi-directional.
- **Enhanced Mobile Touch Targets**: Addressed mobile responsiveness by increasing wizard navigation button (`btn-next`, `btn-prev`) padding to `1.5rem 4rem` with a `64px` minimum height. Mapped explicit `z-index: 20` and `touch-action: manipulation` rules to completely eliminate the standard 300ms touch delay and prevent background overlapping elements from stealing click events.

6. Critical Physics Engine Bug Fixes (CLI)
- **Kinetic Simmering Time Fix**: Resolved a severe architectural logic flaw in the terminal CLI (`main_logic.py`) that caused open vessels (like Kadhais) to output impossibly fast cooking times (e.g., calculating 18.8 minutes instead of the correct 34 minutes).
- **The Core Issue**: The `PRESSURE_POST_BOIL_FACTOR` (0.20), which correctly cuts simmering time by 80% for sealed pressure cookers, was being applied prematurely at Step 1 (Dish Selection) before Step 5 (Utensil Selection). 
- **The Solution**: Deferred the kinetic time baseline calculation until *after* the user selects their utensil. The CLI now properly inspects `inp["is_pc"]` to ensure the 80% time reduction is strictly applied *only* to pressure cookers, bringing the terminal engine into perfect mathematical harmony with the web backend.

7. Production Docker Deployment & Repository Cleanup
- **Containerization**: Introduced a lightweight `Dockerfile` utilizing a lean Python base image, paired with a `docker-compose.yml` for effortless 1-click scaling and deployment.
- **Gunicorn Optimization**: Configured the WSGI entrypoint with optimized worker threading and explicit proxy headers to safely handle mixed-content routing behind production reverse proxies.
- **Repository Trimming**: Hardened `.gitignore` and purged `node_modules` and unused lock files, drastically reducing the repository footprint for a strictly lean architecture.

========================================================================

Biomass Cookstove Pellet Calculator — v10 Change Documentation

Version: 10.0

Scope: Complete architectural overhaul to a 1Hz Transient State Machine, hardware-ready UI integration, and physical environmental overrides.

1. Summary of Major Changes

Version 10 completely deprecates the old linear/algebraic "5-term energy balance" models (v7-v9) and replaces them with a 1Hz Discrete Transient Thermodynamic Solver. This eliminates previous scaling bugs by simulating the cooking process second-by-second.

Key feature upgrades include:

Dynamic Wind Factors: Replaced static still-air convection assumptions with user-selectable environmental wind tiers.

Utensil Material Database: Integrated utensil_db.py to handle varying Specific Heat Capacities ($C_p$) for Aluminum, Cast Iron, and Stainless Steel, along with a Vessel Mass Override feature.

The "Safe Overestimate" Fuel Fix: Resolved a critical bug where pressure cookers (Lid Factor = 0) were mathematically "deleting" combustion energy.

Total Time Estimator: Automated the heat-up time predictions, entirely replacing the flawed sub-linear batch scaling formulas from v8.

2. Dynamic Environmental Wind Factors (New Feature)

Previous versions assumed a perfectly still laboratory environment ($h = 10 \text{ W/m}^2\text{K}$). The engine now utilizes a dynamic k_conv_current variable mapped to standard forced-convection coefficients (Churchill & Bernstein).

Environment

Convection Coeff ($h$)

Impact on Engine

Indoors (Still Air)

10.0 W/m²K

Baseline minimal heat bleed.

Outdoors (Low Wind)

20.0 W/m²K

Doubles convective heat stripping.

Outdoors (Med Wind)

35.0 W/m²K

Significantly delays the $t_{heat}$ phase.

Outdoors (High Wind)

50.0 W/m²K

Triggers engine safety breaks if $Q_{out}$ exceeds stove $Q_{in}$.

3. Utensil Database & Mass Override

Manual input of raw specific heat capacity has been removed. The simulator now silently queries utensil_db.py for material constants based on standard cookware (e.g., standardizing Aluminum at $0.897 \text{ kJ/kg}\cdot\text{K}$).

Vessel Mass Override: To maintain accuracy without punishing UX, the database supplies a default mass (e.g., $1.2\text{ kg}$ for a 5L pot), but prompts the user to override this with a precise weight if known. This dynamically updates the thermal inertia ($MC_{p,total}$) in the 1Hz loop.

4. Resolution of the "Pressure Cooker / Lid Factor" Bug

The Flaw (v8/v9)

In previous versions, final pellet consumption was derived purely from tracked thermodynamic energy: Q_demand = Q_sensible + Q_evap + Q_out.
Because a sealed pressure cooker has a Lid Factor of 0.0, the math dictated that zero steam escaped, making $Q_{evap} = 0$. Consequently, the engine "deleted" all the thermal energy generated by the stove during the simmering phase, outputting impossibly low pellet requirements (e.g., 30g for 20 minutes of cooking).

The Fix (v10: The Safe Overestimate Rule)

The engine's energy cascade was preserved to track internal states accurately, but the final output variable was decoupled from the internal energy sink. Pellet calculations now strictly use absolute time tracking tied to the mechanical feed rate limit:
Pellets = (t_elapsed / 3600.0) * FAN_HIGH * 1000.0
This accurately reflects that the stove continues to burn fuel at the set fan rate, regardless of whether the pot absorbs or rejects the heat.

5. Deprecation of v8 "Sub-Linear Scaling"

Version 8 attempted to fix multi-person cooking times using arbitrary mathematical exponents ($t_{scaled} = t_{base} \times n^{0.25}$).

This artificial scaling was completely removed in v10. Because the new 1Hz Transient Loop recalculates the mass of the food and water every second against the applied heat ($Q_{avail} / MC_p$), the engine now scales itself naturally via pure thermodynamics. Heating 5 Liters of water inherently takes longer than heating 1 Liter without relying on arbitrary exponents. The baseline culinary kinetic simmering times ($t_c$) are now treated as batch-independent constants.
