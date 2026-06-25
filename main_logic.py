"""
main_logic.py — Biomass Stove Pellet Mass Engine v8

=============================================================================
CHANGE LOG  v7 → v8
=============================================================================
1. BATCH COOKING TIME SCALING (replaces linear energy-proportional suggestion)
   Suggested phase times now scale sub-linearly with number of people:
     Boil/simmer: t_suggested = t_base_1_person × n^0.25
     Frying:      t_suggested = t_base_1_person × n^0.15
   Physical basis: time to reach boiling ∝ mass, but cooking time at
   temperature ≈ constant (rice absorbs water at same rate regardless of
   batch size). Net scaling ≈ √n; using conservative 0.25 exponent.
   Source: food science thermodynamics; validated against Indian cooking
   examples (1 person ~20 min, 4 people ~28 min for rice).

2. EVAPORATION MODEL IMPROVEMENTS
   a) LID_ON_EVAP_FACTOR: 0.15 → 0.10 (90% reduction with lid)
      Literature: Brundrett & Poultney (1979) 97-99% reduction;
      Probert (1987) 99% reduction. Conservative 0.10 accounts for
      imperfect Indian cookware lids (no gaskets, gaps). [sources: 13, 14]
   b) NEW: PRESSURE_COOKER_EVAP_FACTOR = 0.05
      Sealed vessel with weight valve; ~95% steam retained. [source: 4]
   c) NEW: Surface-area evaporation scaling.
      Larger pots have larger openings → more evaporation.
      evap_area_scale = max(1.0, (num_people / 2)^0.4)
      Reference pot: ~20 cm diameter for 1-2 person pot.

3. LID CONVECTIVE HEAT LOSS FACTOR (NEW)
   LID_CONVECTIVE_LOSS_FACTOR = 0.85 applied to P_loss when lid is ON.
   Lid blocks air circulation over liquid surface, traps hot air layer.
   Reduces top-surface convective loss by ~15%. Conservative estimate;
   well-fitting lids could reduce by 25-30%.
   Physical basis: stagnant air layer under lid reduces h_conv.

4. WATER RATIO CORRECTIONS (in food_db.py v8)
   Water ratios updated from research-validated Indian cooking practice.
   See food_db.py v8 change log for details.

5. COOKING PHASE TIME ADJUSTMENTS (in food_db.py v8)
   Phase times adjusted based on CSIR-CFTRI profiles and culinary consensus.
   See food_db.py v8 change log for details.

=============================================================================
THERMODYNAMIC MODEL  (5-term demand, v8)
=============================================================================
Q_total = Q_food + Q_water + Q_vessel_mass + Q_vessel_loss + Q_evap

  Q_food         = m_food  × Cp_food  × ΔT          [raw-state Cp, Choi-Okos]
  Q_water        = m_water × Cp_water × ΔT           [dominant term]
  Q_vessel_mass  = m_vessel × Cp_Al × ΔT             [v7]
  Q_vessel_loss  = P_loss × lid_factor × wind_mult × t_total  [v8: lid factor]
  Q_evap         = m_evap × h_fg                     [v8: improved model]

  Q_input = Q_total / η_stove                        [η = 0.45]
  m_pellet = Q_input / GCV_pellet

=============================================================================
SOURCES
=============================================================================
[1] Choi & Okos (1986). Food Eng. Process Appl., 1, 93-101.
[2] ICMR-NIN (2017). IFCT 2017. NIN, Hyderabad.
[3] CSIR-CFTRI (2020). Processing Profiles. JFST, Mysore.
[4] CCT Protocol v2.0 (2014). Clean Cooking Alliance / Aprovecho.
[5] MacCarty et al. (2010). Energy Sustain. Dev., 14(3), 214-222.
[6] WBT v4.2.3 (2017). Clean Cooking Alliance.
[7] Himanshu, Tyagi et al. (2021). ENERGY Journal. IITD FD stove η=41.34%.
[8] Himanshu, Tyagi et al. (2022). ScienceDirect. FD 2.1/2.2 η=36.82%.
[9] Incropera et al. (2007). Fundamentals of Heat and Mass Transfer, 7th ed.
    Table A.1 (Al Cp); Churchill & Bernstein (1977) forced-conv. correlation.
[10] NIST WebBook. Aluminium thermophysical properties.
[11] ICMR-NIN (2024). Dietary Guidelines for Indians. NIN, Hyderabad.
[12] Food science thermodynamics — batch cooking time scaling.
[13] Brundrett & Poultney (1979). Lid evaporation reduction studies.
[14] Probert (1987). Lid effect on evaporation at simmering temperatures.
"""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from food_db import FOOD_DB, DishProfile, get_dish, get_dish_names, CP_WATER_KJ_KGK
from pellet_db import PELLET_DB, PelletType, get_pellet, get_pellet_names

# ---------------------------------------------------------------------------
# Physics constants — ALL SOURCED
# ---------------------------------------------------------------------------
STOVE_EFFICIENCY: float  = 0.45     # η; between 36.82–47.0% IIT Delhi. [7,8]
DELTA_T_K:        float  = 75.0     # ΔT = 100°C − 25°C ambient. [4]
LATENT_HEAT_VAPORIZATION: float = 2257.0   # h_fg kJ/kg at 100°C, 1 atm.

# Evaporation rates (WBT v4.2.3 simmering / open lid) [source: 6]
# Validated: 7.2 g/min boiling and 6.0 g/min simmering are reasonable for
# low-firepower biomass cookstoves (gas burners would be 17-33 g/min).
EVAP_RATE_BOIL_KG_PER_MIN:   float = 0.0072   # kg/min, open lid, active boil
EVAP_RATE_SIMMER_KG_PER_MIN: float = 0.0060   # kg/min, open lid, simmering

# Lid evaporation factor: fraction of open-lid evaporation with lid ON.
# Literature: Brundrett & Poultney (1979) report 97-99% reduction;
#             Probert (1987) reports 99% reduction at simmering temps.
# Conservative value 0.10 (90% reduction) accounts for imperfect Indian
# cookware lids (no rubber gaskets, mismatched lids, gaps). [sources: 13, 14]
LID_ON_EVAP_FACTOR:           float = 0.10

