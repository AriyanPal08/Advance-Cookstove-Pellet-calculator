# Advanced Biomass Cookstove Pellet Calculator

A high-fidelity thermodynamic modeling tool developed at IIT Delhi (Department of Energy Studies) to estimate biomass pellet fuel requirements for forced-draft cookstoves.

Moving beyond standard static energy balances, this simulator utilizes a **1Hz Discrete Transient State Machine** to calculate second-by-second energy routing, accounting for real-world environmental wind, vessel materials, pressure cooker dynamics, and precise culinary kinetics.

Originally a CLI engine, the project has now evolved into a comprehensive ecosystem featuring a **Full-Stack Web Application**, an **Automated Environmental API**, and an **ESP32 Hardware Module**.

---

## System Architecture

The Tadka Chulha software ecosystem consists of three primary modules:

### 1. Full-Stack Web Application
- **Frontend (UI/UX)**: A responsive, state-driven wizard interface built with GPU-accelerated CSS. Features include a sleek Glassmorphism design, Dark Mode toggles, smooth scroll optimizations, and a seamless, zero-reload bi-directional Google Translate integration (English/Hindi).
- **Backend (Flask API)**: A robust Python backend (`app.py`) that securely encapsulates the core physics engine and databases. The frontend asynchronously queries the `/api/simulate` endpoint to run the intensive 1Hz physics simulation loop.
- **Zero-Billing Weather Integration**: The backend automatically resolves geolocation via the Open-Meteo API to fetch live ambient temperatures and wind speeds, intelligently mapping them to internal convective physics tiers to bypass manual user data entry.

### 2. ESP32 Hardware Integration (MicroPython)
- **LCD Interface**: Features a fully refactored 16x2 LCD UI with robust buffer overflow checks to ensure strings never exceed hardware limits.
- **Dynamic Pellet Range Output**: Calculates and displays an advanced min-max pellet load range (e.g., `56m 721-779g`), matching the precise outputs of the web engine.
- **Audio Integration**: Includes a PWM-driven piezo buzzer with custom boot jingles (Tokyo Drift synth riff) and alert handlers.

### 3. Production Deployment (Docker)
The system is fully containerized for production deployment.
- Runs via a lightweight `Dockerfile` (Python base image) and `docker-compose.yml`.
- Leverages `gunicorn` with optimized worker threading and proxy headers for safe mixed-content routing behind reverse proxies.

---

## Core Engine: The 1Hz Transient Physics Loop

The underlying engine operates in three distinct computational phases to eliminate human input error and mathematically protect the conservation of energy.

### Phase 1: State Initialization & Total Time Estimator
Rather than asking the user to guess how long a dish takes to cook, the engine pre-calculates the thermodynamic limits based on the environment:
- **Database Lookups**: Pulls specific heat ($C_p$), mass, and kinetic simmering times from `food_db.py` and `utensil_db.py`.
- **Environmental Inputs**: Applies user-defined or API-fetched wind factors (Newtonian Convection $h$) and ambient temperature.
- **Geometry Derivation**: Reverse-engineers the pot's surface area ($A_{m2}$) and geometric efficiency coupling ($\eta_{geom}$) based on the water volume.
- **The Estimator**: Calculates a projected heat-up time ($t_{heat}$) by evaluating the vessel's thermal mass against the stove's available power minus the average convective/radiative heat bleed. It adds this to the culinary simmer time to suggest a Total Cooking Time.

### Phase 2: The 1Hz Transient Loop
The engine runs a `while t_elapsed < t_total` loop, updating the state of the pot every 1.0 seconds.
- **Step 2A (Power In)**: The stove delivers a constant baseline of thermal energy based on the mechanical High Fan feed rate ($0.78 \text{ kg/hr}$).
- **Step 2B (Dynamic Mass)**: Calculates $MC_{p,total}$ (Food + Water + Metal).
- **Step 2C (Heat Bleed)**: Calculates exact Heat Loss ($Q_{out}$) using real-time pot temperature, ambient temperature, surface area, and dynamic wind factors.
- **Step 2D (Net Energy Routing)**: The engine subtracts heat bleed from heat applied ($Q_{avail} = Q_{in} - Q_{out}$) and cascades the remaining energy:
  - **Route A (Sensible Heating)**: If $T_{pot} < 100^\circ\text{C}$, energy raises the water temperature.
  - **Route B (Evaporation)**: If $T_{pot} = 100^\circ\text{C}$, energy converts liquid water to steam, accounting for lid retention factors.
  - **Route C (Safety Break)**: If water boils dry ($m_{water} \le 0$), the 100°C lock breaks, triggering a severe overheat warning.

### Phase 3: Post-Processing & Output
The system generates a comprehensive diagnostic receipt, slicing the elapsed time into an academic 3-Phase Combustion Model (15% Ignition, 65% Steady State, 20% Radiant Char) and calculating the final physical pellet requirement using the Safe Overestimate Rule.

---

## Mathematical Formulas & Constants

### 1. Convective & Radiative Heat Bleed ($Q_{out}$)
Calculated every second using the Stefan-Boltzmann law and Newtonian cooling:

$$P_{conv} = h \cdot A \cdot (T_{pot} - T_{amb}) \cdot \text{Lid Factor}$$

$$P_{rad} = \epsilon \cdot \sigma \cdot A \cdot (T_{pot}^4 - T_{amb}^4)$$

- **Wind Factor ($h$)**: 10.0 (Indoors), 20.0 (Low Wind), 35.0 (Medium Wind), 50.0 (High Wind)
- **Stefan-Boltzmann ($\sigma$)**: $5.67 \times 10^{-8} \text{ W/m}^2\text{K}^4$

### 2. Evaporative Mass Loss ($m_{evap}$)
During the boiling phase, available energy is converted to steam:

$$m_{evap} = \left(\frac{Q_{avail}}{L_V}\right) \times \text{Lid Factor}$$

- **Latent Heat of Vaporization ($L_V$)**: $2257 \text{ kJ/kg}$
- **Lid Factors**: 1.00 (Lid Off), 0.15 (Lid On), 0.00 (Sealed Pressure Cooker)

### 3. Final Fuel Calculation (The "Safe Overestimate" Rule)
To prevent the engine from artificially deleting energy when a sealed pressure cooker rejects heat transfer, the final pellet mass is calculated via the absolute elapsed time clock alongside procurement margins:

$$\text{Pellets (g)} = \left(\frac{t_{elapsed}}{3600}\right) \times \text{FAN\_HIGH} \times 1000 \times \text{Margin}$$

- **FAN_HIGH (Mechanical Feed Limit)**: $0.78 \text{ kg/hr}$

---

## Developers
- **Ariyan Pal** (Lead Developer)
- **Yash Tyagi** (Co-Developer & Contributor)

Developed for the IIT Delhi Department of Energy Studies.
