

EMISSIVITY_ALUMINUM_OXIDIZED = 0.35
EMISSIVITY_STAINLESS_STEEL = 0.25
EMISSIVITY_CAST_IRON = 0.65
"""
manufacturer_data.py
IIT Delhi ┬╖ Biomass Pellet Cookstove Simulator

Verified manufacturer specifications for utensils (Hawkins, Prestige, etc.).
DO NOT fabricate any data here. If an exact dimension is unavailable in official catalogs,
leave it as None, and the simulator will mathematically derive it where physically valid.
"""



# Material standard densities and properties referenced from physics_constants
MATERIAL_ALUMINUM = "Aluminum"
MATERIAL_SS304 = "Stainless Steel 304"
MATERIAL_CAST_IRON = "Cast Iron"

# =============================================================================
# HAWKINS & PRESTIGE OFFICIAL CATALOG DATA (Sampled)
# =============================================================================
MANUFACTURER_SPECS = {
    # ΓöÇΓöÇ HAWKINS CLASSIC PRESSURE COOKERS ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
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

    # ΓöÇΓöÇ ALUMINIUM POTS (Neona / Generic) ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
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

    # ΓöÇΓöÇ KADHAIS / WOKS ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
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

    # ΓöÇΓöÇ CAST IRON ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
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

    # ΓöÇΓöÇ STAINLESS STEEL 304 ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
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
IIT Delhi ┬╖ Biomass Pellet Cookstove Simulator

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
    def __init__(self, name, geometry_type, capacity_l, empty_mass_kg, material, is_pressure,
                 maximum_fill_ratio, outer_diameter_m, inner_diameter_m, wall_thickness_m,
                 height_m, cp_kj_kgk, emissivity, pressure_rating_kpa):
        self.name = name
        self.geometry_type = geometry_type
        self.capacity_l = capacity_l
        self.empty_mass_kg = empty_mass_kg
        self.material = material
        self.is_pressure = is_pressure
        self.maximum_fill_ratio = maximum_fill_ratio
        self.outer_diameter_m = outer_diameter_m
        self.inner_diameter_m = inner_diameter_m
        self.wall_thickness_m = wall_thickness_m
        self.height_m = height_m
        self.cp_kj_kgk = cp_kj_kgk
        self.emissivity = emissivity
        self.pressure_rating_kpa = pressure_rating_kpa

    def get_inner_radius(self) :
        """Return the inner radius in meters. If missing, derive a reasonable default based on capacity and assumed h/d."""
        if self.inner_diameter_m is not None:
            return self.inner_diameter_m / 2.0
            
        # Fallback mathematically derived radius if manufacturer spec is missing
        V_m3 = self.capacity_l / 1000.0
        # Assume a standard h/d ratio if we don't have the explicit radius
        h_over_d = 0.65 if self.geometry_type in (GeometryType.CYLINDER, GeometryType.PRESSURE_COOKER) else 0.45
        d_m = (4.0 * V_m3 / (math.pi * h_over_d)) ** (1.0 / 3.0)
        return d_m / 2.0

    def get_total_height(self) :
        """Return the total inner height of the vessel in meters."""
        if self.height_m is not None:
            return self.height_m
            
        r_inner = self.get_inner_radius()
        V_m3 = self.capacity_l / 1000.0
        
        if self.geometry_type in (GeometryType.CYLINDER, GeometryType.PRESSURE_COOKER):
            # V = pi * r^2 * h
            return V_m3 / (math.pi * (r_inner ** 2))
        elif self.geometry_type == GeometryType.KADHAI:
            # Spherical cap approximation V = (pi * h / 6) * (3r^2 + h^2)
            # Rough numerical inversion for kadhai shape (shallow bowl)
            h = r_inner * 0.90 # Approximation for typical woks
            return h
        else: # TAWA
            return 0.02 # Minimal height

def _determine_geometry(name) :
    if "Pressure Cooker" in name:
        return GeometryType.PRESSURE_COOKER
    if "Kadhai" in name or "Wok" in name:
        return GeometryType.KADHAI
    if "Tawa" in name or "Pan" in name:
        return GeometryType.TAWA
    return GeometryType.CYLINDER

def _get_cp(material) :
    # Source: Incropera et al. Table A.1 / NIST WebBook
    if material == MATERIAL_ALUMINUM:
        return 0.897
    if material == MATERIAL_CAST_IRON:
        return 0.460
    if material == MATERIAL_SS304:
        return 0.500
    return 0.897

def _get_emissivity(material) :
    if material == MATERIAL_CAST_IRON:
        return EMISSIVITY_CAST_IRON
    if material == MATERIAL_SS304:
        return EMISSIVITY_STAINLESS_STEEL
    return EMISSIVITY_ALUMINUM_OXIDIZED

# =============================================================================
# BUILD MASTER DATABASE
# =============================================================================
UTENSIL_DB = {}

for name, spec in MANUFACTURER_SPECS.items():
    geom = _determine_geometry(name)
    UTENSIL_DB[name] = Utensil(
        name=name,
        geometry_type=geom,
        capacity_l=spec["capacity_l"],
        empty_mass_kg=spec["empty_mass_kg"],
        material=spec["material"],
        is_pressure=spec["is_pressure"],
        maximum_fill_ratio=spec["maximum_fill_ratio"],
        outer_diameter_m=spec.get("outer_diameter_m"),
        inner_diameter_m=spec.get("inner_diameter_m"),
        wall_thickness_m=spec.get("wall_thickness_m"),
        height_m=spec.get("height_m"),
        cp_kj_kgk=_get_cp(spec["material"]),
        emissivity=_get_emissivity(spec["material"]),
        pressure_rating_kpa=spec.get("pressure_rating_kpa")
    )


# ΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉ
# UTENSIL CATEGORIES ΓÇö Ordered grouping for two-step menu selection
# ΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉΓòÉ
UTENSIL_CATEGORIES = [
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

def get_category_names() :
    return [cat[0] for cat in UTENSIL_CATEGORIES]

def get_utensils_in_category(cat_name) :
    for cat, items in UTENSIL_CATEGORIES:
        if cat == cat_name:
            return items
    return []

def get_utensil_names() :
    return list(UTENSIL_DB.keys())

def get_utensil(name) :
    if name not in UTENSIL_DB:
        raise KeyError(f"Unknown utensil: {name!r}. Available: {get_utensil_names()}")
    return UTENSIL_DB[name]
