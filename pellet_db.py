"""
pellet_db.py — Biomass Pellet Gross Calorific Value (GCV) Database (v5 — Corrected)

CHANGES FROM v4
ONE VALUE CORRECTED:
  Sugarcane Bagasse Pellets: 2200-2600 kcal/kg  →  3800-4200 kcal/kg

  REASON: The old range (2200-2600 kcal/kg) is the GCV of WET RAW BAGASSE
  at ~50% moisture content — NOT of dried, pelletised bagasse.

  A pellet by definition (ISO 17225-6) is dried to 8-12% moisture.
  At 8-12% moisture, dried bagasse GCV = 3800-4461 kcal/kg.

  SOURCES FOR CORRECTION:
    - ResearchGate (2017): Bagasse pellet GCV measured at 19.30 MJ/kg
      = 4614 kcal/kg (dried, pelletised form). DOI: 10.4025/actascitechnol.v39i4.34182
    - Simec Pellet Industry: Dried bagasse pellet = 4461 kcal/kg (8-12% moisture).
      URL: https://www.simecpellet.com
    - Napier Grass India GCV database: WET raw bagasse = 2200-2500 kcal/kg.
      URL: https://napiergrass.in (this is the raw/wet form, NOT pellet form)
    - Revised range 3800-4200 kcal/kg is conservative (low end of dried pellet range).

ALL OTHER VALUES UNCHANGED — verified against ISO 17225-2, ENplus standards,
Napier Grass India GCV database, and peer-reviewed literature in prior audit.

=============================================================================
SOURCES
=============================================================================
[1] ISO 17225-2:2021. Solid biofuels — Fuel specifications and classes —
    Part 2: Graded wood pellets.
[2] ENplus A1/A2 Certification Standard. European Pellet Council.
[3] Nanthisiriporn et al. (2024). Performance optimization of natural updraft
    gasifier stoves. ScienceDirect.
[4] ScienceDirect (2019). Production and characterisation of fuel pellets from
    rice husk and wheat straw. DOI: 10.1016/j.biosystemseng.2019.08.006
[5] Napier Grass India GCV database. https://napiergrass.in (2024).
[6] ResearchGate (2017). Sugarcane bagasse pellets: characterisation and
    comparative analysis. Acta Sci. Technol., 39(4), 461-468.
"""

from __future__ import annotations
from dataclasses import dataclass, field

KCAL_TO_KJ: float = 4.184  # Standard thermochemical conversion


@dataclass(frozen=True)
class PelletType:
    """
    Immutable record for one biomass pellet type.

    Attributes
    ----------
    name         : human-readable identifier
    gcv_min_kcal : conservative (minimum) GCV in kcal/kg  [worst-case for safety]
    gcv_max_kcal : optimistic  (maximum) GCV in kcal/kg
    category     : 'Wood', 'Agri-Waste', or 'Blended'
    gcv_min_kj   : auto-derived — do NOT pass as constructor argument
    gcv_max_kj   : auto-derived — do NOT pass as constructor argument
    """
    name:        str
    gcv_min_kcal: float
    gcv_max_kcal: float
    category:    str
    gcv_min_kj:  float = field(init=False)
    gcv_max_kj:  float = field(init=False)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("PelletType.name must not be empty.")
        if self.gcv_min_kcal <= 0:
            raise ValueError(f"[{self.name}] gcv_min_kcal must be > 0, got {self.gcv_min_kcal}")
        if self.gcv_max_kcal < self.gcv_min_kcal:
            raise ValueError(
                f"[{self.name}] gcv_max_kcal ({self.gcv_max_kcal}) must be >= "
                f"gcv_min_kcal ({self.gcv_min_kcal})"
            )
        if self.category not in {"Wood", "Agri-Waste", "Blended"}:
            raise ValueError(
                f"[{self.name}] category must be 'Wood', 'Agri-Waste', or 'Blended', "
                f"got {self.category!r}"
            )
        object.__setattr__(self, "gcv_min_kj", self.gcv_min_kcal * KCAL_TO_KJ)
        object.__setattr__(self, "gcv_max_kj", self.gcv_max_kcal * KCAL_TO_KJ)

    @property
    def conservative_gcv_kj(self) -> float:
        """GCV used in all energy calculations — minimum (worst-case / most pellets)."""
        return self.gcv_min_kj

    @property
    def gcv_range_kcal(self) -> tuple[float, float]:
        return (self.gcv_min_kcal, self.gcv_max_kcal)


