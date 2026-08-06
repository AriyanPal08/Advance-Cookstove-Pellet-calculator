# Evaluation of fuel requirements w.r.t. food cooking and operation time using biomass pellet cookstove under the department of DESE IIT DELHI

A physics-informed, stove-specific decision-support prototype for estimating
pellet loading and cooking duration on the **Tadka Chulha** forced-draft
biomass pellet stove. The prototype has been tested in the laboratory of the
Department of Energy Science and Engineering (DESE), IIT Delhi.
It is designed to keep the interaction simple enough for day-to-day users:
choose a dish, amount, utensil, pellet, lid state, and environment; the
calculator produces a suggested cooking duration and pellet-load range.

## Research position

This repository supports a prototype research paper. The appropriate claim is:

> A physics-informed, experimentally calibrated decision-support prototype for
> the Tadka Chulha forced-draft pellet cookstove, tested in the DESE laboratory
> at IIT Delhi.

It is **not** a universally validated prediction model for all stoves, foods,
pellets, cookware, weather, or operating practices. Recommendations should be
used only within the input ranges and operating conditions validated for the
target stove. Users must supervise cooking and stop if food quality or safety
indicators are unsuitable.

The model uses a calibrated maximum stove thermal efficiency of 0.47 and a
measured high-feed setting of 0.78 kg/h. These are target-stove parameters,
not universal constants. Any research paper must report their experimental
test conditions, fuel basis, replicate count, and uncertainty.

## What the model calculates

The solver advances one-second time steps. At each step it calculates:

1. Thermal power delivered from the selected pellet's energy value, the fixed
   high-feed setting, and the calibrated maximum efficiency.
2. The combined thermal mass of food, added water, and utensil.
3. Convective and radiative losses from a geometry-based vessel surface area.
4. Sensible heating before boiling, followed by evaporation and dry-boil
   safety tracking.
5. A time-based pellet-load recommendation:

   `pellets_g = cook_time_h × 0.78 kg/h × 1000 × reserve factor`

The reserve factor is an operational allowance for real-world variation. It is
not yet a measured statistical uncertainty interval.

## Inputs that remain empirical

Some inputs are scenario or calibration parameters, rather than universal
physical constants:

- Lid-on evaporation coefficient (`0.15`): provisional and vessel/lid specific.
- Pressure-cooker kinetic reduction (`0.20`): provisional and recipe/stove specific.
- Wind tiers: assumed heat-transfer scenarios, not direct wind-speed measurements.
- Food preparation stages and cooking durations: recipe presets.
- Pellet heating values: material ranges that require a declared HHV/LHV and
  moisture basis for formal reporting.

These assumptions are retained because they make the tool practical, but they
must be reported honestly and calibrated with controlled tests before making
general performance claims.

## Interfaces

### Website

The Flask web application presents the same calculation setup used by the
hardware-matched adapter. It provides the accessible day-to-day interface and
uses simple dish, utensil, lid, pellet, and environmental selections.

### ESP32 interface

`hardware/main.py` provides a 16×2 LCD and rotary-encoder interface intended
for an ESP32 running MicroPython. It retains the same database values and core
calculation equations as the software path. Flashing and on-device testing are
still required after every firmware or MicroPython-version change.

### Core data and model files

- `main_logic.py` — desktop physics engine and terminal interface.
- `food_db.py` — recipe presets and food-property estimates.
- `pellet_db.py` — pellet energy ranges.
- `utensil_db.py` — utensil mass, material, and geometry records.
- `software/hardware_adapter.py` — website adapter that loads the hardware
  calculation source for parity.

## Validation and publication readiness

Initial observed cooking trials are encouraging, but they are preliminary and
must not be presented as a complete validation dataset. A paper should report
both successful and failed trials, including quality outcomes such as burning.

For every future test, record:

- exact dish and amount;
- food and added-water mass;
- utensil model, mass, and dimensions;
- pellet type, moisture, and heating-value basis;
- ambient condition and fan/feed setting;
- predicted and measured time and pellet mass; and
- cooking endpoint and quality outcome.

Run at least three replicates per condition before reporting accuracy metrics.
Private experiment logs and audit notes are intentionally excluded from Git.

## Sources and terminology

- Water properties and WBT methodology: Clean Cooking Alliance, Water Boiling
  Test v4.2.3.
- Food-property methodology: Choi and Okos (1986), with composition data from
  IFCT 2017 and USDA FoodData Central where applicable.
- Wood-pellet specification standard: ISO 17225-2:2021. This standard covers
  graded wood pellets only; it is not a direct source for all agricultural,
  RDF, or torrefied pellet entries.

For each pellet record used in a manuscript, declare whether its value is
HHV/GCV, LHV/NCV, or as-received effective heating value, together with the
moisture basis.

## Development status

The project contains a website, desktop terminal engine, ESP32-oriented UI,
and Docker deployment configuration. This is an active prototype; do not use
it as an unattended cooking controller or as a safety-critical device.

**Note:** A custom PCB and a 3D-printed enclosure box for the hardware module are coming soon!