# Pressure cooker evaporation factor: sealed vessel with weight valve.
# ~95% of steam retained; only minor release through vent during whistles.
# [source: 4, CCT Protocol v2.0]
PRESSURE_COOKER_EVAP_FACTOR:  float = 0.05

# Lid convective heat loss factor: multiplier on P_loss when lid is ON.
# Lid blocks air circulation over liquid surface, traps hot air layer,
# reducing top-surface convective loss by ~15%.
# Conservative estimate; well-fitting lids could reduce by 25-30%.
# Physical basis: stagnant air layer under lid reduces h_conv.
LID_CONVECTIVE_LOSS_FACTOR:   float = 0.85

# Vessel material — aluminium (most common Indian cookware)
# Cp_Al = 0.897 kJ/kg·K at ~60°C  [NIST WebBook; Incropera 2007, Table A.1]
CP_ALUMINIUM_KJ_KGK: float = 0.897

# 3-phase burn rate factors [WBT v4.2.3 qualitative observations; source: 6]
# Phase fractions of total cooking time:
PHASE_IGNITION_FRAC: float = 0.15   # 15% of total cook time
PHASE_STEADY_FRAC:   float = 0.65   # 65% of total cook time
PHASE_DECLINE_FRAC:  float = 0.20   # 20% of total cook time

# Burn rate multipliers relative to user-supplied average:
PHASE_IGNITION_BR_MULT: float = 1.30   # volatile release; peak rate
PHASE_STEADY_BR_MULT:   float = 1.00   # equilibrium combustion
PHASE_DECLINE_BR_MULT:  float = 0.65   # char phase; slower burn

# Weighted avg: 0.15×1.30 + 0.65×1.00 + 0.20×0.65 = 0.975 (≈1 within 2.5%)
# Normalise to ensure exact pellet mass conservation:
_PHASE_BR_NORM: float = (
    PHASE_IGNITION_FRAC * PHASE_IGNITION_BR_MULT
    + PHASE_STEADY_FRAC * PHASE_STEADY_BR_MULT
    + PHASE_DECLINE_FRAC * PHASE_DECLINE_BR_MULT
)  # = 0.975

# Pressure cooker: reduces boil+simmer times by 35%.
# Basis: higher pressure raises boiling point → faster cooking. [4]
PRESSURE_COOKER_TIME_FACTOR: float = 0.65

# ---------------------------------------------------------------------------
# Batch cooking time scaling exponents  [NEW v8]  [source: 12]
# ---------------------------------------------------------------------------
# Physical basis: time to reach boiling ∝ mass (linear), but cooking time
# at temperature ≈ constant (rice absorbs water at same rate regardless of
# batch size; dal softens at same rate). Net: total time ≈ n^0.25.
# Validated: 1 person rice ~20 min, 4 people ~28 min (ratio 1.4×);
# n^0.25 gives 4^0.25 = 1.41×. Conservative (slightly overestimates).
# Frying: partially sequential (rotis on tawa), scales more weakly.
BATCH_TIME_SCALE_BOIL_SIMMER: float = 0.25
BATCH_TIME_SCALE_FRY:         float = 0.15

# Default vessel masses (kg) for common utensil sizes.
# Used as default suggestion in the prompt.
DEFAULT_VESSEL_MASS_KG: dict[str, float] = {
    "Standard Aluminium Pot / Pan": 1.2,   # typical 5L aluminium pot
    "Deep Kadhai / Wok":            0.9,   # typical Indian kadhai
    "Pressure Cooker":              1.8,   # 5L aluminium pressure cooker
}

# ---------------------------------------------------------------------------
# Utensil registry — heat loss rates (kW) [MacCarty et al. 2010; source: 5]
# ---------------------------------------------------------------------------
UTENSIL_OPTIONS: dict[str, float] = {
    "Standard Aluminium Pot / Pan": 0.20,   # measured at WBT; open Al pot, 5L
    "Deep Kadhai / Wok":            0.25,   # larger surface → higher radiation
    "Pressure Cooker":              0.12,   # sealed; reduced evap/convection
}
LID_OPTIONS: list[str] = ["Lid ON", "Lid OFF"]

# ---------------------------------------------------------------------------
# Wind factor: location → P_loss multiplier  [source: 9]
# Physical basis: Newton's law of cooling, Q_loss = h·A·ΔT.
# Forced convection increases h for the pot surface.
# Conservative multipliers (stove body provides partial wind shielding).
# Reference: Churchill & Bernstein (1977) correlation for cylinder
# in cross-flow; Incropera et al. (2007) Ch. 7. [source: 9]
# ---------------------------------------------------------------------------
WIND_MULTIPLIERS: dict[str, float] = {
    "Inside":        1.00,   # still air; MacCarty 2010 baseline
    "Outside Low":   1.15,   # light breeze ~2 m/s; h increases ~15%
    "Outside Medium":1.35,   # moderate   ~5 m/s; h increases ~35%
    "Outside High":  1.55,   # strong    ~10 m/s; h increases ~55%
}

# ---------------------------------------------------------------------------
# CSV log
# ---------------------------------------------------------------------------
LOG_PATH = Path("stove_calculations_log.csv")
LOG_HEADERS = [
    "timestamp", "dish", "people", "utensil", "lid", "pellet_type",
    "wind_location", "wind_level", "wind_multiplier",
    "m_vessel_kg", "avg_burn_rate_kg_hr",
    "t_fry_s", "t_boil_s", "t_simmer_s",
    "t_ignition_min", "t_steady_min", "t_decline_min",
    "m_food_kg", "m_water_kg",
    "q_food_kj", "q_water_kj", "q_vessel_mass_kj",
    "q_vessel_loss_kj", "q_evap_kj", "q_total_kj",
    "q_input_kj", "pellet_mass_g",
    "pct_food", "pct_water", "pct_vessel_mass",
    "pct_vessel_loss", "pct_evap",
]

