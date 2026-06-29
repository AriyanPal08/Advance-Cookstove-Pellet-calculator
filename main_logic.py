"""
main_logic.py
1Hz Discrete Transient Biomass Cookstove Simulator  — Version 1
IIT Delhi · Department of Energy Studies

Implements the exact architecture specified in:
  PRD: "1Hz Discrete Transient Biomass Cookstove Simulator Version 1"

Design Rule (Immutable — PRD §1):
  The core loop runs at FAN_HIGH (0.78 kg/hr) for the ENTIRE cook.
  This is a deliberate "safe overestimate": it guarantees the user
  never runs out of fuel by using worst-case constant high-fan operation.
  The 3-Phase combustion receipt is generated AFTER the loop for
  display purposes only and does NOT alter the governing fuel physics.

Architecture (4 pre-simulation steps + 1Hz transient loop):
  §4  Pre-Simulation : input collection + hidden geometry + zero state
  §5  1Hz Loop       : power → thermal mass → heat bleed → state routing
                       → clock advance (runs until t_kinetic_remaining ≤ 0)
  §6  Post-Processing: fuel output + safety diagnostics + 3-phase receipt

Assumptions (PRD §2):
  • Lumped Capacitance: vessel/water/food treated as one uniform thermal node
  • Static Area: vessel surface area held constant (wetted area decrease ignored)
  • Empirical η_geom: calibrated against WBT data, not first-principles derivation
"""

from __future__ import annotations

import math
import sys
import datetime
from pathlib import Path

# Database imports (read-only per PRD §1 Core Directive)
from food_db   import FOOD_DB, DishProfile, get_dish_names
from pellet_db import PELLET_DB, PelletType, get_pellet_names

# =============================================================================
# SECTION 3 — IMMOVABLE PHYSICAL CONSTANTS  (PRD §3 — "Do not use magic numbers")
# =============================================================================

FAN_HIGH:    float = 0.78     # kg/hr  — high-fan mechanical feed rate
MAX_EFF:     float = 0.45     # —       maximum combustion efficiency
K_CONV:      float = 10.0     # W/m²·K — convective heat transfer coefficient (still air)
L_V:         float = 2257.0   # kJ/kg  — latent heat of vaporisation at 100°C
SIGMA:       float = 5.67e-8  # W/m²·K⁴ — Stefan-Boltzmann constant
dt:          float = 1.0      # s      — simulation time step (1 Hz)
EMISSIVITY:  float = 0.3      # —       vessel surface emissivity

# Additional physical constants (sourced, not magic numbers)
CP_WATER:    float = 4.184    # kJ/kg·K — specific heat of water (NIST, ~60°C midpoint)
CP_AIR_REF:  float = 4.184    # kept as alias for clarity in formulas

# Safety thresholds (PRD §6B)
T_OVERHEAT_C:   float = 150.0   # °C — critical vessel overheat threshold
M_WATER_DRY:    float = 0.0     # kg — dry-boil threshold

# Lid factors (PRD §4A Hardware)
LID_FACTOR_ON:  float = 0.15    # evaporation suppression with lid on
LID_FACTOR_OFF: float = 1.00    # full evaporation rate with lid off

# Pressure cooker boil target (optional extension; PRD uses 100°C baseline)
T_BOIL_NORMAL: float = 100.0    # °C
T_BOIL_PC:     float = 120.0    # °C

# Boil time scaling (PRD §4A: t_kinetic_base × n, with n^0.5 for boil phase)
BOIL_SCALE_EXP: float = 0.5    # sub-linear batch scaling for boil/simmer time

# =============================================================================
# SECTION — TERMINAL COLOURS (lightweight, no third-party deps)
# =============================================================================

_ANSI = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

def _c(text: str, *codes: str) -> str:
    return ("".join(codes) + text + "\033[0m") if _ANSI else text

RST = "\033[0m"
BLD = "\033[1m"
DIM = "\033[2m"
CYN = "\033[36m"
GRN = "\033[32m"
YLW = "\033[33m"
RED = "\033[31m"
BLU = "\033[34m"
MGN = "\033[35m"
WHT = "\033[97m"
ORG = "\033[38;5;214m"

def _hdr(title: str) -> None:
    print()
    print(_c("=" * 72, CYN, BLD))
    print(_c(f"  {title}", BLD, WHT))
    print(_c("=" * 72, CYN, BLD))

def _sec(title: str) -> None:
    print()
    print(_c(f"  ── {title} ──", BLD, YLW))
    print(_c("─" * 72, DIM))

