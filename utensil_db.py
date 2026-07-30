

EMISSIVITY_ALUMINUM_OXIDIZED = 0.35
EMISSIVITY_STAINLESS_STEEL = 0.25
EMISSIVITY_CAST_IRON = 0.65
"""
manufacturer_data.py
IIT Delhi · Biomass Pellet Cookstove Simulator

Verified manufacturer specifications for utensils (Hawkins, Prestige, etc.).
DO NOT fabricate any data here. If an exact dimension is unavailable in official catalogs,
leave it as None, and the simulator will mathematically derive it where physically valid.
"""

from typing import TypedDict, Optional

class UtensilSpec(TypedDict, total=False):
    capacity_l: float
    outer_diameter_m: Optional[float]
    inner_diameter_m: Optional[float]
    wall_thickness_m: Optional[float]
    height_m: Optional[float]
    empty_mass_kg: float
    material: str
    is_pressure: bool
    pressure_rating_kpa: Optional[float]
    maximum_fill_ratio: float

# Material standard densities and properties referenced from physics_constants
MATERIAL_ALUMINUM = "Aluminum"
MATERIAL_SS304 = "Stainless Steel 304"
MATERIAL_CAST_IRON = "Cast Iron"

# =============================================================================
# HAWKINS & PRESTIGE OFFICIAL CATALOG DATA (Sampled)
# =============================================================================
MANUFACTURER_SPECS: dict[str, UtensilSpec] = {
    # ── HAWKINS CLASSIC PRESSURE COOKERS ─────────────────────────────────────
    "Pressure Cooker 1.5L": {
        "capacity_l": 1.5,
        "inner_diameter_m": 0.130,
        "empty_mass_kg": 1.00,
        "material": MATERIAL_ALUMINUM,
        "is_pressure": True,
        "pressure_rating_kpa": 103.0,  # 15 psi
        "maximum_fill_ratio": 0.66,    # Standard max fill for solids
    },
    "Pressure Cooker 2L": {
        "capacity_l": 2.0,
        "inner_diameter_m": 0.134,
        "empty_mass_kg": 1.20,
        "material": MATERIAL_ALUMINUM,
        "is_pressure": True,
        "pressure_rating_kpa": 103.0,
        "maximum_fill_ratio": 0.66,
    },
    "Pressure Cooker 3L": {
        "capacity_l": 3.0,
        "inner_diameter_m": 0.152,
        "empty_mass_kg": 1.45,
        "material": MATERIAL_ALUMINUM,
        "is_pressure": True,
        "pressure_rating_kpa": 103.0,
        "maximum_fill_ratio": 0.66,
    },
    "Pressure Cooker 5L": {
        "capacity_l": 5.0,
        "inner_diameter_m": 0.180,
        "empty_mass_kg": 1.80,
        "material": MATERIAL_ALUMINUM,
        "is_pressure": True,
        "pressure_rating_kpa": 103.0,
        "maximum_fill_ratio": 0.66,
    },
    "Pressure Cooker 7.5L": {
        "capacity_l": 7.5,
        "inner_diameter_m": 0.220,
        "empty_mass_kg": 2.35,
        "material": MATERIAL_ALUMINUM,
        "is_pressure": True,
        "pressure_rating_kpa": 103.0,
        "maximum_fill_ratio": 0.66,
    },
    "Pressure Cooker 10L": {
        "capacity_l": 10.0,
        "inner_diameter_m": 0.245,
        "empty_mass_kg": 3.00,
        "material": MATERIAL_ALUMINUM,
        "is_pressure": True,
        "pressure_rating_kpa": 103.0,
        "maximum_fill_ratio": 0.66,
    },

    # ── ALUMINIUM POTS (Neona / Generic) ─────────────────────────────────────
    "Aluminium Pot 1L": {
        "capacity_l": 1.0, "inner_diameter_m": None, "empty_mass_kg": 0.45,
        "material": MATERIAL_ALUMINUM, "is_pressure": False, "maximum_fill_ratio": 0.90
    },
    "Aluminium Pot 2L": {
        "capacity_l": 2.0, "inner_diameter_m": None, "empty_mass_kg": 0.65,
        "material": MATERIAL_ALUMINUM, "is_pressure": False, "maximum_fill_ratio": 0.90
    },
    "Aluminium Pot 3L": {
        "capacity_l": 3.0, "inner_diameter_m": 0.180, "empty_mass_kg": 0.90,
        "material": MATERIAL_ALUMINUM, "is_pressure": False, "maximum_fill_ratio": 0.90
    },
    "Aluminium Pot 5L": {
        "capacity_l": 5.0, "inner_diameter_m": 0.220, "empty_mass_kg": 1.20,
        "material": MATERIAL_ALUMINUM, "is_pressure": False, "maximum_fill_ratio": 0.90
    },
    "Aluminium Pot 8L": {
        "capacity_l": 8.0, "inner_diameter_m": 0.260, "empty_mass_kg": 1.70,
        "material": MATERIAL_ALUMINUM, "is_pressure": False, "maximum_fill_ratio": 0.90
    },
    "Aluminium Pot 10L": {
        "capacity_l": 10.0, "inner_diameter_m": 0.280, "empty_mass_kg": 2.10,
        "material": MATERIAL_ALUMINUM, "is_pressure": False, "maximum_fill_ratio": 0.90
    },

    # ── KADHAIS / WOKS ───────────────────────────────────────────────────────
    "Kadhai / Wok 1.5L": {
        "capacity_l": 1.5, "inner_diameter_m": 0.220, "empty_mass_kg": 0.55,
        "material": MATERIAL_ALUMINUM, "is_pressure": False, "maximum_fill_ratio": 0.90
    },
    "Kadhai / Wok 2.5L": {
        "capacity_l": 2.5, "inner_diameter_m": 0.260, "empty_mass_kg": 0.75,
        "material": MATERIAL_ALUMINUM, "is_pressure": False, "maximum_fill_ratio": 0.90
    },
    "Kadhai / Wok 3.5L": {
        "capacity_l": 3.5, "inner_diameter_m": 0.280, "empty_mass_kg": 0.90,
        "material": MATERIAL_ALUMINUM, "is_pressure": False, "maximum_fill_ratio": 0.90
    },
    "Kadhai / Wok 4L": {
        "capacity_l": 4.0, "inner_diameter_m": 0.300, "empty_mass_kg": 1.00,
        "material": MATERIAL_ALUMINUM, "is_pressure": False, "maximum_fill_ratio": 0.90
    },
    "Kadhai / Wok 6L": {
        "capacity_l": 6.0, "inner_diameter_m": 0.360, "empty_mass_kg": 1.35,
        "material": MATERIAL_ALUMINUM, "is_pressure": False, "maximum_fill_ratio": 0.90
    },

    # ── CAST IRON ────────────────────────────────────────────────────────────
    "Cast Iron Tawa": {
        "capacity_l": 0.5, "inner_diameter_m": 0.260, "empty_mass_kg": 1.80,
        "material": MATERIAL_CAST_IRON, "is_pressure": False, "maximum_fill_ratio": 0.90
    },
    "Cast Iron Frying Pan 26cm": {
        "capacity_l": 1.5, "inner_diameter_m": 0.260, "empty_mass_kg": 2.10,
        "material": MATERIAL_CAST_IRON, "is_pressure": False, "maximum_fill_ratio": 0.90
    },
    "Cast Iron Kadhai 2L": {
        "capacity_l": 2.0, "inner_diameter_m": 0.240, "empty_mass_kg": 2.50,
        "material": MATERIAL_CAST_IRON, "is_pressure": False, "maximum_fill_ratio": 0.90
    },

    # ── STAINLESS STEEL 304 ──────────────────────────────────────────────────
    "Stainless Steel Pot 3L": {
        "capacity_l": 3.0, "inner_diameter_m": 0.180, "empty_mass_kg": 1.10,
        "material": MATERIAL_SS304, "is_pressure": False, "maximum_fill_ratio": 0.90
    },
    "Stainless Steel Pot 5L": {
        "capacity_l": 5.0, "inner_diameter_m": 0.220, "empty_mass_kg": 1.55,
        "material": MATERIAL_SS304, "is_pressure": False, "maximum_fill_ratio": 0.90
    },
    "Stainless Steel Kadhai 2.5L": {
        "capacity_l": 2.5, "inner_diameter_m": 0.260, "empty_mass_kg": 0.95,
        "material": MATERIAL_SS304, "is_pressure": False, "maximum_fill_ratio": 0.90
    },
}