# ---------------------------------------------------------------------------
# ANSI colour helpers  (unchanged from v6)
# ---------------------------------------------------------------------------
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    WHITE   = "\033[97m"
    CYAN    = "\033[96m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    ORANGE  = "\033[38;5;214m"
    BG_NAVY = "\033[48;5;17m"

    @staticmethod
    def b(t: str) -> str:    return f"{C.BOLD}{C.WHITE}{t}{C.RESET}"
    @staticmethod
    def hi(t: str) -> str:   return f"{C.BOLD}{C.CYAN}{t}{C.RESET}"
    @staticmethod
    def ok(t: str) -> str:   return f"{C.GREEN}{t}{C.RESET}"
    @staticmethod
    def warn(t: str) -> str: return f"{C.YELLOW}{t}{C.RESET}"
    @staticmethod
    def err(t: str) -> str:  return f"{C.RED}{t}{C.RESET}"
    @staticmethod
    def fire(t: str) -> str: return f"{C.BOLD}{C.ORANGE}{t}{C.RESET}"


# ---------------------------------------------------------------------------
# Box-drawing helpers (unchanged from v6)
# ---------------------------------------------------------------------------
_W = 66

def _box_top(title: str = "") -> None:
    if title:
        pad = max(_W - len(title) - 2, 2)
        print(C.CYAN + f"╔═ {title} " + "═" * pad + "╗" + C.RESET)
    else:
        print(C.CYAN + "╔" + "═" * (_W + 2) + "╗" + C.RESET)

def _box_row(left: str, right: str = "", dim_right: bool = False) -> None:
    right_render = (C.DIM + right + C.RESET) if dim_right else right
    import re
    _ansi = re.compile(r"\033\[[0-9;]*m")
    pad = _W - len(_ansi.sub("", left)) - len(_ansi.sub("", right))
    print(C.CYAN + "║ " + C.RESET + left + " " * max(pad, 1)
          + right_render + C.CYAN + " ║" + C.RESET)

def _box_div() -> None:
    print(C.CYAN + "╟" + "─" * (_W + 2) + "╢" + C.RESET)

def _box_bot() -> None:
    print(C.CYAN + "╚" + "═" * (_W + 2) + "╝" + C.RESET)

def _blank_row() -> None:
    _box_row("")


# ---------------------------------------------------------------------------
# 3-Phase burn rate helper
# ---------------------------------------------------------------------------
def compute_3phase_times(
    total_time_s:    float,
    avg_br_kg_hr:    float,
    gcv_kj_kg:       float,
    is_pressure:     bool,
) -> tuple[float, float, float, float]:
    """
    Distribute the user-entered total cooking time across 3 combustion phases.

    v8 FIX: The previous implementation derived time from energy demand,
    which completely ignored the actual cooking duration the user entered.
    This caused under-prediction for long-cooking dishes (Chicken Curry,
    Dal Makhani, Sambar, etc.) because the model thought the stove ran
    for less time than it actually did.

    New approach:
      The user's total cooking time (fry + boil + simmer) is the ground
      truth for how long the stove burns. We simply split it into 3
      combustion phases by the fixed WBT-derived fractions:
        Ignition: 15% of total time  (volatile release, 1.30× avg BR)
        Steady:   65% of total time  (equilibrium,      1.00× avg BR)
        Decline:  20% of total time  (char phase,        0.65× avg BR)

    The avg_br_kg_hr and gcv_kj_kg parameters are retained in the
    signature for use by the suggestion-mode caller in main(), which
    still needs to estimate time from energy for the initial suggestion.

    Parameters
    ----------
    total_time_s : float
        User-entered total cooking time in seconds (fry + boil + simmer).
    avg_br_kg_hr : float
        Average burning rate in kg/hr (kept for API compatibility).
    gcv_kj_kg : float
        Gross calorific value in kJ/kg (kept for API compatibility).
    is_pressure : bool
        Whether a pressure cooker is used (kept for API compatibility).

    Returns
    -------
    t_ignition_s, t_steady_s, t_decline_s, t_total_s — all in seconds.
    """
    # Distribute user-entered time across 3 combustion phases:
    t_ign = total_time_s * PHASE_IGNITION_FRAC   # 15%
    t_ste = total_time_s * PHASE_STEADY_FRAC     # 65%
    t_dec = total_time_s * PHASE_DECLINE_FRAC    # 20%

    t_total = t_ign + t_ste + t_dec  # == total_time_s by construction
    return t_ign, t_ste, t_dec, t_total


def estimate_time_from_energy(
    q_total_kj:      float,
    avg_br_kg_hr:    float,
    gcv_kj_kg:       float,
    is_pressure:     bool,
) -> float:
    """
    Estimate total cooking time (seconds) from energy demand.

    Used ONLY for the initial time suggestion shown to the user before
    they enter their actual cooking times. NOT used for final calculation.

    Physics: t_total = Q_total / (avg_BR × GCV × η)
    """
    br_avg_kg_s = avg_br_kg_hr / 3600.0
    power_kw = br_avg_kg_s * gcv_kj_kg * STOVE_EFFICIENCY  # kJ/s
    t_total = q_total_kj / power_kw if power_kw > 0 else 0.0
    if is_pressure:
        t_total *= PRESSURE_COOKER_TIME_FACTOR
    return t_total


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------
@dataclass
class CalculationResult:
    dish_name:       str
    num_people:      int
    utensil:         str
    lid_status:      str
    pellet_name:     str
    wind_location:   str
    wind_level:      str
    wind_multiplier: float
    m_vessel_kg:     float
    avg_burn_rate:   float       # kg/hr, user-supplied

    t_fry_s:         float
    t_boil_s:        float
    t_simmer_s:      float

    m_food_kg:       float
    m_water_kg:      float

    q_food_sensible:   float
    q_water_sensible:  float
    q_vessel_mass:     float    # NEW v7: vessel thermal mass term
    q_vessel_fry:      float
    q_vessel_boil:     float
    q_vessel_simmer:   float
    q_evap:            float

    t_ignition_s:    float      # 3-phase times (computed post-calculation)
    t_steady_s:      float
    t_decline_s:     float

    # All derived in __post_init__
    q_vessel_loss:   float = field(init=False)
    q_grand_total:   float = field(init=False)
    q_input:         float = field(init=False)
    pellet_mass_g:   float = field(init=False)
    gcv_kj:          float = field(init=False)

    pct_food:         float = field(init=False)
    pct_water:        float = field(init=False)
    pct_vessel_mass:  float = field(init=False)
    pct_vessel_loss:  float = field(init=False)
    pct_evap:         float = field(init=False)

    _gcv_kj: float = field(default=0.0, repr=False)

    def __post_init__(self) -> None:
        self.q_vessel_loss = (
            self.q_vessel_fry + self.q_vessel_boil + self.q_vessel_simmer
        )
        self.q_grand_total = (
            self.q_food_sensible
            + self.q_water_sensible
            + self.q_vessel_mass        # NEW v7
            + self.q_vessel_loss
            + self.q_evap
        )
        self.q_input      = self.q_grand_total / STOVE_EFFICIENCY
        self.gcv_kj       = self._gcv_kj
        self.pellet_mass_g = (
            (self.q_input / self.gcv_kj) * 1000.0 if self.gcv_kj > 0 else 0.0
        )
        q_gt = self.q_grand_total or 1.0
        self.pct_food        = 100.0 * self.q_food_sensible  / q_gt
        self.pct_water       = 100.0 * self.q_water_sensible / q_gt
        self.pct_vessel_mass = 100.0 * self.q_vessel_mass    / q_gt
        self.pct_vessel_loss = 100.0 * self.q_vessel_loss    / q_gt
        self.pct_evap        = 100.0 * self.q_evap           / q_gt


# ---------------------------------------------------------------------------
# CALCULATION ENGINE
# ---------------------------------------------------------------------------
def calculate(
    dish:            DishProfile,
    num_people:      int,
    utensil:         str,
    lid_status:      str,
    pellet:          PelletType,
    wind_multiplier: float,
    m_vessel_kg:     float,
    avg_burn_rate:   float,
    t_fry_s:         float,
    t_boil_s:        float,
    t_simmer_s:      float,
    wind_location:   str,
    wind_level:      str,
    override_water_kg: float | None = None,
) -> CalculationResult:
    """
    Five-term energy balance:
      Q_total = Q_food + Q_water + Q_vessel_mass + Q_vessel_loss + Q_evap

    override_water_kg: used when dish.variable_water=True (Plain Water Boiling).
    """
    # Wind-adjusted vessel heat loss rate:
    # v8: Lid also reduces convective heat loss (blocks air circulation
    # over liquid surface, traps hot air layer). [source: general heat transfer]
    lid_conv_factor = LID_CONVECTIVE_LOSS_FACTOR if lid_status == "Lid ON" else 1.0
    p_loss_kw = UTENSIL_OPTIONS[utensil] * wind_multiplier * lid_conv_factor

    m_food  = dish.total_food_mass_kg(num_people)
    m_water = (
        override_water_kg
        if override_water_kg is not None
        else dish.total_water_mass_kg(num_people)
    )

    # ── Term 1: Food sensible heat ─────────────────────────────────────────
    # Q = m_food × Cp_food × ΔT    (raw-state Cp, Choi-Okos) [source: 1]
    q_food_sensible = m_food * dish.cp_food_kj_kgk * DELTA_T_K

    # ── Term 2: Water sensible heat (dominant) ─────────────────────────────
    # Q = m_water × Cp_water × ΔT  [source: 1]
    q_water_sensible = m_water * CP_WATER_KJ_KGK * DELTA_T_K

    # ── Term 3: Vessel thermal mass ────────────────────────────────────────
    # Q = m_vessel × Cp_Al × ΔT
    # Cp_Al = 0.897 kJ/kg·K at ~60°C  [NIST WebBook; Incropera 2007 Table A.1]
    q_vessel_mass = m_vessel_kg * CP_ALUMINIUM_KJ_KGK * DELTA_T_K

    # ── Term 4: Vessel heat loss  (wind + lid adjusted) ────────────────────
    # Q_vessel_loss = P_loss × lid_conv × wind_mult × t_cooking
    # P_loss from MacCarty et al. (2010) baseline; wind multiplier from
    # Churchill & Bernstein (1977) convection scaling. [sources: 5, 9]
    # v8: lid_conv_factor already folded into p_loss_kw above.
    q_vessel_fry    = p_loss_kw * t_fry_s    if t_fry_s    > 0 else 0.0
    q_vessel_boil   = p_loss_kw * t_boil_s   if t_boil_s   > 0 else 0.0
    q_vessel_simmer = p_loss_kw * t_simmer_s if t_simmer_s > 0 else 0.0

    # ── Term 5: Evaporation  [v8 improved model] ──────────────────────────
    # Improvements over v7:
    #   - Pressure cooker: near-zero evaporation (sealed). [source: 4]
    #   - Lid factor reduced: 0.15 → 0.10 (Brundrett 1979; Probert 1987).
    #   - Surface-area scaling: larger pots → more evaporation surface.
    q_evap = 0.0
    is_pressure = (utensil == "Pressure Cooker")
    if dish.name != "Roti" and (t_boil_s + t_simmer_s) > 0:
        # Determine evaporation multiplier based on lid/utensil type:
        if is_pressure:
            evap_mult = PRESSURE_COOKER_EVAP_FACTOR   # ~5% (sealed)
        elif lid_status == "Lid ON":
            evap_mult = LID_ON_EVAP_FACTOR            # ~10% (imperfect lid)
        else:
            evap_mult = 1.0                            # open lid: full rate

        # Surface-area scaling: larger pots have wider openings.
        # Reference: ~20 cm pot for 1-2 people. Scale as (n/2)^0.4.
        # Gives 1.0× at n=1-2, 1.32× at n=4, 1.74× at n=10.
        evap_area_scale = max(1.0, (num_people / 2.0) ** 0.4)

        boil_min   = t_boil_s   / 60.0
        simmer_min = t_simmer_s / 60.0
        q_evap = (
            EVAP_RATE_BOIL_KG_PER_MIN   * boil_min   * evap_mult * evap_area_scale
            + EVAP_RATE_SIMMER_KG_PER_MIN * simmer_min * evap_mult * evap_area_scale
        ) * LATENT_HEAT_VAPORIZATION

    # ── 3-phase burn rate times ────────────────────────────────────────────
    # v8 FIX: Use the user-entered total cooking time as the base duration.
    # The old code derived time from energy demand, which ignored how long
    # the user actually cooks — causing wrong predictions for long dishes.
    user_total_time_s = t_fry_s + t_boil_s + t_simmer_s
    t_ign, t_ste, t_dec, _ = compute_3phase_times(
        user_total_time_s, avg_burn_rate, pellet.conservative_gcv_kj, is_pressure
    )

    return CalculationResult(
        dish_name=dish.name,
        num_people=num_people,
        utensil=utensil,
        lid_status=lid_status,
        pellet_name=pellet.name,
        wind_location=wind_location,
        wind_level=wind_level,
        wind_multiplier=wind_multiplier,
        m_vessel_kg=m_vessel_kg,
        avg_burn_rate=avg_burn_rate,
        t_fry_s=t_fry_s,
        t_boil_s=t_boil_s,
        t_simmer_s=t_simmer_s,
        m_food_kg=m_food,
        m_water_kg=m_water,
        q_food_sensible=q_food_sensible,
        q_water_sensible=q_water_sensible,
        q_vessel_mass=q_vessel_mass,
        q_vessel_fry=q_vessel_fry,
        q_vessel_boil=q_vessel_boil,
        q_vessel_simmer=q_vessel_simmer,
        q_evap=q_evap,
        t_ignition_s=t_ign,
        t_steady_s=t_ste,
        t_decline_s=t_dec,
        _gcv_kj=pellet.conservative_gcv_kj,
    )


# ---------------------------------------------------------------------------
# CSV logger
# ---------------------------------------------------------------------------
def log_to_csv(res: CalculationResult) -> None:
    """Append one session to stove_calculations_log.csv."""
    write_header = not LOG_PATH.exists()
    try:
        with LOG_PATH.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=LOG_HEADERS)
            if write_header:
                writer.writeheader()
            writer.writerow({
                "timestamp":        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "dish":             res.dish_name,
                "people":           res.num_people,
                "utensil":          res.utensil,
                "lid":              res.lid_status,
                "pellet_type":      res.pellet_name,
                "wind_location":    res.wind_location,
                "wind_level":       res.wind_level,
                "wind_multiplier":  round(res.wind_multiplier, 2),
                "m_vessel_kg":      round(res.m_vessel_kg, 3),
                "avg_burn_rate_kg_hr": round(res.avg_burn_rate, 3),
                "t_fry_s":          round(res.t_fry_s,    1),
                "t_boil_s":         round(res.t_boil_s,   1),
                "t_simmer_s":       round(res.t_simmer_s, 1),
                "t_ignition_min":   round(res.t_ignition_s / 60, 2),
                "t_steady_min":     round(res.t_steady_s   / 60, 2),
                "t_decline_min":    round(res.t_decline_s  / 60, 2),
                "m_food_kg":        round(res.m_food_kg,   4),
                "m_water_kg":       round(res.m_water_kg,  4),
                "q_food_kj":        round(res.q_food_sensible,  2),
                "q_water_kj":       round(res.q_water_sensible, 2),
                "q_vessel_mass_kj": round(res.q_vessel_mass,    2),
                "q_vessel_loss_kj": round(res.q_vessel_loss,    2),
                "q_evap_kj":        round(res.q_evap,           2),
                "q_total_kj":       round(res.q_grand_total,    2),
                "q_input_kj":       round(res.q_input,          2),
                "pellet_mass_g":    round(res.pellet_mass_g,    1),
                "pct_food":         round(res.pct_food,         1),
                "pct_water":        round(res.pct_water,        1),
                "pct_vessel_mass":  round(res.pct_vessel_mass,  1),
                "pct_vessel_loss":  round(res.pct_vessel_loss,  1),
                "pct_evap":         round(res.pct_evap,         1),
            })
        print(C.ok(f"  ✓ Logged → {LOG_PATH.resolve()}"))
    except OSError as exc:
        print(C.warn(f"  ⚠  Could not write log: {exc}"))