def _info(label: str, val: str, unit: str = "") -> None:
    u = _c(f" {unit}", DIM) if unit else ""
    print(_c(f"  {label:<46}", DIM) + _c(val, GRN, BLD) + u)

def _warn(msg: str) -> None:
    print(_c(f"\n  [!]  {msg}", YLW))

def _fatal(msg: str) -> None:
    print(_c(f"\n  [FATAL]  {msg}", RED, BLD))

def _prompt(msg: str, default: str | None = None) -> str:
    suffix = _c(f" [{default}]", DIM) if default is not None else ""
    try:
        raw = input(_c(f"\n  >>  {msg}", BLD, BLU)
                    + suffix
                    + _c(" : ", BLD, BLU)).strip()
    except EOFError:
        raw = ""
    return raw if (raw != "" or default is None) else default

def _menu(title: str, options: list[str]) -> int:
    _sec(title)
    for i, opt in enumerate(options, 1):
        print(_c(f"    [{i}]  {opt}", WHT))
    while True:
        try:
            raw = _prompt("Select option number")
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                print(_c(f"  ✓  {options[idx]}", GRN))
                return idx
            _warn(f"Enter a number 1–{len(options)}.")
        except ValueError:
            _warn("Please enter a valid number.")
        except KeyboardInterrupt:
            _quit_or_continue()

def _prompt_float(msg: str, default: float,
                  lo: float = 0.0, hi: float = 1e9) -> float:
    while True:
        try:
            raw = _prompt(msg, str(default))
            val = float(raw)
            if lo < val <= hi:
                return val
            _warn(f"Must be > {lo} and ≤ {hi}.")
        except ValueError:
            _warn("Enter a valid number.")
        except KeyboardInterrupt:
            _quit_or_continue()

def _prompt_int(msg: str, default: int, lo: int = 1) -> int:
    while True:
        try:
            raw = _prompt(msg, str(default))
            val = int(raw)
            if val >= lo:
                return val
            _warn(f"Must be ≥ {lo}.")
        except ValueError:
            _warn("Enter a whole number.")
        except KeyboardInterrupt:
            _quit_or_continue()

def _quit_or_continue() -> None:
    print(_c("\n  Ctrl+C detected. Type 'q' to quit or Enter to continue.", YLW))
    try:
        if input("  >> ").strip().lower() == "q":
            print(_c("\n  Goodbye.\n", DIM))
            sys.exit(0)
    except (KeyboardInterrupt, EOFError):
        sys.exit(0)

# =============================================================================
# SECTION 4 — PRE-SIMULATION LOGIC
# =============================================================================

