"""Desktop terminal entry point using the hardware calculator as its source of truth.

Run from this folder with:  python terminal.py
"""

from hardware_adapter import (
    WIND_TIERS, simulate, get_dish_names, get_dish,
    get_pellet_names, get_utensil_names, get_utensil,
)


def choose(title, options):
    """Select an existing hardware database entry without changing its value."""
    print("\n" + title)
    for index, option in enumerate(options, 1):
        print("  {:>2}. {}".format(index, option))
    while True:
        try:
            choice = int(input("Choose a number: ").strip())
            if 1 <= choice <= len(options):
                return options[choice - 1]
        except ValueError:
            pass
        print("Please enter one of the listed numbers.")


def number(prompt, default, minimum=None, maximum=None, integer=False):
    """Read a bounded value; bounds come from the hardware food database."""
    suffix = " [{}]".format(default)
    while True:
        raw = input(prompt + suffix + ": ").strip()
        try:
            value = default if not raw else (int(raw) if integer else float(raw))
            if minimum is not None and value < minimum:
                raise ValueError
            if maximum is not None and value > maximum:
                raise ValueError
            return value
        except ValueError:
            print("Enter a value from {} to {}.".format(minimum, maximum))


def collect_payload():
    dish_name = choose("1/7 Select dish", get_dish_names())
    dish = get_dish(dish_name)
    qty_label = dish.qty_prompt or ("Water volume (L)" if dish.variable_water else "Servings")
    qty = number(
        "2/7 " + qty_label,
        dish.qty_default,
        dish.qty_min,
        dish.qty_max,
        integer=not dish.qty_is_float and not dish.variable_water,
    )

    wind_label = choose("3/7 Wind environment", list(WIND_TIERS.keys()))
    utensil_name = choose("4/7 Utensil", get_utensil_names())
    utensil = get_utensil(utensil_name)
    mass = number("5/7 Vessel mass (kg)", utensil.mass_kg, 0.1, 10.0)
    pellet_name = choose("6/7 Pellet type", get_pellet_names())
    ambient = number("7/7 Ambient temperature (C)", 25.0, 15.0, 45.0)

    payload = {
        "dish_name": dish_name,
        "qty": qty,
        "t_ambient_c": ambient,
        "wind_label": wind_label,
        "pellet_name": pellet_name,
        "utensil_name": utensil_name,
        "m_pot": mass,
        "lid_state": "ON",
    }
    if not utensil.is_pressure:
        payload["lid_state"] = choose("Lid state", ["ON", "OFF"])
    return payload


def print_result(inp):
    print("\n" + "=" * 58)
    print("HARDWARE-MATCHED PELLET CALCULATION")
    print("=" * 58)
    print("Dish:              {}".format(inp["dish_name"]))
    print("Utensil:           {}".format(inp["utensil_name"]))
    print("Cooking time:      {:.1f} min".format(inp["t_total_min_user"]))
    print("Boil estimate:     {:.1f} min".format(inp["t_boil_est_s"] / 60.0))
    print("Hopper load:       {:.1f} g".format(inp["pellets_required_g"]))
    print("Feed-only amount:  {:.1f} g".format(inp["pellets_time_based_g"]))
    print("Safety margin:     {}".format(inp["margin_reason"]))
    print("Final vessel temp: {:.1f} C".format(inp["T_pot_c"]))
    if inp["flag_dry_boil"]:
        print("WARNING: Dry-boil detected.")
    if inp["flag_overheat"]:
        print("WARNING: Vessel overheat detected.")


def main():
    print("Cookstove Pellet Calculator — hardware-matched desktop terminal")
    while True:
        try:
            inp = simulate(collect_payload())
            print_result(inp)
        except (KeyError, TypeError, ValueError) as error:
            print("Calculation could not run: {}".format(error))

        if input("\nCalculate another dish? [y/N]: ").strip().lower() != "y":
            return


if __name__ == "__main__":
    main()