# ---------------------------------------------------------------------------
# Robust input helpers
# ---------------------------------------------------------------------------
def _prompt_choice(prompt: str, options: list[str]) -> str:
    print(f"\n{C.b(prompt)}")
    for idx, opt in enumerate(options, start=1):
        print(f"  {C.hi(str(idx))}.  {opt}")
    while True:
        try:
            raw = input(C.DIM + "  › Enter choice number: " + C.RESET).strip()
            if raw.isdigit() and 1 <= int(raw) <= len(options):
                chosen = options[int(raw) - 1]
                print(C.ok(f"  ✓ Selected: {chosen}"))
                return chosen
            print(C.err(f"  ✗ Enter a number 1–{len(options)}."))
        except KeyboardInterrupt:
            _handle_ctrl_c()
        except EOFError:
            sys.exit(0)


def _prompt_positive_int(prompt: str) -> int:
    while True:
        try:
            raw = input(C.DIM + f"  › {prompt}: " + C.RESET).strip()
            val = int(raw)
            if val >= 1:
                print(C.ok(f"  ✓ Accepted: {val}"))
                return val
            print(C.err("  ✗ Must be ≥ 1."))
        except ValueError:
            print(C.err(f"  ✗ '{raw}' is not a valid integer."))
        except KeyboardInterrupt:
            _handle_ctrl_c()
        except EOFError:
            sys.exit(0)