def collect_inputs() -> dict:
    """
    PRD §4A: Collect all user inputs and perform database lookups.
    Returns a flat dict of validated parameters ready for the physics engine.
    """
    _hdr("IIT DELHI  |  1Hz Transient Biomass Cookstove Simulator  |  v1")

    inp: dict = {}

    # ── Dish selection ────────────────────────────────────────────────────────
    dish_names = get_dish_names()
    _sec("Step 1 / 7  —  Dish Selection")
    for i, name in enumerate(dish_names, 1):
        d   = FOOD_DB[name]
        print(_c(f"    [{i:>2}]  {name:<42}  {d.category}", WHT))

    while True:
        try:
            raw = _prompt("Select dish number")
            idx = int(raw) - 1
            if 0 <= idx < len(dish_names):
                inp["dish_name"] = dish_names[idx]
                inp["dish"]      = FOOD_DB[inp["dish_name"]]
                break
            _warn(f"Enter 1–{len(dish_names)}.")
        except ValueError:
            _warn("Enter a valid number.")
        except KeyboardInterrupt:
            _quit_or_continue()

    dish: DishProfile = inp["dish"]

    # ── Portions / water volume ───────────────────────────────────────────────
    if dish.variable_water:
        # Plain Water Boiling: user specifies total litres directly  (PRD §4A)
        _sec("Step 2 / 7  —  Water Volume")
        inp["water_liters"] = _prompt_float(
            "Total water to boil (Litres)", default=5.0, lo=0.0, hi=200.0
        )
        inp["portions"] = 1
    else:
        _sec("Step 2 / 7  —  Number of People / Servings")
        inp["portions"] = _prompt_int("Number of people", default=2)

    n: int = inp["portions"]

    # ── Ambient temperature ───────────────────────────────────────────────────
    _sec("Step 3 / 7  —  Ambient Temperature")
    inp["t_ambient_c"] = _prompt_float(
        "Ambient temperature (°C)", default=25.0, lo=-10.0, hi=50.0
    )

    # ── Pellet selection  (PRD §4A: GCV pulled from pellet_db) ───────────────
    pellet_names = get_pellet_names()
    _sec("Step 4 / 7  —  Pellet Type")
    for i, name in enumerate(pellet_names, 1):
        p = PELLET_DB[name]
        print(_c(
            f"    [{i:>2}]  {name:<44}"
            f"  {p.gcv_min_kcal:,}–{p.gcv_max_kcal:,} kcal/kg  [{p.category}]",
            WHT
        ))
    while True:
        try:
            raw = _prompt("Select pellet type")
            idx = int(raw) - 1
            if 0 <= idx < len(pellet_names):
                inp["pellet_name"] = pellet_names[idx]
                inp["pellet"]      = PELLET_DB[inp["pellet_name"]]
                break
            _warn(f"Enter 1–{len(pellet_names)}.")
        except ValueError:
            _warn("Enter a valid number.")
        except KeyboardInterrupt:
            _quit_or_continue()

    pellet: PelletType = inp["pellet"]

    # ── Vessel configuration  (PRD §4A Hardware) ─────────────────────────────
    _sec("Step 5 / 7  —  Vessel Configuration")

    VESSEL_DEFAULTS = {
        "Standard Aluminium Pot (5L)":  {"mass_kg": 1.20, "cp": 0.897, "p_loss_kw": 0.20},
        "Kadhai / Wok":                 {"mass_kg": 0.90, "cp": 0.897, "p_loss_kw": 0.25},
        "Frying Pan / Tawa":            {"mass_kg": 0.70, "cp": 0.460, "p_loss_kw": 0.30},
        "Pressure Cooker (5L)":         {"mass_kg": 1.80, "cp": 0.897, "p_loss_kw": 0.08},
    }
    vessel_names = list(VESSEL_DEFAULTS.keys())
    v_idx = _menu("Vessel Type", vessel_names)
    v_cfg = VESSEL_DEFAULTS[vessel_names[v_idx]]
    inp["vessel_name"]   = vessel_names[v_idx]
    inp["is_pc"]         = (v_idx == 3)   # Pressure Cooker is index 3
    inp["cp_pot"]        = v_cfg["cp"]

    print(_c(
        f"\n  Default mass for {vessel_names[v_idx]}: {v_cfg['mass_kg']:.2f} kg\n"
        f"  (5L Al pot ≈ 1.2 kg; pressure cooker ≈ 1.8 kg)", DIM
    ))
    inp["m_pot"] = _prompt_float(
        "Vessel empty mass (kg)", default=v_cfg["mass_kg"], lo=0.0, hi=50.0
    )

    # ── Lid state  (PRD §4A: Lid Factor) ─────────────────────────────────────
    if inp["is_pc"]:
        inp["lid_label"]  = "ON (Pressure Cooker — sealed)"
        inp["lid_factor"] = 0.0   # sealed: negligible evaporation
    else:
        _sec("Step 6 / 7  —  Lid State")
        lid_idx = _menu("Lid State", ["Lid ON (covered)", "Lid OFF (open)"])
        if lid_idx == 0:
            inp["lid_label"]  = "Lid ON"
            inp["lid_factor"] = LID_FACTOR_ON    # 0.15  (PRD §4A)
        else:
            inp["lid_label"]  = "Lid OFF"
            inp["lid_factor"] = LID_FACTOR_OFF   # 1.00  (PRD §4A)

    # ── Kinetic time  (PRD §4A: t_kinetic_base × n, user override) ───────────
    # Base kinetic time = total phase time from food_db for 1 person.
    # Boil phase scales sub-linearly (n^0.5); fry/simmer are batch-invariant.
    _sec("Step 7 / 7  —  Kinetic Cooking Time")

    if dish.variable_water:
        t_kinetic_base_s = dish.phases.boiling_s   # water boiling only
    else:
        t_fry_s    = float(dish.phases.frying_s)
        t_boil_s   = dish.phases.boiling_s * (n ** BOIL_SCALE_EXP)
        t_simmer_s = float(dish.phases.simmering_s)
        if inp["is_pc"]:
            t_boil_s   *= 0.35   # PRD §4A Time Override compatible
            t_simmer_s *= 0.35
        t_kinetic_base_s = t_fry_s + t_boil_s + t_simmer_s

    t_kinetic_min = t_kinetic_base_s / 60.0
    print(_c(
        f"  Physics-derived kinetic time: {t_kinetic_min:.1f} min"
        f"  ({t_kinetic_base_s:.0f} s)", DIM
    ))
    print(_c(
        "  This is the food kinetic requirement (stir-fry, enzymatic completion,\n"
        "  starch gelatinisation). Press Enter to accept.", DIM
    ))

    # PRD §4A — "Time Override: Manual user input overrides t_kinetic_base"
    t_override_min = _prompt_float(
        "Total cook time (minutes) — Enter to accept suggestion",
        default=round(t_kinetic_min, 1),
        lo=0.0, hi=600.0
    )
    inp["t_kinetic_s"] = t_override_min * 60.0

    # ── PRD §4A: Food/water masses ────────────────────────────────────────────
    if dish.variable_water:
        inp["m_food"]          = dish.food_mass_per_serving_kg    # ≈ 0.001 kg trace
        inp["cp_food"]         = dish.cp_food_kj_kgk
        inp["m_water_initial"] = inp["water_liters"]              # 1 L ≈ 1 kg
    else:
        # PRD §4B: m_food = m_base_food × n;  m_water_initial = m_base_water × n
        inp["m_food"]          = dish.food_mass_per_serving_kg    * n
        inp["cp_food"]         = dish.cp_food_kj_kgk
        inp["m_water_initial"] = dish.added_water_per_serving_kg  * n

    # ── PRD §4A: GCV from pellet db ───────────────────────────────────────────
    inp["gcv_kj_kg"] = pellet.conservative_gcv_kj

    return inp


