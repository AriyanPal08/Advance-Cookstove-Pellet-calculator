document.addEventListener("DOMContentLoaded", () => {
    const configForm = document.getElementById("config-form");
    const previewPanel = document.getElementById("preview-panel");
    const receiptPanel = document.getElementById("receipt-panel");
    const simulatingPanel = document.getElementById("simulating");
    const loadingPanel = document.getElementById("loading");
    const formMessage = document.getElementById("form-message");

    let appData = {};

    function showFormError(message) {
        formMessage.textContent = message;
        formMessage.classList.remove("hidden");
    }

    function clearFormError() {
        formMessage.textContent = "";
        formMessage.classList.add("hidden");
    }

    async function requestJson(url, options = {}) {
        const response = await fetch(url, options);
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.success) {
            throw new Error(data.error || "The calculator could not complete this request.");
        }
        return data;
    }

    // Elements
    const dishSelect = document.getElementById("dish_name");
    const qtyLabel = document.getElementById("qty_label");
    const qtyInput = document.getElementById("qty");
    const qtyUnit = document.getElementById("qty_unit");
    const utensilSelect = document.getElementById("utensil_name");
    const lidGroup = document.getElementById("lid_group");
    const mPotInput = document.getElementById("m_pot");

    // Initialize data
    fetch("/api/init")
        .then(res => {
            if (!res.ok) throw new Error("Calculator data could not be loaded.");
            return res.json();
        })
        .then(data => {
            appData = data;
            
            // Populate Dishes
            data.dishes.forEach(d => {
                const opt = document.createElement("option");
                opt.value = d.name;
                opt.textContent = d.name;
                dishSelect.appendChild(opt);
            });

            // Populate Pellets
            const pelletSelect = document.getElementById("pellet_name");
            data.pellets.forEach(p => {
                const opt = document.createElement("option");
                opt.value = p;
                opt.textContent = p;
                pelletSelect.appendChild(opt);
            });

            // Populate Utensils
            data.utensils.forEach(u => {
                const opt = document.createElement("option");
                opt.value = u.name;
                opt.textContent = u.name;
                utensilSelect.appendChild(opt);
            });

            // Populate Wind Tiers
            const windSelect = document.getElementById("wind_label");
            data.wind_tiers.forEach(w => {
                const opt = document.createElement("option");
                opt.value = w;
                opt.textContent = w;
                windSelect.appendChild(opt);
            });

            loadingPanel.classList.add("hidden");
            configForm.classList.remove("hidden");
            
            updateDishFields();
            updateUtensilFields();
        })
        .catch(error => {
            loadingPanel.innerHTML = `<p class="text-error">${error.message}</p><p>Please refresh the page or check that the calculator server is running.</p>`;
        });

    dishSelect.addEventListener("change", updateDishFields);
    utensilSelect.addEventListener("change", updateUtensilFields);

    function updateDishFields() {
        const dName = dishSelect.value;
        const dish = appData.dishes.find(d => d.name === dName);
        if(!dish) return;

        qtyLabel.textContent = dish.qty_prompt;
        qtyInput.min = dish.qty_min;
        qtyInput.max = dish.qty_max;
        qtyInput.value = dish.qty_default;
        qtyInput.step = dish.qty_is_float ? "0.1" : "1";
        
        if (dish.qty_unit) {
            qtyUnit.textContent = dish.qty_unit;
            qtyUnit.style.display = "inline-block";
        } else {
            qtyUnit.style.display = "none";
        }
    }

    function updateUtensilFields() {
        const uName = utensilSelect.value;
        const utensil = appData.utensils.find(u => u.name === uName);
        if(!utensil) return;

        mPotInput.value = utensil.mass_kg;
        if (utensil.is_pressure) {
            lidGroup.style.display = "none";
        } else {
            lidGroup.style.display = "block";
        }
    }

    configForm.addEventListener("submit", (e) => {
        e.preventDefault();
        clearFormError();
        
        const payload = Object.fromEntries(new FormData(configForm));
        
        requestJson("/api/preview", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        })
        .then(data => {
            document.getElementById("preview_heat").textContent = data.t_heat_est_min.toFixed(1) + " min";
            document.getElementById("preview_boil").textContent = data.t_boil_est_min.toFixed(1) + " min";
            document.getElementById("preview_kinetic").textContent = data.t_kinetic_base_min.toFixed(1) + " min";
            document.getElementById("preview_buffer").textContent = data.t_safety_buffer_s.toFixed(0) + " s";
            document.getElementById("t_total_min").value = data.t_suggested_total_min.toFixed(1);

            configForm.classList.add("hidden");
            previewPanel.classList.remove("hidden");
        })
        .catch(error => showFormError(error.message));
    });

    document.getElementById("btn-back").addEventListener("click", () => {
        previewPanel.classList.add("hidden");
        configForm.classList.remove("hidden");
    });

    document.getElementById("btn-simulate").addEventListener("click", () => {
        const payload = Object.fromEntries(new FormData(configForm));
        payload.t_total_min = document.getElementById("t_total_min").value;
        
        previewPanel.classList.add("hidden");
        simulatingPanel.classList.remove("hidden");

        requestJson("/api/simulate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        })
        .then(data => {
            simulatingPanel.classList.add("hidden");
            renderReceipt(data.receipt);
            receiptPanel.classList.remove("hidden");
        })
        .catch(error => {
            simulatingPanel.classList.add("hidden");
            configForm.classList.remove("hidden");
            showFormError(error.message);
        });
    });

    document.getElementById("btn-restart").addEventListener("click", () => {
        receiptPanel.classList.add("hidden");
        clearFormError();
        configForm.classList.remove("hidden");
    });

    function renderReceipt(r) {
        const inputsHtml = `
            <tr><td>Dish</td><td>${r.dish_name}</td></tr>
            ${r.water_liters ? `<tr><td>Water Volume</td><td>${r.water_liters} L</td></tr>` : `<tr><td>Portions</td><td>${r.portions}</td></tr>`}
            <tr><td>Ambient Temp</td><td>${r.t_ambient_c.toFixed(1)} °C</td></tr>
            <tr><td>Wind Factor</td><td>${r.wind_label}</td></tr>
            <tr><td>Utensil</td><td>${r.utensil_name}</td></tr>
            <tr><td>Vessel Mass (used)</td><td>${r.m_pot.toFixed(3)} kg</td></tr>
            <tr><td>Lid State</td><td>${r.lid_label}</td></tr>
            <tr><td>Pellet</td><td>${r.pellet_name}</td></tr>
            <tr><td>Stove Power (P_in)</td><td>${r.P_in_kw.toFixed(6)} kW</td></tr>
        `;
        document.getElementById("receipt-inputs").innerHTML = inputsHtml;

        const timesHtml = `
            <tr><td>Estimated heat-up time</td><td>${(r.t_heat_est_s/60).toFixed(1)} min</td></tr>
            <tr><td>Kinetic time</td><td>${(r.t_kinetic_base_s/60).toFixed(1)} min</td></tr>
            <tr><td>User-selected total</td><td>${r.t_total_min_user.toFixed(1)} min</td></tr>
        `;
        document.getElementById("receipt-times").innerHTML = timesHtml;

        const energyHtml = `
            <tr><td>Energy supplied (Q_in)</td><td>${r.Q_in_kj.toFixed(2)} kJ</td></tr>
            <tr><td>Heat losses (Q_out)</td><td>${r.Q_out_kj.toFixed(2)} kJ</td></tr>
            <tr><td>Sensible heating</td><td>${r.Q_sensible_kj.toFixed(2)} kJ</td></tr>
            <tr><td>Evaporation (Q_evap)</td><td>${r.Q_evap_kj.toFixed(2)} kJ</td></tr>
            <tr><td>Thermodynamic demand</td><td>${r.Q_demand_kj.toFixed(2)} kJ</td></tr>
        `;
        document.getElementById("receipt-energy").innerHTML = energyHtml;

        let safetyHtml = "";
        if (r.flag_dry_boil) {
            safetyHtml += `<p class="text-error">[FATAL] DRY-BOIL DETECTED</p>`;
        } else {
            safetyHtml += `<p class="text-success">✓ No dry-boil event</p>`;
        }
        if (r.flag_overheat) {
            safetyHtml += `<p class="text-error">[CRITICAL] VESSEL OVERHEAT</p>`;
        } else {
            safetyHtml += `<p class="text-success">✓ Final temp: ${r.T_pot_c.toFixed(1)} °C</p>`;
        }
        document.getElementById("receipt-safety").innerHTML = safetyHtml;

        const pelletsG = r.pellets_required_g;
        let pelletText = pelletsG.toFixed(1) + " g";
        if (pelletsG >= 1000) pelletText += ` (${(pelletsG/1000).toFixed(3)} kg)`;
        document.getElementById("receipt-pellets").textContent = pelletText;
        document.getElementById("receipt-pellets-details").textContent = `Time-based reference: ${r.pellets_time_based_g.toFixed(1)} g | [${r.pellet_name}]`;
    }
});
