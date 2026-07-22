document.addEventListener("DOMContentLoaded", () => {
    // UI State Management
    const state = {
        currentStepIndex: 0,
        steps: [
            'welcome', 'dish', 'qty', 'temp', 'wind', 'pellets', 'utensil', 'mass', 'lid', 'review', 'simulating', 'receipt'
        ],
        formData: {},
        appData: {},
        results: null
    };

    // DOM Elements
    const elements = {
        welcome: document.getElementById('step-welcome'),
        wizardForm: document.getElementById('wizard-form'),
        dishSelect: document.getElementById('dish_name'),
        qtyLabel: document.getElementById('qty_label'),
        qtyInput: document.getElementById('qty'),
        qtyUnit: document.getElementById('qty_unit'),
        pelletSelect: document.getElementById('pellet_name'),
        utensilSelect: document.getElementById('utensil_name'),
        windSelect: document.getElementById('wind_label'),
        mPotInput: document.getElementById('m_pot'),
        lidStep: document.getElementById('step-lid'),
        reviewStep: document.getElementById('step-review'),
        reviewSummary: document.getElementById('review-summary'),
        previewStats: document.getElementById('preview-stats'),
        simulatingStep: document.getElementById('step-simulating'),
        receiptStep: document.getElementById('step-receipt'),
        footer: document.getElementById('progress-footer'),
        btnRestartTop: document.getElementById('btn-restart-top')
    };

    // Initialization
    async function init() {
        try {
            const response = await fetch("/api/init");
            if (!response.ok) throw new Error("Load failed");
            state.appData = await response.json();
            populateSelects();
            attachListeners();
        } catch (err) {
            console.error(err);
        }
    }

    function populateSelects() {
        // Dishes
        state.appData.dishes.forEach(d => {
            const opt = new Option(d.name, d.name);
            elements.dishSelect.add(opt);
        });

        // Pellets
        state.appData.pellets.forEach(p => {
            const opt = new Option(p, p);
            elements.pelletSelect.add(opt);
        });

        // Utensils
        state.appData.utensils.forEach(u => {
            const opt = new Option(u.name, u.name);
            elements.utensilSelect.add(opt);
        });

        // Wind
        state.appData.wind_tiers.forEach(w => {
            const opt = new Option(w, w);
            elements.windSelect.add(opt);
        });

        updateDishFields();
        updateUtensilFields();
    }

    function attachListeners() {
        // Start Button
        document.getElementById('btn-start').onclick = () => goToStep(1);

        // Navigation Buttons
        document.querySelectorAll('.btn-next').forEach(btn => {
            btn.onclick = (e) => {
                const section = e.target.closest('section');
                if (validateSection(section)) {
                    if (e.target.id === 'btn-to-review') {
                        handleToReview();
                    } else {
                        nextStep();
                    }
                }
            };
        });

        document.querySelectorAll('.btn-prev').forEach(btn => {
            btn.onclick = prevStep;
        });

        // Dynamic Updates
        elements.dishSelect.onchange = updateDishFields;
        elements.utensilSelect.onchange = updateUtensilFields;

        // Review & Simulate
        document.getElementById('btn-back-to-form').onclick = () => goToStep(state.steps.indexOf('lid'));
        document.getElementById('btn-simulate').onclick = runSimulation;

        // Restart
        document.getElementById('btn-restart').onclick = restart;
        elements.btnRestartTop.onclick = restart;
    }

    // Step Logic
    function goToStep(index) {
        // Hide all steps
        document.querySelectorAll('.step-content').forEach(s => {
            s.classList.add('hidden');
            s.classList.remove('active');
        });
        
        elements.wizardForm.classList.toggle('hidden', index === 0 || index >= state.steps.indexOf('review'));

        state.currentStepIndex = index;
        const stepId = state.steps[index];
        const currentStep = document.getElementById(`step-${stepId}`);
        
        if (currentStep) {
            currentStep.classList.remove('hidden');
            setTimeout(() => currentStep.classList.add('active'), 10);
            
            // Focus input if exists
            const input = currentStep.querySelector('input, select');
            if (input) input.focus();
        }

        updateProgress();
        
        // Show/Hide top restart button
        elements.btnRestartTop.classList.toggle('hidden', index === 0);
    }

    function nextStep() {
        let nextIndex = state.currentStepIndex + 1;
        
        // Skip lid step if pressure cooker
        if (state.steps[nextIndex] === 'lid') {
            const uName = elements.utensilSelect.value;
            const utensil = state.appData.utensils.find(u => u.name === uName);
            if (utensil && utensil.is_pressure) {
                handleToReview();
                return;
            }
        }

        if (nextIndex < state.steps.length) {
            goToStep(nextIndex);
        }
    }

    function prevStep() {
        let prevIndex = state.currentStepIndex - 1;
        if (prevIndex >= 0) goToStep(prevIndex);
    }

    function validateSection(section) {
        const inputs = section.querySelectorAll('input, select');
        for (let input of inputs) {
            if (input.hasAttribute('required') && !input.value) {
                input.reportValidity();
                return false;
            }
        }
        return true;
    }

    function updateDishFields() {
        const dish = state.appData.dishes.find(d => d.name === elements.dishSelect.value);
        if (dish) {
            elements.qtyLabel.textContent = dish.qty_prompt;
            elements.qtyInput.min = dish.qty_min;
            elements.qtyInput.max = dish.qty_max;
            elements.qtyInput.value = dish.qty_default;
            elements.qtyInput.step = dish.qty_is_float ? "0.1" : "1";
            elements.qtyUnit.textContent = dish.qty_unit || "";
        }
    }

    function updateUtensilFields() {
        const utensil = state.appData.utensils.find(u => u.name === elements.utensilSelect.value);
        if (utensil) {
            elements.mPotInput.value = utensil.mass_kg;
        }
    }

    async function handleToReview() {
        updateFormData();
        goToStep(state.steps.indexOf('review'));
        renderReviewSummary();
        
        // Fetch preview data
        try {
            const data = await requestJson("/api/preview", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(state.formData)
            });
            renderPreviewStats(data);
        } catch (err) {
            console.error(err);
        }
    }

    function updateFormData() {
        const formData = new FormData(elements.wizardForm);
        state.formData = Object.fromEntries(formData);
    }

    function renderReviewSummary() {
        const items = [
            { label: 'Dish', value: state.formData.dish_name },
            { label: 'Quantity', value: `${state.formData.qty} ${elements.qtyUnit.textContent}` },
            { label: 'Ambient', value: `${state.formData.t_ambient_c} °C` },
            { label: 'Wind', value: state.formData.wind_label },
            { label: 'Pellet', value: state.formData.pellet_name },
            { label: 'Utensil', value: state.formData.utensil_name },
            { label: 'Vessel Mass', value: `${state.formData.m_pot} kg` }
        ];

        elements.reviewSummary.innerHTML = items.map(item => `
            <div class="p-4 border border-border rounded-xl">
                <p class="stat-label">${item.label}</p>
                <p class="font-bold">${item.value}</p>
            </div>
        `).join('');
    }

    function renderPreviewStats(data) {
        const stats = [
            { label: 'Heat-up', value: `${data.t_heat_est_min.toFixed(1)}m` },
            { label: 'Boil', value: `${data.t_boil_est_min.toFixed(1)}m` },
            { label: 'Kinetic', value: `${data.t_kinetic_base_min.toFixed(1)}m` },
            { label: 'Suggested', value: `${data.t_suggested_total_min.toFixed(0)}m` }
        ];

        elements.previewStats.innerHTML = stats.map(s => `
            <div>
                <p class="text-[10px] font-bold uppercase tracking-widest text-muted">${s.label}</p>
                <p class="text-lg font-bold">${s.value}</p>
            </div>
        `).join('');
        
        // Save suggested time
        state.formData.t_total_min = data.t_suggested_total_min;
    }

    async function runSimulation() {
        goToStep(state.steps.indexOf('simulating'));
        
        try {
            const data = await requestJson("/api/simulate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(state.formData)
            });
            state.results = data.receipt;
            renderReceipt();
            goToStep(state.steps.indexOf('receipt'));
        } catch (err) {
            alert(err.message);
            goToStep(state.steps.indexOf('review'));
        }
    }

    function renderReceipt() {
        const r = state.results;
        
        // Pellet Load
        const pelletsG = r.pellets_required_g;
        elements.receiptStep.querySelector('#receipt-pellets').textContent = 
            pelletsG >= 1000 ? `${(pelletsG/1000).toFixed(2)} kg` : `${pelletsG.toFixed(0)} g`;

        // Times
        document.getElementById('receipt-times').innerHTML = `
            <div class="flex justify-between"><span class="text-muted">Heat-up</span><span class="font-bold">${(r.t_heat_est_s/60).toFixed(1)}m</span></div>
            <div class="flex justify-between"><span class="text-muted">Kinetic</span><span class="font-bold">${(r.t_kinetic_base_s/60).toFixed(1)}m</span></div>
            <div class="flex justify-between border-t border-border pt-2 mt-2"><span class="text-foreground font-bold">Total Duration</span><span class="font-bold text-accent">${r.t_total_min_user.toFixed(1)}m</span></div>
        `;

        // Energy
        document.getElementById('receipt-energy').innerHTML = `
            <div class="flex justify-between"><span class="text-muted">Energy Supplied</span><span class="font-bold">${r.Q_in_kj.toFixed(0)} kJ</span></div>
            <div class="flex justify-between"><span class="text-muted">Heat Losses</span><span class="font-bold">${r.Q_out_kj.toFixed(0)} kJ</span></div>
            <div class="flex justify-between"><span class="text-muted">Sensible Heat</span><span class="font-bold">${r.Q_sensible_kj.toFixed(0)} kJ</span></div>
            <div class="flex justify-between border-t border-border pt-2 mt-2"><span class="text-foreground font-bold">Total Demand</span><span class="font-bold">${r.Q_demand_kj.toFixed(0)} kJ</span></div>
        `;

        // Safety
        let safetyHtml = "";
        if (r.flag_dry_boil) {
            safetyHtml = `<div class="p-4 bg-red-50 text-red-700 rounded-xl font-bold">⚠️ CRITICAL: Dry-boil detected.</div>`;
        } else if (r.flag_overheat) {
            safetyHtml = `<div class="p-4 bg-red-50 text-red-700 rounded-xl font-bold">⚠️ WARNING: Vessel overheat (${r.T_pot_c.toFixed(1)}°C).</div>`;
        } else {
            safetyHtml = `<div class="p-4 bg-green-50 text-green-700 rounded-xl font-bold">✓ Safe operation confirmed. Final temp: ${r.T_pot_c.toFixed(1)}°C</div>`;
        }
        document.getElementById('receipt-safety').innerHTML = safetyHtml;
    }

    function updateProgress() {
        const formSteps = state.steps.slice(1, state.steps.indexOf('review'));
        const currentFormIndex = formSteps.indexOf(state.steps[state.currentStepIndex]);
        
        if (currentFormIndex !== -1) {
            elements.footer.classList.remove('opacity-0', 'pointer-events-none');
            elements.footer.innerHTML = formSteps.map((_, i) => `
                <div class="progress-dot ${i === currentFormIndex ? 'active' : ''}"></div>
            `).join('');
        } else {
            elements.footer.classList.add('opacity-0', 'pointer-events-none');
        }
    }

    function restart() {
        elements.wizardForm.reset();
        goToStep(0);
    }

    async function requestJson(url, options = {}) {
        const response = await fetch(url, options);
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.success) {
            throw new Error(data.error || "Request failed");
        }
        return data;
    }

    init();
});
