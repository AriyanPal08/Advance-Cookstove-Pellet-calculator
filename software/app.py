from flask import Flask, render_template, request, jsonify

from hardware_adapter import (
    FOOD_DB, get_dish_names, PELLET_DB, get_pellet_names,
    get_utensil_names, get_utensil, WIND_TIERS, LID_FACTOR_ON,
    LID_FACTOR_OFF, FAN_HIGH, CP_WATER, PRESSURE_POST_BOIL_FACTOR,
    compute_vessel_geometry, _emissivity_for_utensil, estimate_cook_time,
    compute_safety_buffer_s, zero_state, run_1hz_loop, post_process,
)

import os
import urllib.request
import json as json_lib
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)

# Fix for Render/Cloud load balancers (trust X-Forwarded-* headers)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Set up Security Headers (Talisman)
csp = {
    'default-src': ["'self'"],
    'script-src': ["'self'", "'unsafe-inline'", "https://translate.google.com", "https://translate.googleapis.com"],
    'style-src': ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com", "https://translate.googleapis.com"],
    'font-src': ["'self'", "https://fonts.gstatic.com"],
    'img-src': ["'self'", "data:", "blob:", "https://www.google.com", "https://www.gstatic.com"],
    'connect-src': ["'self'", "https://api.open-meteo.com", "https://get.geojs.io", "https://ipapi.co", "https://api.bigdatacloud.net", "https://translate.googleapis.com"],
}
# Automatically force HTTPS if FLASK_ENV is set to production
is_prod = os.environ.get("FLASK_ENV") == "production"
Talisman(app, content_security_policy=csp, force_https=is_prod)

# Set up Rate Limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["1000 per day", "200 per hour"],
    storage_uri="memory://"
)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/init", methods=["GET"])
def init_data():
    """Return lists for dropdowns."""
    dishes = []
    for name in get_dish_names():
        d = FOOD_DB[name]
        dishes.append({
            "name": name,
            "category": d.category,
            "variable_water": d.variable_water,
            "qty_prompt": d.qty_prompt if getattr(d, 'qty_prompt', '') else ("Volume of Water (Litres)" if d.variable_water else "Number of people"),
            "qty_unit": getattr(d, 'qty_unit', ''),
            "qty_is_float": getattr(d, 'qty_is_float', False),
            "qty_min": getattr(d, 'qty_min', 0.0),
            "qty_max": getattr(d, 'qty_max', 200.0 if d.variable_water else 50.0),
            "qty_default": getattr(d, 'qty_default', 5.0 if d.variable_water else 2)
        })
    
    pellets = []
    for name in get_pellet_names():
        pellet = PELLET_DB[name]
        pellets.append({
            "name": name,
            "category": pellet.category,
            "gcv_range_kcal": pellet.gcv_range_kcal,
        })
    utensils = []
    for name in get_utensil_names():
        u = get_utensil(name)
        utensils.append({
            "name": name,
            "mass_kg": u.mass_kg,
            "is_pressure": u.is_pressure
        })

    wind_tiers = list(WIND_TIERS.keys())

    return jsonify({
        "dishes": dishes,
        "pellets": pellets,
        "utensils": utensils,
        "wind_tiers": wind_tiers
    })