def setup_geometry(inp: dict) -> dict:
    """
    PRD §4B — Hidden Geometry (computed silently, not shown to user until receipt).

    Standard cylinder (height = diameter):
      V_m³ = m_water_initial / 1000
      d    = (4 × V_m³ / π) ^ (1/3)
      A    = 1.25 × π × d²

    PRD §4C — Empirical Geometric Coupling:
      η_geom = MAX_EFF × max(0.25, min(1.0, √(m_water_initial / 5.0)))
    """
    m_w = inp["m_water_initial"]

    # Geometry  (PRD §4B)
    V_m3 = m_w / 1000.0
    d    = (4.0 * V_m3 / math.pi) ** (1.0 / 3.0)
    A    = 1.25 * math.pi * d ** 2

    # Empirical geometric coupling  (PRD §4C)
    eta_geom = MAX_EFF * max(0.25, min(1.0, math.sqrt(m_w / 5.0)))

    inp.update({
        "V_m3":     V_m3,
        "d_m":      d,
        "A_m2":     A,
        "eta_geom": eta_geom,
    })
    return inp


def zero_state(inp: dict) -> dict:
    """
    PRD §4D — Initialise simulation state variables to zero/ambient.
    """
    inp.update({
        "t_elapsed_s":          0.0,
        "T_pot_c":              inp["t_ambient_c"],   # pot starts at ambient
        "m_water_current":      inp["m_water_initial"],
        "t_kinetic_remaining":  inp["t_kinetic_s"],
        # Safety flags
        "flag_dry_boil":        False,
        "flag_overheat":        False,
        # Diagnostics
        "t_boil_reached_s":     None,    # time when T_pot first hit 100°C
        "tick_log":             [],      # sparse log for receipt
    })
    return inp


# =============================================================================
# SECTION 5 — 1Hz TRANSIENT PHYSICS LOOP  (PRD §5)
# =============================================================================