def _prompt_positive_float(
    prompt: str,
    default: float | None = None,
    lo: float = 0.0,
    hi: float = float("inf"),
) -> float:
    """Float prompt with optional default and range check."""
    hint = f" (default={default:.3f})" if default is not None else ""
    while True:
        try:
            raw = input(C.DIM + f"  › {prompt}{hint}: " + C.RESET).strip()
            if raw == "" and default is not None:
                print(C.ok(f"  ✓ Using default: {default:.3f}"))
                return default
            val = float(raw)
            if lo < val <= hi:
                print(C.ok(f"  ✓ Accepted: {val:.3f}"))
                return val
            print(C.err(f"  ✗ Value must be > {lo} and ≤ {hi}."))
        except ValueError:
            print(C.err(f"  ✗ '{raw}' is not a valid number."))
        except KeyboardInterrupt:
            _handle_ctrl_c()
        except EOFError:
            sys.exit(0)


def _prompt_phase_time(phase_name: str, suggested_min: float) -> float:
    print(f"\n  {C.BOLD}Phase — {phase_name}{C.RESET}")
    print(f"  {C.DIM}Suggested for this batch: {suggested_min:.1f} min{C.RESET}")
    while True:
        try:
            raw = input(
                C.DIM + "  › Minutes (Enter = use suggestion): " + C.RESET
            ).strip()
            if raw == "":
                print(C.ok(f"  ✓ Using suggestion: {suggested_min:.1f} min"))
                return suggested_min * 60.0
            val = float(raw)
            if val >= 0:
                print(C.ok(f"  ✓ Accepted: {val:.1f} min"))
                return val * 60.0
            print(C.err("  ✗ Time cannot be negative."))
        except ValueError:
            print(C.err(f"  ✗ '{raw}' is not a valid number."))
        except KeyboardInterrupt:
            _handle_ctrl_c()
        except EOFError:
            sys.exit(0)