def _build_inputs(data):
    """Replicate the first part of collect_inputs logic from main_logic.py."""
    inp = {}
    # The utensil is selected later in the web form. Start as an open vessel,
    # then recompute the kinetic duration once its real type is known.
    inp["is_pc"] = False
    
    # 1. Dish
    inp["dish_name"] = data["dish_name"]
    inp["dish"] = FOOD_DB[inp["dish_name"]]
    dish = inp["dish"]

    # 2. Portions / Water
    if dish.variable_water:
        inp["water_liters"] = float(data["qty"])
        inp["portions"] = 1
        inp["m_food"] = dish.food_mass_per_serving_kg
        inp["cp_food"] = dish.cp_food_kj_kgk
        inp["m_water_initial"] = inp["water_liters"]
        inp["t_kinetic_base_s"] = 0.0
    else:
        n = float(data["qty"]) if getattr(dish, 'qty_is_float', False) else int(data["qty"])
        inp["portions"] = n
        inp["m_food"] = dish.food_mass_per_serving_kg * n
        inp["cp_food"] = dish.cp_food_kj_kgk
        inp["m_water_initial"] = dish.added_water_per_serving_kg * n
        
        kinetic_time_s = 0.0
        for stage in dish.stages:
            if stage.stage_type == "kinetic":
                # This reduction is a pressure-cooker-only hardware rule.
                kinetic_time_s += stage.duration_s * (
                    PRESSURE_POST_BOIL_FACTOR if inp["is_pc"] else 1.0
                )
            elif stage.stage_type == "frying":
                kinetic_time_s += stage.duration_s
        inp["t_kinetic_base_s"] = kinetic_time_s

    # 3. Ambient & Wind
    inp["t_ambient_c"] = float(data["t_ambient_c"])
    inp["wind_label"] = data["wind_label"]
    inp["k_conv_current"] = WIND_TIERS[inp["wind_label"]]

    # 4. Pellet
    inp["pellet_name"] = data["pellet_name"]
    inp["pellet"] = PELLET_DB[inp["pellet_name"]]
    inp["gcv_kj_kg"] = inp["pellet"].conservative_gcv_kj

    # 5. Utensil
    inp["utensil_name"] = data["utensil_name"]
    utensil = get_utensil(inp["utensil_name"])
    inp["cp_pot"] = utensil.cp_kj_kgk
    inp["is_pc"] = utensil.is_pressure
    inp["utensil"] = utensil # Important for post_process to read utensil.is_pressure

    if not dish.variable_water:
        kinetic_time_s = 0.0
        for stage in dish.stages:
            if stage.stage_type == "kinetic":
                kinetic_time_s += stage.duration_s * (
                    PRESSURE_POST_BOIL_FACTOR if inp["is_pc"] else 1.0
                )
            elif stage.stage_type == "frying":
                kinetic_time_s += stage.duration_s
        inp["t_kinetic_base_s"] = kinetic_time_s

    inp["m_pot"] = float(data.get("m_pot", utensil.mass_kg))

    # Lid
    if inp["is_pc"]:
        inp["lid_label"] = "ON (Pressure Cooker — sealed)"
        inp["lid_factor"] = 0.0
    else:
        if data.get("lid_state") == "ON":
            inp["lid_label"] = "Lid ON"
            inp["lid_factor"] = LID_FACTOR_ON
        else:
            inp["lid_label"] = "Lid OFF"
            inp["lid_factor"] = LID_FACTOR_OFF

    # Geometry
    m_w = inp["m_water_initial"]
    inp["emissivity"] = _emissivity_for_utensil(utensil)
    # Match hardware/main.py run_simulation() exactly.
    geom = compute_vessel_geometry(m_w, inp["utensil_name"], inp["lid_factor"])
    inp.update(geom)

    # Preview logic
    eta_geom = inp["eta_geom"]
    P_in_kw = (FAN_HIGH / 3600.0) * inp["gcv_kj_kg"] * eta_geom
    MCp_total = (inp["m_food"] * inp["cp_food"] + m_w * CP_WATER + inp["m_pot"] * inp["cp_pot"])
    T_amb = inp["t_ambient_c"]
    k_conv = inp["k_conv_current"]

    preview = estimate_cook_time(
        m_food=inp["m_food"],
        cp_food=inp["cp_food"],
        m_water=m_w,
        m_pot=inp["m_pot"],
        cp_pot=inp["cp_pot"],
        t_kinetic_s=inp["t_kinetic_base_s"],
        P_in_kw=P_in_kw,
        A_m2=inp["A_m2"],
        k_conv=k_conv,
        emissivity=inp["emissivity"],
        T_amb=T_amb,
        lid_fac=inp["lid_factor"],
    )

    t_heat_s = preview["t_heat_s"]
    if preview["heat_cannot_rise"] > 0.5 or t_heat_s <= 0.0:
        t_heat_s = 0.0

    Q_out_avg_kw = (preview["Q_out_accum_kj"] / preview["t_preview_s"] if preview["t_preview_s"] > 0.0 else 0.0)
    t_safety_buffer_s = compute_safety_buffer_s(t_heat_s, k_conv, m_w)
    t_core_s = t_heat_s + inp["t_kinetic_base_s"]
    t_suggested_total_s = t_core_s + t_safety_buffer_s
    t_suggested_total_min = t_suggested_total_s / 60.0

    inp["P_in_kw"] = P_in_kw
    inp["MCp_total_init"] = MCp_total
    inp["Q_out_avg_kw"] = Q_out_avg_kw
    inp["t_heat_est_s"] = t_heat_s
    inp["t_boil_est_s"] = preview["t_boil_s"]
    inp["t_safety_buffer_s"] = t_safety_buffer_s
    inp["t_preview_s"] = preview["t_preview_s"]
    inp["t_suggested_total_min"] = t_suggested_total_min

    return inp