def run_1hz_loop(inp: dict) -> dict:
    """
    PRD §5 — Execute the 1Hz transient loop.

    Runs while t_kinetic_remaining > 0.
    Each iteration = 1 second (dt = 1.0 s).

    Order per tick:
      5.1  Power generation
      5.2  Dynamic thermal mass
      5.3  Heat bleed (convection + radiation)
      5.4  Net energy → state routing (sensible / evaporation / dry runaway)
      5.5  Advance clock + hysteresis gate on kinetic timer
    """

    # Unpack constants used every tick for speed
    m_food:    float = inp["m_food"]
    cp_food:   float = inp["cp_food"]
    m_pot:     float = inp["m_pot"]
    cp_pot:    float = inp["cp_pot"]
    A:         float = inp["A_m2"]
    eta_geom:  float = inp["eta_geom"]
    gcv:       float = inp["gcv_kj_kg"]
    lid_fac:   float = inp["lid_factor"]
    T_amb:     float = inp["t_ambient_c"]
    T_amb_K:   float = T_amb + 273.15

    # Mutable state
    T_pot:              float = inp["T_pot_c"]
    m_water:            float = inp["m_water_current"]
    t_elapsed:          float = inp["t_elapsed_s"]
    t_kin_rem:          float = inp["t_kinetic_remaining"]
    flag_dry:           bool  = False
    flag_over:          bool  = False
    t_boil_reached:     float | None = None

    # ── PRD §5.1: P_in is constant for entire run (high-fan assumption) ───────
    # "the simulation assumes the worst-case mechanical feed: user leaves
    #  stove on HIGH FAN (0.78 kg/hr) for the entire cook"  [PRD §1]
    P_in_kw: float = (FAN_HIGH / 3600.0) * gcv * eta_geom   # kW
    Q_in:    float = P_in_kw * dt                            # kJ per tick

    # Sparse logging: record every 60 ticks (1 min) to keep receipt clean
    log_interval: int = 60
    tick_log: list    = []
    tick:     int     = 0

    # ── MAIN LOOP ─────────────────────────────────────────────────────────────
    while t_kin_rem > 0:

        # ── Step 5.2: Dynamic thermal mass  (PRD §5.2) ────────────────────────
        # m_water_current changes as water evaporates → MCp_total is dynamic
        MCp_total = (m_food * cp_food) + (m_water * CP_WATER) + (m_pot * cp_pot)

        # ── Step 5.3: Heat bleed  (PRD §5.3) ─────────────────────────────────
        T_pot_K  = T_pot + 273.15
        P_conv   = K_CONV * A * (T_pot_K - T_amb_K)                    # Watts
        P_rad    = EMISSIVITY * SIGMA * A * (T_pot_K**4 - T_amb_K**4)  # Watts
        Q_out    = ((P_conv + P_rad) / 1000.0) * dt                    # kJ

        # ── Step 5.4: Net energy & state routing  (PRD §5.4) ──────────────────
        Q_avail = Q_in - Q_out

        if Q_avail <= 0.0:
            # ── Branch A: Net cooling ─────────────────────────────────────────
            # PRD §5.4: "If Q_avail ≤ 0 (Cooling): ΔT = Q_avail / MCp_total"
            if MCp_total > 0:
                T_pot += Q_avail / MCp_total
        else:
            # ── Branch B: Net heating ─────────────────────────────────────────
            # B1: Sensible heating to 100°C  (PRD §5.4 Sensible Heating)
            if T_pot < 100.0:
                Q_to_100 = MCp_total * (100.0 - T_pot)
                if Q_avail <= Q_to_100:
                    T_pot   += Q_avail / MCp_total
                    Q_avail  = 0.0
                else:
                    T_pot    = 100.0
                    Q_avail -= Q_to_100
                    if t_boil_reached is None:
                        t_boil_reached = t_elapsed + dt   # record first boil

            # B2: Evaporation  (PRD §5.4 Evaporation — Latent Heat)
            if Q_avail > 0 and m_water > 0:
                m_evap_potential = (Q_avail / L_V) * lid_fac
                if m_evap_potential <= m_water:
                    m_water -= m_evap_potential
                    Q_avail  = 0.0
                else:
                    # Water runs out mid-tick
                    Q_boil  = (m_water / lid_fac) * L_V
                    m_water = 0.0
                    Q_avail -= Q_boil
                    # Fall through to dry runaway below

            # B3: Dry runaway  (PRD §5.4 Dry Runaway Heating)
            # Reached only when m_water == 0 and Q_avail still > 0
            if Q_avail > 0 and m_water <= 0:
                MCp_dry = (m_food * cp_food) + (m_pot * cp_pot)
                if MCp_dry > 0:
                    T_pot += Q_avail / MCp_dry
                Q_avail = 0.0

        # ── Step 5.5: Advance clock + hysteresis gate  (PRD §5.5) ─────────────
        t_elapsed += dt

        # Hysteresis: kinetic timer counts down ONLY once boiling is sustained
        # "If T_pot ≥ 99°C: t_kinetic_remaining -= dt"  [PRD §5.5]
        if T_pot >= 99.0:
            t_kin_rem -= dt

        # ── Safety checks  (PRD §6B — evaluated every tick) ───────────────────
        if m_water <= M_WATER_DRY and not flag_dry:
            flag_dry = True
        if T_pot > T_OVERHEAT_C and not flag_over:
            flag_over = True

        # ── Sparse telemetry log (every 60 s = 1 min) ─────────────────────────
        tick += 1
        if tick % log_interval == 0 or t_kin_rem <= 0:
            tick_log.append({
                "t_s":     t_elapsed,
                "T_c":     T_pot,
                "m_w_kg":  m_water,
                "t_kr_s":  t_kin_rem,
            })

    # ── Store final state ──────────────────────────────────────────────────────
    inp.update({
        "t_elapsed_s":         t_elapsed,
        "T_pot_c":             T_pot,
        "m_water_current":     m_water,
        "t_kinetic_remaining": t_kin_rem,
        "flag_dry_boil":       flag_dry,
        "flag_overheat":       flag_over,
        "t_boil_reached_s":    t_boil_reached,
        "tick_log":            tick_log,
        "P_in_kw":             P_in_kw,
        "Q_in_per_tick":       Q_in,
    })
    return inp


