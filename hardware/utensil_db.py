# =============================================================================
# hardware/utensil_db.py — MicroPython Port (ESP32)
# Cookware Vessel Database — v5 Expanded (Hawkins/Prestige Specs)
# Converted from @dataclass(frozen=True) to plain __init__ class.
# All masses, Cp values, and entries preserved byte-for-byte.
#
# SOURCES:
# [1] MacCarty et al. (2010). Energy Sustain. Dev., 14(3), 214-222.
# [2] NIST WebBook — Aluminium thermophysical properties.
# [3] Incropera et al. (2007). Fundamentals of Heat and Mass Transfer, 7th ed.
# =============================================================================

# Material-specific heat capacities (kJ/kg-K)
CP_ALUM = 0.897          # Aluminium [NIST WebBook, Incropera Table A.1]
CP_CAST_IRON = 0.460     # Cast Iron [Incropera Table A.1]
CP_SS304 = 0.500         # Stainless Steel 304 [Incropera Table A.1]


class Utensil:
    def __init__(self, name, mass_kg, cp_kj_kgk, p_loss_kw,
                 is_pressure=False, material_note=""):
        self.name = name
        self.mass_kg = mass_kg
        self.cp_kj_kgk = cp_kj_kgk
        self.p_loss_kw = p_loss_kw
        self.is_pressure = is_pressure
        self.material_note = material_note


# ═══════════════════════════════════════════════════════════════════════════════
# MASTER UTENSIL DATABASE — 23 entries
# All masses verified against Hawkins/Prestige 2023-2024 datasheets.
# ═══════════════════════════════════════════════════════════════════════════════

UTENSIL_DB = {

    # ── ALUMINIUM POTS (Open/Covered) — Hawkins Neona / Classic ──────────────
    "AL Pot 1L": Utensil(
        name="AL Pot 1L",
        mass_kg=0.45,
        cp_kj_kgk=CP_ALUM,
        p_loss_kw=0.07,
        is_pressure=False,
    ),
    "AL Pot 2L": Utensil(
        name="AL Pot 2L",
        mass_kg=0.65,
        cp_kj_kgk=CP_ALUM,
        p_loss_kw=0.10,
        is_pressure=False,
    ),
    "AL Pot 3L": Utensil(
        name="AL Pot 3L",
        mass_kg=0.90,
        cp_kj_kgk=CP_ALUM,
        p_loss_kw=0.15,
        is_pressure=False,
    ),
    "AL Pot 5L": Utensil(
        name="AL Pot 5L",
        mass_kg=1.20,
        cp_kj_kgk=CP_ALUM,
        p_loss_kw=0.20,
        is_pressure=False,
    ),
    "AL Pot 8L": Utensil(
        name="AL Pot 8L",
        mass_kg=1.70,
        cp_kj_kgk=CP_ALUM,
        p_loss_kw=0.28,
        is_pressure=False,
    ),
    "AL Pot 10L": Utensil(
        name="AL Pot 10L",
        mass_kg=2.10,
        cp_kj_kgk=CP_ALUM,
        p_loss_kw=0.32,
        is_pressure=False,
    ),

    # ── ALUMINIUM PRESSURE COOKERS — Hawkins Classic / Prestige ──────────────
    "Cooker 1.5L": Utensil(
        name="Cooker 1.5L",
        mass_kg=1.00,
        cp_kj_kgk=CP_ALUM,
        p_loss_kw=0.03,
        is_pressure=True,
    ),
    "Cooker 2L": Utensil(
        name="Cooker 2L",
        mass_kg=1.20,
        cp_kj_kgk=CP_ALUM,
        p_loss_kw=0.04,
        is_pressure=True,
    ),
    "Cooker 3L": Utensil(
        name="Cooker 3L",
        mass_kg=1.45,
        cp_kj_kgk=CP_ALUM,
        p_loss_kw=0.05,
        is_pressure=True,
    ),
    "Cooker 5L": Utensil(
        name="Cooker 5L",
        mass_kg=1.80,
        cp_kj_kgk=CP_ALUM,
        p_loss_kw=0.08,
        is_pressure=True,
    ),
    "Cooker 7.5L": Utensil(
        name="Cooker 7.5L",
        mass_kg=2.35,
        cp_kj_kgk=CP_ALUM,
        p_loss_kw=0.12,
        is_pressure=True,
    ),
    "Cooker 10L": Utensil(
        name="Cooker 10L",
        mass_kg=3.00,
        cp_kj_kgk=CP_ALUM,
        p_loss_kw=0.15,
        is_pressure=True,
    ),

    # ── ALUMINIUM KADHAIS (Woks) — Hawkins range ────────────────────────────
    "Kadhai 1.5L": Utensil(
        name="Kadhai 1.5L",
        mass_kg=0.55,
        cp_kj_kgk=CP_ALUM,
        p_loss_kw=0.14,
        is_pressure=False,
    ),
    "Kadhai 2.5L": Utensil(
        name="Kadhai 2.5L",
        mass_kg=0.75,
        cp_kj_kgk=CP_ALUM,
        p_loss_kw=0.18,
        is_pressure=False,
    ),
    "Kadhai 3.5L": Utensil(
        name="Kadhai 3.5L",
        mass_kg=0.90,
        cp_kj_kgk=CP_ALUM,
        p_loss_kw=0.22,
        is_pressure=False,
    ),
    "Kadhai 4L": Utensil(
        name="Kadhai 4L",
        mass_kg=1.00,
        cp_kj_kgk=CP_ALUM,
        p_loss_kw=0.24,
        is_pressure=False,
    ),
    "Kadhai 6L": Utensil(
        name="Kadhai 6L",
        mass_kg=1.35,
        cp_kj_kgk=CP_ALUM,
        p_loss_kw=0.32,
        is_pressure=False,
    ),

    # ── CAST IRON (Tawa / Frying Pan) ────────────────────────────────────────
    "Iron Tawa": Utensil(
        name="Iron Tawa",
        mass_kg=1.80,
        cp_kj_kgk=CP_CAST_IRON,
        p_loss_kw=0.28,
        is_pressure=False,
    ),
    "Iron BIG PAN": Utensil(
        name="Iron BIG PAN",
        mass_kg=2.10,
        cp_kj_kgk=CP_CAST_IRON,
        p_loss_kw=0.35,
        is_pressure=False,
    ),
    "Iron Kadhai 2L": Utensil(
        name="Iron Kadhai 2L",
        mass_kg=2.50,
        cp_kj_kgk=CP_CAST_IRON,
        p_loss_kw=0.22,
        is_pressure=False,
    ),

    # ── STAINLESS STEEL 304 (Premium) — Prestige range ──────────────────────
    " Steel Pot 3L": Utensil(
        name="Stainless Steel Pot 3L",
        mass_kg=1.10,
        cp_kj_kgk=CP_SS304,
        p_loss_kw=0.16,
        is_pressure=False,
    ),
    "Steel Pot 5L": Utensil(
        name="Stainless Steel Pot 5L",
        mass_kg=1.55,
        cp_kj_kgk=CP_SS304,
        p_loss_kw=0.22,
        is_pressure=False,
    ),
    "Steel Kadhai 2.5L": Utensil(
        name="Stainless Steel Kadhai 2.5L",
        mass_kg=0.95,
        cp_kj_kgk=CP_SS304,
        p_loss_kw=0.18,
        is_pressure=False,
    ),
}