@app.route("/api/preview", methods=["POST"])
@limiter.limit("20 per minute")  # Stricter limit for calculation endpoints
def preview():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Enter the simulation inputs and try again."}), 400
    try:
        inp = _build_inputs(data)
        return jsonify({
            "success": True,
            "t_heat_est_min": inp["t_heat_est_s"] / 60.0,
            "t_boil_est_min": inp["t_boil_est_s"] / 60.0,
            "t_kinetic_base_min": inp["t_kinetic_base_s"] / 60.0,
            "t_safety_buffer_s": inp["t_safety_buffer_s"],
            "t_suggested_total_min": inp["t_suggested_total_min"]
        })
    except (KeyError, TypeError, ValueError) as e:
        return jsonify({"success": False, "error": f"Check the selected inputs: {e}"}), 400

@app.route("/api/simulate", methods=["POST"])
@limiter.limit("10 per minute")  # Heavy calculation, strictly rate limit
def simulate():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Enter the simulation inputs and try again."}), 400
    try:
        inp = _build_inputs(data)
        
        # Hardware uses the calculated duration (heat-up + kinetic + safety
        # buffer) rather than a user override. Keep the web result identical.
        t_total_min = inp["t_suggested_total_min"]
        inp["t_total_s"] = t_total_min * 60.0
        inp["t_total_min_user"] = t_total_min

        # Run loop
        inp = zero_state(inp)
        inp = run_1hz_loop(inp)
        inp = post_process(inp)

        # Prepare receipt output
        receipt = {
            "dish_name": inp["dish_name"],
            "portions": inp["portions"],
            "water_liters": data.get("qty") if inp["dish"].variable_water else None,
            "t_ambient_c": inp["t_ambient_c"],
            "wind_label": inp["wind_label"],
            "k_conv_current": inp["k_conv_current"],
            "utensil_name": inp["utensil_name"],
            "m_pot": inp["m_pot"],
            "cp_pot": inp["cp_pot"],
            "emissivity": inp["emissivity"],
            "lid_label": inp["lid_label"],
            "pellet_name": inp["pellet_name"],
            "gcv_kj_kg": inp["pellet"].conservative_gcv_kj,
            "t_heat_est_s": inp["t_heat_est_s"],
            "t_boil_est_s": inp["t_boil_est_s"],
            "t_kinetic_base_s": inp["t_kinetic_base_s"],
            "t_safety_buffer_s": inp["t_safety_buffer_s"],
            "t_total_min_user": inp["t_total_min_user"],
            "t_boil_reached_s": inp["t_boil_reached_s"],
            "Q_out_avg_kw": inp["Q_out_avg_kw"],
            "m_food": inp["m_food"],
            "m_water_initial": inp["m_water_initial"],
            "A_m2": inp["A_m2"],
            "eta_geom": inp["eta_geom"],
            "P_in_kw": inp["P_in_kw"],
            "t_elapsed_s": inp["t_elapsed_s"],
            "Q_in_kj": inp.get("Q_in_kj", inp["P_in_kw"] * inp["t_elapsed_s"]),
            "Q_out_kj": inp.get("Q_out_kj", 0),
            "Q_sensible_kj": inp.get("Q_sensible_kj", 0),
            "Q_evap_kj": inp.get("Q_evap_kj", 0),
            "Q_demand_kj": inp.get("Q_demand_kj", 0),
            "m_water_current": inp["m_water_current"],
            "flag_dry_boil": inp["flag_dry_boil"],
            "flag_overheat": inp["flag_overheat"],
            "T_pot_c": inp["T_pot_c"],
            "t_phase1_s": inp["t_phase1_s"],
            "t_phase2_s": inp["t_phase2_s"],
            "t_phase3_s": inp["t_phase3_s"],
            "pellets_required_g": inp["pellets_required_g"],
            "pellets_time_based_g": inp.get("pellets_time_based_g", 0),
            "tick_log": inp["tick_log"]
        }
        
        # Avoid non-serializable object issues by only returning basic types
        return jsonify({"success": True, "receipt": receipt})
    except (KeyError, TypeError, ValueError) as e:
        return jsonify({"success": False, "error": f"Check the selected inputs: {e}"}), 400

