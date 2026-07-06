"""
pellet_db.py — Biomass Pellet GCV Database (MicroPython Native)
"""

KCAL_TO_KJ = 4.184

class PelletType:
    def __init__(self, name, gcv_min_kcal, gcv_max_kcal, category):
        self.name = name
        self.gcv_min_kcal = gcv_min_kcal
        self.gcv_max_kcal = gcv_max_kcal
        self.category = category

        if not self.name.strip():
            raise ValueError("PelletType.name must not be empty.")
        if self.gcv_min_kcal <= 0:
            raise ValueError(f"[{self.name}] gcv_min_kcal must be > 0, got {self.gcv_min_kcal}")
        if self.gcv_max_kcal < self.gcv_min_kcal:
            raise ValueError(f"[{self.name}] gcv_max_kcal must be >= gcv_min_kcal")
        if self.category not in {"Wood", "Agri-Waste", "Blended"}:
            raise ValueError(f"[{self.name}] category must be 'Wood', 'Agri-Waste', or 'Blended'")
            
        self.gcv_min_kj = self.gcv_min_kcal * KCAL_TO_KJ
        self.gcv_max_kj = self.gcv_max_kcal * KCAL_TO_KJ

    @property
    def conservative_gcv_kj(self):
        return self.gcv_min_kj

    @property
    def gcv_range_kcal(self):
        return (self.gcv_min_kcal, self.gcv_max_kcal)

_RAW_DATA = [
    ("Softwood Pellets (Pine, Spruce, Fir, Cedar)",  4300, 4580, "Wood"),
    ("Hardwood Pellets (Oak, Beech, Maple, Elm)",    4200, 4500, "Wood"),
    ("Bamboo Pellets",                               4500, 4800, "Wood"),
    ("Torrefied (Black) Pellets",                    5000, 5500, "Wood"),
    ("Eucalyptus Bark Pellets",                      4000, 4200, "Wood"),
    ("Groundnut (Peanut) Shell Pellets",             3800, 4500, "Agri-Waste"),
    ("Coffee Husk & Waste Pellets",                  4100, 4300, "Agri-Waste"),
    ("Switchgrass & Miscanthus Pellets",             3800, 4100, "Agri-Waste"),
    ("Corncob & Maize Stalk Pellets",                3500, 4200, "Agri-Waste"),
    ("Cotton Stalk Pellets",                         3500, 3900, "Agri-Waste"),
    ("Mustard Husk Pellets",                         3600, 3900, "Agri-Waste"),
    ("Wheat Straw Pellets",                          3200, 3600, "Agri-Waste"),
    ("Rice Husk Pellets",                            3200, 3500, "Agri-Waste"),
    ("Alfalfa Pellets",                              3200, 3400, "Agri-Waste"),
    ("Sugarcane Bagasse Pellets",                    3800, 4200, "Agri-Waste"),
    ("Paper & Cardboard Pellets (RDF)",              3800, 4300, "Blended"),
]

PELLET_DB = {
    name: PelletType(name, lo, hi, cat) for name, lo, hi, cat in _RAW_DATA
}

def get_pellet_names():
    return sorted(PELLET_DB.keys())

def get_pellet(pellet_name):
    if pellet_name not in PELLET_DB:
        raise KeyError(f"Unknown pellet type: {pellet_name!r}")
    return PELLET_DB[pellet_name]

def get_conservative_gcv_kj(pellet_name):
    return get_pellet(pellet_name).conservative_gcv_kj