# =============================================================================
# SECTION 6 — POST-PROCESSING OUTPUTS  (PRD §6)
# =============================================================================

def post_process(inp: dict) -> dict:
    """
    PRD §6A — Fuel output:
      Total_Pellets_Required = (t_elapsed / 3600) × FAN_HIGH × 1000  [grams]

    PRD §6B — Safety diagnostics.

    PRD §6C — Academic 3-Phase Receipt (display only — no physics impact):
      Phase 1 (Ignition):   first 15% of t_elapsed
      Phase 2 (Steady):     middle 65% of t_elapsed
      Phase 3 (Char/Coals): final 20% of t_elapsed
    """
    t_elapsed = inp["t_elapsed_s"]

    # ── §6A: Ultimate fuel output ──────────────────────────────────────────────
    pellets_g = (t_elapsed / 3600.0) * FAN_HIGH * 1000.0
    inp["pellets_required_g"] = pellets_g
    inp["pellets_required_kg"] = pellets_g / 1000.0

    # ── §6C: 3-Phase time windows (illustrative only) ──────────────────────────
    t_ph1 = 0.15 * t_elapsed
    t_ph2 = 0.65 * t_elapsed
    t_ph3 = 0.20 * t_elapsed

    inp.update({
        "t_phase1_s":  t_ph1,
        "t_phase2_s":  t_ph2,
        "t_phase3_s":  t_ph3,
    })
    return inp


# =============================================================================
# SECTION — PROFESSIONAL RECEIPT PRINTER
# =============================================================================

def _bar(fraction: float, width: int = 28) -> str:
    filled = int(min(max(fraction, 0.0), 1.0) * width)
    return "|" + "█" * filled + "░" * (width - filled) + "|"