@app.route("/api/weather", methods=["GET"])
@limiter.limit("30 per minute")
def api_weather():
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    
    try:
        if not lat or not lon:
            client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            if client_ip and ',' in client_ip:
                client_ip = client_ip.split(',')[0].strip()
            
            ip_url = "https://get.geojs.io/v1/ip/geo.json"
            if client_ip and not client_ip.startswith("127.") and not client_ip.startswith("192.168.") and not client_ip.startswith("10."):
                ip_url = f"https://get.geojs.io/v1/ip/geo/{client_ip}.json"
                
            req = urllib.request.Request(ip_url, headers={'User-Agent': 'TadkaChulha/1.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                geo_data = json_lib.loads(response.read().decode('utf-8'))
                lat = geo_data.get("latitude")
                lon = geo_data.get("longitude")
                city = geo_data.get("city", "Local Area")
                region = geo_data.get("region", "")
                loc_name = f"{city}{', ' + region if region else ''}"
        else:
            loc_name = f"Lat {float(lat):.2f}, Lon {float(lon):.2f}"
            try:
                geo_url = f"https://api.bigdatacloud.net/data/reverse-geocode-client?latitude={lat}&longitude={lon}&localityLanguage=en"
                req_geo = urllib.request.Request(geo_url, headers={'User-Agent': 'TadkaChulha/1.0'})
                with urllib.request.urlopen(req_geo, timeout=4) as response:
                    geo_data = json_lib.loads(response.read().decode('utf-8'))
                    place = geo_data.get("locality") or geo_data.get("city") or geo_data.get("principalSubdivision")
                    if place:
                        loc_name = f"{place}{', ' + geo_data.get('principalSubdivision') if geo_data.get('principalSubdivision') and place != geo_data.get('principalSubdivision') else ''}"
            except Exception:
                pass

        if not lat or not lon:
            return jsonify({"success": False, "error": "Could not resolve location coordinates"}), 400

        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,wind_speed_10m"
        req_w = urllib.request.Request(weather_url, headers={'User-Agent': 'TadkaChulha/1.0'})
        with urllib.request.urlopen(req_w, timeout=5) as response:
            w_data = json_lib.loads(response.read().decode('utf-8'))
            temp = w_data.get("current", {}).get("temperature_2m")
            wind_speed = w_data.get("current", {}).get("wind_speed_10m", 0)
            
            if temp is None:
                return jsonify({"success": False, "error": "Temperature missing from weather dataset"}), 502
                
            wind_category = "Outdoors (Low Wind)"
            if wind_speed < 5:
                wind_category = "Indoors / Still Air"
            elif 5 <= wind_speed < 15:
                wind_category = "Outdoors (Low Wind)"
            elif 15 <= wind_speed < 25:
                wind_category = "Outdoors (Medium Wind)"
            elif wind_speed >= 25:
                wind_category = "Outdoors (High Wind)"

            return jsonify({
                "success": True,
                "temp": temp,
                "wind_speed": wind_speed,
                "wind_category": wind_category,
                "location": loc_name
            })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)