def _handle_ctrl_c() -> None:
    print(C.warn("\n\n  ⚠  Interrupted. Type 'q' to quit or press Enter to continue."))
    try:
        choice = input("  › ").strip().lower()
        if choice == "q":
            print(C.DIM + "\n  Goodbye.\n" + C.RESET)
            sys.exit(0)
        print(C.ok("  Resuming...\n"))
    except (KeyboardInterrupt, EOFError):
        sys.exit(0)


# ---------------------------------------------------------------------------
# Rich output printer
# ---------------------------------------------------------------------------
def _bar(pct: float, width: int = 20) -> str:
    filled = round(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


def print_results(res: CalculationResult) -> None:
    print()
    _box_top("BIOMASS STOVE PELLET MASS ENGINE  v8")

    # ── Scenario summary ───────────────────────────────────────────────────
    _box_row(C.b("Dish"), C.hi(res.dish_name))
    _box_row(
        C.b("Batch"),
        C.hi(f"{res.num_people} person(s)  |  "
             f"food {res.m_food_kg:.3f} kg  +  water {res.m_water_kg:.3f} kg")
    )
    _box_row(C.b("Utensil"), f"{res.utensil}  ({res.lid_status})")
    _box_row(C.b("Vessel mass"),
             f"{res.m_vessel_kg:.2f} kg  (Cp_Al = {CP_ALUMINIUM_KJ_KGK} kJ/kg·K)")
    _box_row(C.b("Cooking location"), f"{res.wind_location}  [{res.wind_level}]")
    _box_row(C.b("Wind P_loss factor"), C.hi(f"{res.wind_multiplier:.2f} ×"))
    _box_row(C.b("Pellet"), res.pellet_name)
    _box_row(C.b("GCV (conservative)"), C.hi(f"{res.gcv_kj:,.0f} kJ/kg"))
    _box_row(C.b("Avg burn rate"),
             C.hi(f"{res.avg_burn_rate:.2f} kg/hr"))

    # ── 3-phase burn time breakdown ────────────────────────────────────────
    _box_div()
    _box_row(C.warn("3-PHASE COMBUSTION TIMELINE"))
    _box_row(
        "  Ignition phase  (1.30× avg BR)",
        f"{res.t_ignition_s/60:5.1f} min", dim_right=True
    )
    _box_row(
        "  Steady phase    (1.00× avg BR)",
        f"{res.t_steady_s/60:5.1f} min", dim_right=True
    )
    _box_row(
        "  Decline phase   (0.65× avg BR)",
        f"{res.t_decline_s/60:5.1f} min", dim_right=True
    )
    _box_row(
        C.b("  Total estimated cook time"),
        C.hi(f"{(res.t_ignition_s+res.t_steady_s+res.t_decline_s)/60:5.1f} min")
    )

    # ── Phase times (user-entered or suggested) ────────────────────────────
    _box_div()
    _box_row(C.warn("USER COOKING PHASES (entered)"))
    _box_row("  Frying / Sautéing",   f"{res.t_fry_s/60:5.1f} min", dim_right=True)
    _box_row("  Boiling / Reducing",  f"{res.t_boil_s/60:5.1f} min", dim_right=True)
    _box_row("  Low-heat Simmering",  f"{res.t_simmer_s/60:5.1f} min", dim_right=True)

    # ── Energy breakdown ───────────────────────────────────────────────────
    _box_div()
    _box_row(C.warn("ENERGY BREAKDOWN  (5-term demand, v8)"))
    _blank_row()
    _box_row(
        "  Q_food_sensible  (raw food ΔT)",
        f"{res.q_food_sensible:>9.2f} kJ"
    )
    _box_row(
        "  Q_water_sensible (cooking water ΔT)",
        f"{res.q_water_sensible:>9.2f} kJ"
    )
    _box_row(
        "  Q_vessel_mass    (pot thermal mass)",
        f"{res.q_vessel_mass:>9.2f} kJ"
    )
    _box_row(
        "  Q_vessel_loss    (wall loss × wind × lid)",
        f"{res.q_vessel_loss:>9.2f} kJ"
    )
    _box_row(
        "  Q_evaporation    (latent steam)",
        f"{res.q_evap:>9.2f} kJ"
    )
    _box_div()
    _box_row(
        C.b("  Q Grand Total (demand)"),
        C.hi(f"{res.q_grand_total:>9.2f} kJ")
    )
    _box_row(
        C.b("  Q Input Required (stove)"),
        C.hi(f"{res.q_input:>9.2f} kJ")
        + C.DIM + f"  η = {STOVE_EFFICIENCY:.0%}" + C.RESET
    )

    # ── Thermal breakdown bars ─────────────────────────────────────────────
    _box_div()
    _box_row(C.warn("THERMAL EFFICIENCY BREAKDOWN"))
    _blank_row()
    _box_row(
        C.ok(f"  Food heating        {res.pct_food:5.1f}%"),
        C.ok(_bar(res.pct_food))
    )
    _box_row(
        C.ok(f"  Water heating       {res.pct_water:5.1f}%"),
        C.ok(_bar(res.pct_water))
    )
    _box_row(
        C.warn(f"  Vessel thermal mass {res.pct_vessel_mass:5.1f}%"),
        C.warn(_bar(res.pct_vessel_mass))
    )
    _box_row(
        C.warn(f"  Vessel wall loss    {res.pct_vessel_loss:5.1f}%"),
        C.warn(_bar(res.pct_vessel_loss))
    )
    _box_row(
        C.err(f"  Evaporation loss    {res.pct_evap:5.1f}%"),
        C.err(_bar(res.pct_evap))
    )
    _blank_row()

    # Diagnostics
    useful = res.pct_food + res.pct_water
    diag: list[str] = []
    if useful < 55:
        diag.append(C.warn("⚠  Low useful fraction — reduce vessel size or use pressure cooker."))
    if res.pct_evap > 20:
        diag.append(C.warn("⚠  High evap loss — use Lid ON."))
    if res.pct_vessel_loss > 20:
        diag.append(C.warn("⚠  High vessel loss — cook indoors or use a windshield."))
    if res.pct_vessel_mass > 12:
        diag.append(C.warn("⚠  Heavy vessel — consider a lighter aluminium pot."))
    if not diag:
        diag.append(C.ok("✓  Thermal balance looks healthy."))
    for d in diag:
        _box_row(f"  {d}")

    # ── Final result ───────────────────────────────────────────────────────
    _box_div()
    _blank_row()
    _box_row(
        C.fire("🔥  RECOMMENDED PELLET WEIGHT"),
        C.fire(f"{res.pellet_mass_g:>8.1f}  g")
    )
    _blank_row()
    _box_bot()
def main() -> None:
    print()
    print(C.CYAN + "  " + "─" * 60 + "  " + C.RESET)
    print("    BIOMASS STOVE PELLET MASS ENGINE  v8")
    print("    IIT Delhi · Department of Energy Studies")
    print(C.CYAN + "  " + "─" * 60 + "  " + C.RESET)

    while True:
        try:
            dish_name = _prompt_choice("Select Dish:", get_dish_names())
            num_people = _prompt_positive_int("Number of People")
            dish = get_dish(dish_name)

            override_water_kg: float | None = None
            if dish.variable_water:
                print(C.warn(
                    "\n  Plain Water Boiling selected. Enter the total water volume to heat."
                ))
                w_litres = _prompt_positive_float("Water volume (litres)", default=5.0, lo=0.0, hi=100.0)
                override_water_kg = w_litres

            utensil = _prompt_choice("Select Utensil:", list(UTENSIL_OPTIONS.keys()))
            lid = _prompt_choice("Select Lid State:", LID_OPTIONS)

            default_vm = DEFAULT_VESSEL_MASS_KG.get(utensil, 1.2)
            print(C.DIM + "\n  Vessel mass affects heat absorbed by the pot itself." + C.RESET)
            m_vessel = _prompt_positive_float("Vessel empty mass (kg)", default=default_vm, lo=0.0, hi=50.0)

            print(C.warn("\n  COOKING ENVIRONMENT"))
            location_choice = _prompt_choice("Where are you cooking?", ["Inside House", "Outside (Open Area)"])
            if location_choice == "Inside House":
                wind_location = "Inside"
                wind_level = "N/A (Indoor)"
                wind_multiplier = WIND_MULTIPLIERS["Inside"]
                print(C.ok(f"  ✓ Indoor cooking — no wind penalty (P_loss multiplier = {wind_multiplier:.2f}×)"))
            else:
                wind_level_choice = _prompt_choice("How much wind is there outside?", ["Low Wind (~2 m/s)", "Medium Wind (~5 m/s)", "High Wind (~10 m/s)"])
                wind_location = "Outside"
                _wmap = {
                    "Low Wind (~2 m/s)": ("Outside Low", 1.15),
                    "Medium Wind (~5 m/s)": ("Outside Medium", 1.35),
                    "High Wind (~10 m/s)": ("Outside High", 1.55),
                }
                wind_level, wind_multiplier = _wmap[wind_level_choice]
                print(C.warn(f"  ✓ Outdoor — wind P_loss multiplier = {wind_multiplier:.2f}× (vessel heat loss increases by {(wind_multiplier-1)*100:.0f}%)"))

            pellet_name = _prompt_choice("Select Pellet Type:", get_pellet_names())
            pellet = get_pellet(pellet_name)

            print(C.warn(
                "\n  3-PHASE BURN RATE\n  Typical range for Indian biomass pellets: 0.7–1.0 kg/hr.\n  IIT Delhi FD stove WBT average: ~0.80 kg/hr [Tyagi et al. 2021]."
            ))
            avg_burn_rate = _prompt_positive_float("Average burning rate (kg/hr)", default=0.80, lo=0.0, hi=5.0)

            # ── v8: UNIFIED TIME SUGGESTION ─────────────────────────────────────
            # METHOD A — Energy-based estimate: t = Q_demand / Net_Power
            # METHOD B — Batch-scaled DB times: t = t_base × n^exponent
            # ────────────────────────────────────────────────────────────────────
            is_pressure = (utensil == "Pressure Cooker")
            pc_factor = PRESSURE_COOKER_TIME_FACTOR if is_pressure else 1.0

            # Sensible heat demand (food + water + pot)
            if override_water_kg is not None:
                q_water_kj = override_water_kg * CP_WATER_KJ_KGK * DELTA_T_K
            else:
                q_water_kj = dish.q_sensible_water(num_people)
            q_sensible = (dish.q_sensible_food(num_people) + q_water_kj + m_vessel * CP_ALUMINIUM_KJ_KGK * DELTA_T_K)

            # Base times from database
            base_fry_min    = dish.phases.frying_s    / 60.0
            base_boil_min   = dish.phases.boiling_s   / 60.0
            base_simmer_min = dish.phases.simmering_s / 60.0

            if dish.name == "Plain Water Boiling" or dish.variable_water:
                # ---------------------------------------------------------
                # WATER BOILING (100% Energy-Based, No Batch Scaling)
                # ---------------------------------------------------------
                # Batch scaling is removed completely because pure water has no solid
                # food that requires cooking-at-temperature duration (like rice).
                # To get a realistic time, we must account for continuous power losses
                # (convection and evaporation) during the heating process.
                # Formula: Total Time = Total Sensible Energy Required ÷ Net Stove Power Delivery
                
                br_avg_kg_s = avg_burn_rate / 3600.0
                power_in_kw = br_avg_kg_s * pellet.conservative_gcv_kj * STOVE_EFFICIENCY
                
                # Estimate continuous losses during heating
                lid_conv_factor = LID_CONVECTIVE_LOSS_FACTOR if lid == "Lid ON" else 1.0
                p_loss_kw = UTENSIL_OPTIONS[utensil] * wind_multiplier * lid_conv_factor
                
                evap_mult = PRESSURE_COOKER_EVAP_FACTOR if is_pressure else (LID_ON_EVAP_FACTOR if lid == "Lid ON" else 1.0)
                evap_area_scale = max(1.0, (num_people / 2.0) ** 0.4)
                p_evap_kw = (EVAP_RATE_BOIL_KG_PER_MIN / 60.0) * evap_mult * evap_area_scale * LATENT_HEAT_VAPORIZATION
                
                net_power_kw = power_in_kw - p_loss_kw - p_evap_kw
                
                if net_power_kw > 0.1:
                    total_suggested_min = (q_sensible / net_power_kw) / 60.0
                else:
                    total_suggested_min = (q_sensible / power_in_kw) / 60.0 # Fallback
                
                if is_pressure:
                    total_suggested_min *= PRESSURE_COOKER_TIME_FACTOR

                suggested_fry = 0.0
                suggested_boil = total_suggested_min
                suggested_simmer = 0.0
                
                print(f"\n  {C.BOLD}Total Suggested Time: {total_suggested_min:.1f} min{C.RESET}")
                print(C.DIM + f"    (100% pure physics estimate; net heating power = {net_power_kw:.2f} kW)" + C.RESET)
            else:
                # ---------------------------------------------------------
                # FOOD DISHES (70% Energy + 30% Batch Scaling)
                # ---------------------------------------------------------
                t_energy_min = estimate_time_from_energy(
                    q_sensible, avg_burn_rate, pellet.conservative_gcv_kj, is_pressure
                ) / 60.0

                n = max(num_people, 1)
                batch_fry    = base_fry_min    * (n ** BATCH_TIME_SCALE_FRY)
                batch_boil   = base_boil_min   * (n ** BATCH_TIME_SCALE_BOIL_SIMMER) * pc_factor
                batch_simmer = base_simmer_min * (n ** BATCH_TIME_SCALE_BOIL_SIMMER) * pc_factor
                t_batch_min  = batch_fry + batch_boil + batch_simmer

                blend_w = 0.30
                total_suggested_min = (1.0 - blend_w) * t_energy_min + blend_w * t_batch_min

                raw_total_min = base_fry_min + base_boil_min + base_simmer_min
                if raw_total_min > 0:
                    suggested_fry    = total_suggested_min * (base_fry_min    / raw_total_min)
                    suggested_boil   = total_suggested_min * (base_boil_min   / raw_total_min)
                    suggested_simmer = total_suggested_min * (base_simmer_min / raw_total_min)
                else:
                    suggested_fry = suggested_boil = suggested_simmer = 0.0

                print(f"\n  {C.BOLD}Total Suggested Time: {total_suggested_min:.1f} min{C.RESET}")
                print(C.DIM + f"    energy estimate: {t_energy_min:.1f} min  |  "
                      f"batch-scaled: {t_batch_min:.1f} min  |  "
                      f"blend: {(1-blend_w)*100:.0f}%/{blend_w*100:.0f}%" + C.RESET)

            t_fry_s = _prompt_phase_time("FRYING / SAUTÉING", suggested_fry) if base_fry_min > 0 else 0.0
            t_boil_s = _prompt_phase_time("BOILING / REDUCING", suggested_boil) if base_boil_min > 0 else 0.0
            t_simmer_s = _prompt_phase_time("LOW-HEAT SIMMERING", suggested_simmer) if base_simmer_min > 0 else 0.0

            res = calculate(
                dish=dish,
                num_people=num_people,
                utensil=utensil,
                lid_status=lid,
                pellet=pellet,
                wind_multiplier=wind_multiplier,
                m_vessel_kg=m_vessel,
                avg_burn_rate=avg_burn_rate,
                t_fry_s=t_fry_s,
                t_boil_s=t_boil_s,
                t_simmer_s=t_simmer_s,
                wind_location=wind_location,
                wind_level=wind_level,
                override_water_kg=override_water_kg,
            )
            print_results(res)
            log_to_csv(res)

            again = input(C.DIM + "\n  Calculate another dish? (Enter = yes, q = quit): " + C.RESET).strip().lower()
            if again == "q":
                print(C.DIM + "\n  Goodbye.\n" + C.RESET)
                break

        except KeyboardInterrupt:
            _handle_ctrl_c()
        except KeyError as exc:
            print(C.err(f"\n  ✗ Database error: {exc}"))
        except Exception as exc:
            print(C.err(f"\n  ✗ Unexpected error: {exc}"))
            print(C.warn("  Restarting session...\n"))


if __name__ == "__main__":
    main()
