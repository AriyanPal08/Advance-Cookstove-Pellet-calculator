"""
utensil_db.py — Cookware Vessel Database (MicroPython Native)
IIT Delhi · Biomass Pellet Cookstove Simulator
"""

class Utensil:
    """Standard Python class for vessel records."""
    def __init__(self, name, mass_kg, cp_kj_kgk, p_loss_kw, is_pressure=False, material_note=""):
        self.name = name
        self.mass_kg = mass_kg
        self.cp_kj_kgk = cp_kj_kgk
        self.p_loss_kw = p_loss_kw
        self.is_pressure = is_pressure
        self.material_note = material_note

        if not self.name.strip():
            raise ValueError("Utensil.name must not be empty.")
        if self.mass_kg <= 0:
            raise ValueError(f"[{self.name}] mass_kg must be > 0, got {self.mass_kg}")
        if self.cp_kj_kgk <= 0:
            raise ValueError(f"[{self.name}] cp_kj_kgk must be > 0, got {self.cp_kj_kgk}")
        if self.p_loss_kw < 0:
            raise ValueError(f"[{self.name}] p_loss_kw must be >= 0, got {self.p_loss_kw}")

UTENSIL_DB = {
    "AL PAN/PATILA": Utensil(
        name="AL PAN/PATILA",
        mass_kg=1.20,
        cp_kj_kgk=0.897,
        p_loss_kw=0.20,
        is_pressure=False,
        material_note="Aluminium, Cp=0.897 kJ/kg·K [NIST/Incropera Table A.1]",
    ),
    "K ": Utensil(
        name="Kadhai / Wok",
        mass_kg=0.90,
        cp_kj_kgk=0.897,
        p_loss_kw=0.25,
        is_pressure=False,
        material_note="Aluminium, Cp=0.897 kJ/kg·K [NIST/Incropera Table A.1]",
    ),
    "T": Utensil(
        name="TAWA",
        mass_kg=0.70,
        cp_kj_kgk=0.460,
        p_loss_kw=0.30,
        is_pressure=False,
        material_note="Cast Iron, Cp=0.460 kJ/kg·K [Incropera Table A.1]",
    ),
    "C": Utensil(
        name="COOKER (5L)",
        mass_kg=1.80,
        cp_kj_kgk=0.897,
        p_loss_kw=0.08,
        is_pressure=True,
        material_note="Aluminium body, Cp=0.897 kJ/kg·K [NIST/Incropera Table A.1]",
    ),
}

def get_utensil_names():
    return list(UTENSIL_DB.keys())

def get_utensil(name):
    if name not in UTENSIL_DB:
        raise KeyError(f"Unknown utensil: {name!r}")
    return UTENSIL_DB[name]