"""
utensil_db.py
IIT Delhi · Biomass Pellet Cookstove Simulator

Provides the Utensil database and geometric modeling definitions.
"""
from enum import Enum, auto
import math

class GeometryType(Enum):
    CYLINDER = auto()
    PRESSURE_COOKER = auto()
    KADHAI = auto()
    TAWA = auto()

class Utensil:
    def __init__(self, name, empty_mass_kg, cp_kj_kgk, p_loss_kw, is_pressure,
                 material_note, manufacturer, spec_type, base_diameter_mm=None,
                 internal_height_mm=None, rated_capacity_L=None, geometry_type=None,
                 emissivity=None):
        self.name = name
        self.empty_mass_kg = empty_mass_kg
        self.cp_kj_kgk = cp_kj_kgk
        self.p_loss_kw = p_loss_kw
        self.is_pressure = is_pressure
        self.material_note = material_note
        self.manufacturer = manufacturer
        self.spec_type = spec_type
        self.base_diameter_mm = base_diameter_mm
        self.internal_height_mm = internal_height_mm
        self.rated_capacity_L = rated_capacity_L
        self.geometry_type = geometry_type
        self.emissivity = emissivity

    def get_inner_radius(self):
        if self.base_diameter_mm:
            return (self.base_diameter_mm / 1000.0) / 2.0
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# UTENSIL CATEGORIES — Ordered grouping for two-step menu selection
# ═══════════════════════════════════════════════════════════════════════════════
UTENSIL_CATEGORIES: list[tuple[str, list[str]]] = [
    ("Kadhai / Wok", [
        "Kadhai / Wok 1.5L",
        "Kadhai / Wok 2.5L",
        "Kadhai / Wok 3.5L",
        "Kadhai / Wok 4L",
        "Kadhai / Wok 6L",
    ]),
    ("Aluminium Pot", [
        "Aluminium Pot 1L",
        "Aluminium Pot 2L",
        "Aluminium Pot 3L",
        "Aluminium Pot 5L",
        "Aluminium Pot 8L",
        "Aluminium Pot 10L",
    ]),
    ("Pressure Cooker", [
        "Pressure Cooker 1.5L",
        "Pressure Cooker 2L",
        "Pressure Cooker 3L",
        "Pressure Cooker 5L",
        "Pressure Cooker 7.5L",
        "Pressure Cooker 10L",
    ]),
    ("Stainless Steel", [
        "Stainless Steel Pot 3L",
        "Stainless Steel Pot 5L",
        "Stainless Steel Kadhai 2.5L",
    ]),
    ("Cast Iron", [
        "Cast Iron Tawa",
        "Cast Iron Frying Pan 26cm",
        "Cast Iron Kadhai 2L",
    ]),
]

def get_category_names() -> list[str]:
    return [cat[0] for cat in UTENSIL_CATEGORIES]

def get_utensils_in_category(cat_name: str) -> list[str]:
    for cat, items in UTENSIL_CATEGORIES:
        if cat == cat_name:
            return items
    return []

def get_utensil_names() -> list[str]:
    return list(UTENSIL_DB.keys())

def get_utensil(name: str) -> Utensil:
    if name not in UTENSIL_DB:
        raise KeyError(f"Unknown utensil: {name!r}. Available: {get_utensil_names()}")
    return UTENSIL_DB[name]