# ═══════════════════════════════════════════════════════════════════════════════
# UTENSIL CATEGORIES — Ordered grouping for two-step menu selection
# ═══════════════════════════════════════════════════════════════════════════════

UTENSIL_CATEGORIES = [
    ("Kadhai / Wok", [
        "Kadhai 1.5L",
        "Kadhai 2.5L",
        "Kadhai 3.5L",
        "Kadhai 4L",
        "Kadhai 6L",
    ]),
    ("AL  Pot", [
        "AL Pot 1L",
        "AL Pot 2L",
        "AL Pot 3L",
        "AL Pot 5L",
        "AL Pot 8L",
        "AL Pot 10L",
    ]),
    ("Cooker", [
        "Cooker 1.5L",
        "Cooker 2L",
        "Cooker 3L",
        "Cooker 5L",
        "Cooker 7.5L",
        "Cooker 10L",
    ]),
    ("Steel", [
        "Steel Pot 3L",
        "Steel Pot 5L",
        "Steel Kadhai 2.5L",
    ]),
    ("Cast Iron", [
        "Iron Tawa",
        "Iron BIG PAN",
        "Iron Kadhai 2L",
    ]),
]


def get_category_names():
    return [cat[0] for cat in UTENSIL_CATEGORIES]


def get_utensils_in_category(cat_name):
    for cat, items in UTENSIL_CATEGORIES:
        if cat == cat_name:
            return items
    return []


def get_utensil_names():
    return list(UTENSIL_DB.keys())


def get_utensil(name):
    if name not in UTENSIL_DB:
        raise KeyError("Unknown utensil: " + name)
    return UTENSIL_DB[name]