def print_receipt(inp: dict) -> None:
    """Render the full calculation receipt to stdout."""

    now_str  = datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    t_el     = inp["t_elapsed_s"]
    t_el_min = t_el / 60.0
    pellet   = inp["pellet"]
    pellets_g = inp["pellets_required_g"]
    q_in_total = inp["P_in_kw"] * t_el    # total energy supplied by stove [kJ]

    def box(label: str, val: str, unit: str = "", col: str = CYN) -> None:
        u   = f" {unit}" if unit else ""
        v   = f"{val}{u}"
        pad = max(0, 62 - len(label) - len(v))
        print(_c(f"  | {label}", col)
              + _c(v, GRN, BLD)
              + _c(" " * pad + "|", col))

    def div(col: str = CYN) -> None:
        print(_c("  +" + "─" * 66 + "+", col))

    def title(t: str, col: str = CYN) -> None:
        print(_c(f"\n  +── {t} " + "─" * max(2, 60 - len(t)) + "+", col, BLD))

    # ── Header ────────────────────────────────────────────────────────────────
    print()
    print(_c("=" * 72, CYN, BLD))
    print(_c("  IIT DELHI  |  1Hz Transient Biomass Cookstove Simulator  |  v1", BLD, WHT))
    print(_c("=" * 72, CYN, BLD))
    print(_c(f"  Generated : {now_str}", DIM))
    print(_c("  Engine    : 1Hz Discrete Transient Solver (Lumped Capacitance, PRD v1)", DIM))
    print()

    # ── Inputs & geometry ─────────────────────────────────────────────────────
    title("SIMULATION INPUTS  &  HIDDEN GEOMETRY")
    box("Dish",                  inp["dish_name"])
    if inp["dish"].variable_water:
        box("Water volume",      f"{inp['water_liters']:.2f}",  "L")
    else:
        box("Portions",          str(inp["portions"]),           "serving(s)")
    box("Ambient temperature",   f"{inp['t_ambient_c']:.1f}",   "°C")
    box("Vessel",                inp["vessel_name"])
    box("Vessel mass",           f"{inp['m_pot']:.3f}",         "kg")
    box("Vessel Cp",             f"{inp['cp_pot']:.3f}",        "kJ/kg·K")
    box("Lid state",             inp["lid_label"])
    box("Lid factor",            f"{inp['lid_factor']:.2f}")
    box("Pellet",                pellet.name)
    box("GCV (conservative)",    f"{pellet.conservative_gcv_kj:,.1f}", "kJ/kg")
    box("Kinetic cook time",     f"{inp['t_kinetic_s']/60:.1f}", "min (user-approved)")
    div()
    title("DERIVED GEOMETRY  (PRD §4B — hidden, cylinder h=d)")
    box("Initial food mass",     f"{inp['m_food']*1000:.1f}",           "g")
    box("Initial water mass",    f"{inp['m_water_initial']*1000:.1f}",  "g")
    box("Cylinder volume",       f"{inp['V_m3']*1e6:.2f}",              "mL  (V = m_water/1000)")
    box("Cylinder diameter",     f"{inp['d_m']*100:.2f}",               "cm")
    box("Vessel surface area A", f"{inp['A_m2']*1e4:.2f}",              "cm²  (A = 1.25 π d²)")
    box("η_geom",                f"{inp['eta_geom']:.6f}",              f"= MAX_EFF × clamp(√(m_w/5), 0.25, 1)")
    box("P_in (constant)",       f"{inp['P_in_kw']:.6f}",              "kW  = (FAN_HIGH/3600) × GCV × η_geom")
    div()

    # ── Simulation telemetry ───────────────────────────────────────────────────
    title("SIMULATION TELEMETRY  (1 Hz loop, sparse log @ 1-min intervals)")
    print(_c(f"  {'Time (min)':<12} {'T_pot (°C)':<14} {'Water (g)':<14} {'Kinetic rem (s)':<18}", DIM))
    print(_c("  " + "─" * 60, DIM))
    for rec in inp["tick_log"]:
        t_min_disp = rec["t_s"] / 60.0
        print(_c(
            f"  {t_min_disp:>9.1f}    "
            f"{rec['T_c']:>10.2f}    "
            f"{rec['m_w_kg']*1000:>10.1f}    "
            f"{rec['t_kr_s']:>12.1f}",
            WHT
        ))
    if inp["t_boil_reached_s"] is not None:
        print(_c(
            f"\n  ► Boiling point (100°C) first reached at "
            f"t = {inp['t_boil_reached_s']/60:.1f} min", GRN
        ))
    div()

    # ── Energy summary ─────────────────────────────────────────────────────────
    title("ENERGY SUMMARY")
    box("Total simulation time",  f"{t_el:.0f}",        "s")
    box("Total simulation time",  f"{t_el_min:.2f}",    "min")
    box("Stove power (P_in)",     f"{inp['P_in_kw']:.6f}", "kW  [constant — high fan]")
    box("Total energy supplied",  f"{q_in_total:.2f}",  "kJ  (P_in × t_elapsed)")
    box("Water remaining",        f"{inp['m_water_current']*1000:.1f}", "g")
    div()

    # ── §6B: Safety diagnostics ────────────────────────────────────────────────
    title("SAFETY DIAGNOSTICS  (PRD §6B)", col=RED if (inp["flag_dry_boil"] or inp["flag_overheat"]) else GRN)
    if inp["flag_dry_boil"]:
        print(_c("  [FATAL]  DRY-BOIL DETECTED  — m_water reached 0 during simulation.", RED, BLD))
        print(_c("           Food is burnt. Increase water or reduce cook time.", RED))
    else:
        print(_c("  ✓  No dry-boil event detected.", GRN))

    if inp["flag_overheat"]:
        print(_c("  [CRITICAL]  VESSEL OVERHEAT  — T_pot exceeded 150°C.", RED, BLD))
        print(_c("              Check vessel mass and cook time.", RED))
    else:
        print(_c(f"  ✓  Final vessel temperature: {inp['T_pot_c']:.1f} °C  (≤ 150°C safe limit).", GRN))
    div()

    # ── §6C: 3-Phase combustion receipt (illustrative — no physics impact) ─────
    title("ACADEMIC 3-PHASE COMBUSTION TIMELINE  (PRD §6C — DISPLAY ONLY)", col=BLU)
    print(_c("  DISCLAIMER: Illustrative post-processing receipt.", DIM))
    print(_c("  This section does NOT alter the governing fuel physics.", DIM, BLD))
    print()

    ph1_start = 0.0
    ph1_end   = inp["t_phase1_s"]
    ph2_end   = ph1_end + inp["t_phase2_s"]
    ph3_end   = ph2_end + inp["t_phase3_s"]

    print(_c(
        f"  Phase 1 — IGNITION    "
        f"(t = 0 → {ph1_end/60:.1f} min, 15% of {t_el_min:.1f} min)",
        BLU, BLD
    ))
    print(_c(
        "    Stove reaching operating temperature. Expect initial smoke.", DIM
    ))
    print(_c(
        f"  Phase 2 — STEADY STATE"
        f"(t = {ph1_end/60:.1f} → {ph2_end/60:.1f} min, 65% of {t_el_min:.1f} min)",
        BLU, BLD
    ))
    print(_c(
        "    Optimal clean combustion and rapid boiling.", DIM
    ))
    print(_c(
        f"  Phase 3 — CHAR / COALS"
        f"(t = {ph2_end/60:.1f} → {ph3_end/60:.1f} min, 20% of {t_el_min:.1f} min)",
        BLU, BLD
    ))
    print(_c(
        "    Fresh wood exhausted. Simmer finishing on highly efficient radiant char.", DIM
    ))
    div(col=BLU)

    # ── §6A: Ultimate fuel result ──────────────────────────────────────────────
    mass_str = f"{pellets_g:.1f} g"
    if pellets_g >= 1000:
        mass_str += f"  ({pellets_g/1000:.3f} kg)"

    print()
    print(_c("=" * 72, ORG, BLD))
    print(_c("  RECOMMENDED PELLET LOAD  (PRD §6A)", BLD, WHT))
    print()
    print(_c("  Formula:  Pellets = (t_elapsed / 3600) × FAN_HIGH × 1000", DIM))
    print(_c(
        f"            Pellets = ({t_el:.0f} / 3600) × {FAN_HIGH} × 1000", DIM
    ))
    print()
    print(_c("  " + "─" * 60, ORG))
    print(_c(f"  ►  {mass_str:<20} ◄", ORG, BLD)
          + _c(f"  [{pellet.name}]", DIM))
    print(_c("  " + "─" * 60, ORG))
    print()
    print(_c("  ► Add ≥ 10% safety margin for real-world procurement.", DIM))
    print(_c("  ► Simulation used HIGH FAN (0.78 kg/hr) throughout — conservative.", DIM))
    print(_c("=" * 72, ORG, BLD))
    print()


