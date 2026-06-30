"""
utensil_db.py — Cookware Vessel Database
IIT Delhi · Biomass Pellet Cookstove Simulator

=============================================================================
PURPOSE
=============================================================================
Provides m_pot (vessel empty mass) and Cp_pot (vessel specific heat) for the
1Hz transient simulator's Q_vessel and MCp_total terms.

NOTE ON p_loss_kw: Earlier versions of this engine used a fixed P_loss (kW)
per vessel type as a simplified heat-loss model. The 1Hz transient PRD
replaces that simplification with a first-principles Q_out computed every
tick from Stefan-Boltzmann radiation + Newtonian convection using the
vessel's actual surface area and current T_pot (see main_logic.py §5.3).
p_loss_kw is therefore NOT used by the transient engine; it is retained
here only as a reference value for any future steady-state comparison.

=============================================================================
SOURCES
=============================================================================
[1] MacCarty et al. (2010). Energy Sustain. Dev., 14(3), 214-222.
    [P_loss reference values for open Al pot, kadhai]
[2] NIST WebBook — Aluminium thermophysical properties (Cp_Al = 0.897 kJ/kg·K)
[3] Incropera et al. (2007). Fundamentals of Heat and Mass Transfer, 7th ed.,
    Table A.1 / A.2 (Cp values: Aluminium, Cast Iron, Stainless Steel)
[4] Engineering reference: typical Indian cookware empty masses
    (5L aluminium pot, kadhai, tawa, pressure cooker body) — informed estimate,
    no single peer-reviewed source exists for exact retail vessel masses.
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Utensil:
    """
    Immutable vessel record.

    Attributes
    ----------
    name         : display name
    mass_kg      : empty vessel mass (kg)         [source: 4, informed estimate]
    cp_kj_kgk    : vessel material specific heat (kJ/kg·K)  [sources: 2, 3]
    p_loss_kw    : reference-only steady-state heat loss (kW) [source: 1]
                   NOT used by the 1Hz transient engine (Q_out is computed
                   from first principles every tick instead).
    is_pressure  : True if vessel is a sealed pressure cooker
    material_note: human-readable Cp derivation note
    """
    name:          str
    mass_kg:       float
    cp_kj_kgk:     float
    p_loss_kw:     float
    is_pressure:   bool = False
    material_note: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Utensil.name must not be empty.")
        if self.mass_kg <= 0:
            raise ValueError(f"[{self.name}] mass_kg must be > 0, got {self.mass_kg}")
        if self.cp_kj_kgk <= 0:
            raise ValueError(f"[{self.name}] cp_kj_kgk must be > 0, got {self.cp_kj_kgk}")
        if self.p_loss_kw < 0:
            raise ValueError(f"[{self.name}] p_loss_kw must be >= 0, got {self.p_loss_kw}")


# ---------------------------------------------------------------------------
# MASTER UTENSIL DATABASE
# ---------------------------------------------------------------------------
# mass_kg, cp_kj_kgk, p_loss_kw carried forward unchanged from the values
# already verified in the prior version of main_logic.py (same sources).
# ---------------------------------------------------------------------------

UTENSIL_DB: dict[str, Utensil] = {

    "Standard Aluminium Pot (5L)": Utensil(
        name="Standard Aluminium Pot (5L)",
        mass_kg=1.20,
        cp_kj_kgk=0.897,
        p_loss_kw=0.20,   # MacCarty et al. (2010) [1] — reference only
        is_pressure=False,
        material_note="Aluminium, Cp=0.897 kJ/kg·K [NIST/Incropera Table A.1]",
    ),

    "Kadhai / Wok": Utensil(
        name="Kadhai / Wok",
        mass_kg=0.90,
        cp_kj_kgk=0.897,
        p_loss_kw=0.25,   # larger open surface; +25% vs standard pot [1]
        is_pressure=False,
        material_note="Aluminium, Cp=0.897 kJ/kg·K [NIST/Incropera Table A.1]",
    ),

    "Frying Pan / Tawa": Utensil(
        name="Frying Pan / Tawa",
        mass_kg=0.70,
        cp_kj_kgk=0.460,
        p_loss_kw=0.30,   # large flat surface; +50% vs standard pot [estimate]
        is_pressure=False,
        material_note="Cast Iron, Cp=0.460 kJ/kg·K [Incropera Table A.1]",
    ),

    "Pressure Cooker (5L)": Utensil(
        name="Pressure Cooker (5L)",
        mass_kg=1.80,
        cp_kj_kgk=0.897,
        p_loss_kw=0.08,   # sealed; minimal convective/evap loss [estimate]
        is_pressure=True,
        material_note="Aluminium body, Cp=0.897 kJ/kg·K [NIST/Incropera Table A.1]",
    ),

}


def get_utensil_names() -> list[str]:
    """Return the list of utensil names in canonical (insertion) order."""
    return list(UTENSIL_DB.keys())


def get_utensil(name: str) -> Utensil:
    """Return a Utensil by name, raising KeyError if unknown."""
    if name not in UTENSIL_DB:
        raise KeyError(f"Unknown utensil: {name!r}. Available: {get_utensil_names()}")
    return UTENSIL_DB[name]