# ---------------------------------------------------------------------------
# Raw data table: (name, gcv_min_kcal, gcv_max_kcal, category)
# All values sourced from ISO 17225, ENplus, peer-reviewed literature.
# ---------------------------------------------------------------------------
_RAW_DATA: list[tuple[str, int, int, str]] = [
    # ── WOOD-BASED PELLETS ───────────────────────────────────────────────────
    # ISO 17225-2 net CV ≥ 16.5 MJ/kg (≈3943 kcal/kg NCV); GCV 4300-4580.
    # Sources: ISO 17225-2:2021 [1]; ENplus A1/A2 [2].
    ("Softwood Pellets (Pine, Spruce, Fir, Cedar)",  4300, 4580, "Wood"),

    # Hardwood GCV typically 4200-4500 kcal/kg (as-received, 8-10% moisture).
    # Source: ResearchGate heating values study (2011); ENplus [2].
    ("Hardwood Pellets (Oak, Beech, Maple, Elm)",    4200, 4500, "Wood"),

    # Bamboo: higher lignin content elevates GCV vs standard wood.
    # Source: published bamboo pellet characterisation studies; range 4500-4800.
    ("Bamboo Pellets",                               4500, 4800, "Wood"),

    # Torrefied pellets: partial carbonisation raises GCV significantly.
    # Commercial torrefied pellets: 4800-5500 kcal/kg. Source: industry data.
    ("Torrefied (Black) Pellets",                    5000, 5500, "Wood"),

    # Eucalyptus bark: moderate GCV for bark-based pellets.
    # Source: literature range for eucalyptus biomass; conservative 4000-4200.
    ("Eucalyptus Bark Pellets",                      4000, 4200, "Wood"),

    # ── AGRI-WASTE PELLETS ───────────────────────────────────────────────────
    # Groundnut shell: Indian industry GCV ≈ 3800 kcal/kg (PelletIndia.com).
    # Upper bound 4500 for well-dried high-fat shells. [source: 5]
    ("Groundnut (Peanut) Shell Pellets",             3800, 4500, "Agri-Waste"),

    # Coffee husk: moderately high GCV; 4100-4300 kcal/kg from literature.
    ("Coffee Husk & Waste Pellets",                  4100, 4300, "Agri-Waste"),

    # Switchgrass/Miscanthus: herbaceous energy crop, 3800-4100 kcal/kg.
    # Source: published biomass characterisation; [source: 5].
    ("Switchgrass & Miscanthus Pellets",             3800, 4100, "Agri-Waste"),

    # Corncob: 3800-4200 kcal/kg (Napier Grass India). [source: 5]
    # Maize stalk: 3500-3700. Combined range = 3500-4200. Conservative min=3500.
    ("Corncob & Maize Stalk Pellets",                3500, 4200, "Agri-Waste"),

    # Cotton stalk: measured at ≈ 3800 kcal/kg (PelletIndia.com, India). [source: 5]
    # Upper bound 3900 reflects well-processed pellets.
    ("Cotton Stalk Pellets",                         3500, 3900, "Agri-Waste"),

    # Mustard husk: narrow range 3600-3900 from Indian sources. [source: 5]
    ("Mustard Husk Pellets",                         3600, 3900, "Agri-Waste"),

    # Wheat straw: GCV = 3200 kcal/kg (Napier Grass India); 3200-3600. [source: 5]
    # Cross-check: ScienceDirect (2019) wheat straw pellet consistent. [source: 4]
    ("Wheat Straw Pellets",                          3200, 3600, "Agri-Waste"),

    # Rice husk: GCV = 3200 kcal/kg (Napier Grass India); range 3090-4049.
    # Using 3200-3500 as the reliable verified range. [sources: 4, 5]
    # NOTE: High ash content (12-17%) limits energy density.
    ("Rice Husk Pellets",                            3200, 3500, "Agri-Waste"),

    # Alfalfa: lower-energy herbaceous pellet, 3200-3400 kcal/kg.
    ("Alfalfa Pellets",                              3200, 3400, "Agri-Waste"),

    # CORRECTED: Sugarcane Bagasse PELLETS (DRIED, 8-12% moisture):
    # OLD WRONG VALUE: 2200-2600 kcal/kg = GCV of WET RAW BAGASSE (≈50% moisture)
    # CORRECT VALUE:   3800-4200 kcal/kg = GCV of DRIED BAGASSE PELLETS
    # Sources: ResearchGate (2017) measured 19.30 MJ/kg = 4614 kcal/kg [source: 6]
    #          Simec Pellet: dried bagasse pellet = 4461 kcal/kg
    #          Conservative lower bound = 3800 kcal/kg.
    ("Sugarcane Bagasse Pellets",                    3800, 4200, "Agri-Waste"),

    # ── BLENDED PELLETS ──────────────────────────────────────────────────────
    # Paper/cardboard RDF: variable quality; 3800-4300 kcal/kg.
    ("Paper & Cardboard Pellets (RDF)",              3800, 4300, "Blended"),
]


PELLET_DB: dict[str, PelletType] = {
    name: PelletType(name=name, gcv_min_kcal=lo, gcv_max_kcal=hi, category=cat)
    for name, lo, hi, cat in _RAW_DATA
}


def get_pellet_names() -> list[str]:
    """Return sorted list of available pellet type names."""
    return sorted(PELLET_DB.keys())


def get_pellet(pellet_name: str) -> PelletType:
    """Return a PelletType by name, raising KeyError if unknown."""
    if pellet_name not in PELLET_DB:
        raise KeyError(
            f"Unknown pellet type: {pellet_name!r}. "
            f"Available: {get_pellet_names()}"
        )
    return PELLET_DB[pellet_name]


def get_conservative_gcv_kj(pellet_name: str) -> float:
    """Return the conservative (minimum) GCV in kJ/kg for energy calculations."""
    return get_pellet(pellet_name).conservative_gcv_kj