# =============================================================================
# SECTION — MAIN ENTRY POINT
# =============================================================================

def main() -> None:
    """
    Orchestrates the 4-step pre-simulation + 1Hz loop + post-processing.

    Execution order (per PRD architecture):
      collect_inputs()  → §4A: validated user parameters + DB lookups
      setup_geometry()  → §4B/4C: hidden geometry + η_geom
      zero_state()      → §4D: initialise T_pot, m_water, timers
      run_1hz_loop()    → §5: 1-second transient solver
      post_process()    → §6A/B/C: fuel calc + diagnostics + receipt
      print_receipt()   → terminal output
    """
    while True:
        try:
            inp = collect_inputs()
            inp = setup_geometry(inp)
            inp = zero_state(inp)

            _hdr("RUNNING 1Hz TRANSIENT PHYSICS LOOP")
            print(_c(
                f"  Simulating at 1 Hz until {inp['t_kinetic_s']/60:.1f} min of kinetic time\n"
                f"  completes above 99°C.  This may take a moment for long cooks...", DIM
            ))

            inp = run_1hz_loop(inp)

            print(_c(
                f"\n  ✓  Loop complete.  "
                f"t_elapsed = {inp['t_elapsed_s']:.0f} s "
                f"({inp['t_elapsed_s']/60:.1f} min)", GRN
            ))

            inp = post_process(inp)
            print_receipt(inp)

            raw = _prompt(
                "Calculate another dish? Enter to restart / type 'q' to quit",
                default="Enter"
            ).strip().lower()
            if raw == "q":
                print(_c("\n  Goodbye.\n", DIM))
                break

        except KeyboardInterrupt:
            _quit_or_continue()
        except KeyError as exc:
            print(_c(f"\n  [X]  Database lookup error: {exc}\n", RED))
        except Exception as exc:
            print(_c(f"\n  [X]  Unexpected error: {exc}\n", RED))
            raise


if __name__ == "__main__":
    main()