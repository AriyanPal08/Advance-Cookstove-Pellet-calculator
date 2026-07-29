Biomass Cookstove Pellet Calculator — v11 Change Documentation

Version: 11.0

Scope: Complete transition to a Production-Ready Web Application, Automated Environmental APIs, Hardware UI Refinements, and Docker Containerization.

1. Summary of Major Changes
Version 11 represents a massive leap from a local terminal script to a fully realized, full-stack software application. Over the last 3 weeks, the system was completely overhauled with a modern Flask backend, a highly polished frontend UI, automated zero-billing weather detection, production-ready containerization, and significant hardware upgrades.

2. Full-Stack Web Application Overhaul
- **Frontend Modernization**: Built a sleek, GPU-accelerated web UI featuring Glassmorphism, Dark Mode, smooth scroll optimizations, and mobile-responsive CSS.
- **Backend API**: Engineered a robust Flask backend (`app.py`) to seamlessly serve the 1Hz transient physics simulation to the frontend UI via AJAX.
- **Credits & Documentation**: Added Yash Tyagi as Co-Developer alongside Ariyan Pal (Lead) across the UI footer, credits, and README.

3. Automated Weather & Wind Integration
- **Zero-Billing Weather API**: Implemented a server-side `/api/weather` endpoint using the Open-Meteo API. 
- The system now automatically geo-locates the user and fetches real-time wind speeds and temperatures, bypassing the need for manual data entry while ensuring zero API billing costs forever.

4. Hardware LCD & MicroPython Upgrades (`hardware/main.py`)
- **LCD Menu Refactor**: Completely refactored LCD user prompts, implemented robust error handling, and added overflow checks to guarantee text never exceeds the 16x2 character limits.
- **Pellet Range Recommendation**: Hardware now calculates and displays a min-max pellet range (`{min}m {base}-{margin}g`) for extreme accuracy on the LCD.
- **Audio Polish**: Replaced the standard startup tone with a "Tokyo Drift" synth riff boot jingle.

5. Critical Physics & Translation Hardening
- **Seamless Background Translation**: Re-engineered Google Translate integration to operate silently without page reloads or intrusive toolbars, enabling infinite bi-directional English/Hindi toggling.
- **Pressure Cooker Timing Fix**: Fixed a critical logic flaw in `main_logic.py` where the `PRESSURE_POST_BOIL_FACTOR` (0.20) was prematurely slashing kinetic simmering times for open vessels by 80%.
- **Enhanced Touch Targets**: Enlarged wizard navigation buttons with explicit `z-index: 20` mapping to eliminate touch-delay and overlap failures on mobile screens.

6. Production Docker Deployment
- Added a `Dockerfile` and `docker-compose.yml` for lean, 1-click production deployments.
- Configured Gunicorn with optimized workers and proxy headers for safe mixed-content routing in production.
- Secured `.gitignore` by removing `node_modules` and lock files for a strictly lean repository footprint.

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
