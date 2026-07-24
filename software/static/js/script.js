document.addEventListener('DOMContentLoaded', () => {
    // 1. STATE
    const state = {
        currentStepIndex: 0,
        steps: ['welcome','dish','qty','temp','wind','pellets','utensil','mass','lid','review','simulating','receipt'],
        formData: {},
        appData: {},
        results: null,
        soundMuted: false
    };

    // 2. DOM ELEMENTS
    const elements = {
        // Existing
        welcome: document.getElementById('step-welcome'),
        wizardForm: document.getElementById('wizard-form'),
        dishSelect: document.getElementById('dish_name'),
        qtyLabel: document.getElementById('qty_label'),
        qtyInput: document.getElementById('qty'),
        qtyUnit: document.getElementById('qty_unit'),
        pelletSelect: document.getElementById('pellet_name'),
        dishCards: document.getElementById('dish-cards'),
        pelletCards: document.getElementById('pellet-cards'),
        utensilCards: document.getElementById('utensil-cards'),
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
        btnRestartTop: document.getElementById('btn-restart-top'),
        // New
        siteHeader: document.getElementById('site-header'),
        heroSection: document.getElementById('hero-section'),
        learnMore: document.getElementById('learn-more'),
        calculatorSection: document.getElementById('calculator-section'),
        calculatingBg: document.getElementById('calculating-bg'),
        muteToggle: document.getElementById('mute-toggle'),
        scrollImagePanel: document.getElementById('scroll-image-panel'),
        modalLicense: document.getElementById('modal-license'),
        modalAttributions: document.getElementById('modal-attributions')
    };

    // 3. CATEGORY DISPLAY NAME HELPER
    function displayCategory(cat) {
        if (!cat) return 'Uncategorized';
        const trimmed = cat.replace(/\s+/g, ' ').trim();
        const map = {
            'AL Pot': 'Aluminium Pot',
            'Kadhai / Wok': 'Kadhai / Wok',
            'Cooker': 'Pressure Cooker',
            'Steel': 'Stainless Steel',
            'Cast Iron': 'Cast Iron'
        };
        return map[trimmed] || trimmed;
    }

    // 4. INIT
    async function init() {
        try {
            const response = await fetch('/api/init');
            if (!response.ok) throw new Error('Load failed');
            state.appData = await response.json();
            populateSelects();
            attachListeners();
            initScrollytelling();
            initSectionNav();
            initModals();
        } catch (err) {
            console.error(err);
        }
    }

    // 5. POPULATE SELECTS
    function populateSelects() {
        // Dishes
        state.appData.dishes.forEach(d => {
            const opt = new Option(d.name, d.name);
            elements.dishSelect.add(opt);
        });

        // Pellets
        state.appData.pellets.forEach(p => {
            const opt = new Option(p.name, p.name);
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
        renderSelectionCards();
    }

    // Helper to generate a placeholder color and initials
    function getAvatarProps(name) {
        const initials = name.split(/[\s-]+/).slice(0, 2).map(w => w[0]).join('').toUpperCase();
        const hash = [...name].reduce((acc, char) => char.charCodeAt(0) + ((acc << 5) - acc), 0);
        const hue = Math.abs(hash % 360);
        return { initials, color: `hsl(${hue}, 40%, 60%)` };
    }

    // 6. RENDER SELECTION CARDS
    function renderSelectionCards() {
        renderCards(elements.dishCards, state.appData.dishes, elements.dishSelect, dish => {
            const avatar = getAvatarProps(dish.name);
            return `
            <div class="flex items-center gap-3 w-full text-left">
                <div class="w-12 h-12 rounded-lg bg-border overflow-hidden shrink-0 relative" style="background-color: ${avatar.color}">
                    <span class="absolute inset-0 flex items-center justify-center text-white font-bold text-sm" aria-hidden="true">${avatar.initials}</span>
                    <img src="/static/img/dishes/${createSlug(dish.name)}.jpg" alt="" class="absolute inset-0 w-full h-full object-cover z-10" onerror="this.style.display='none'">
                </div>
                <div class="flex-grow min-w-0">
                    <span class="selection-card__eyebrow block truncate">${escapeHtml(dish.category || 'Dish')}</span>
                    <strong class="block truncate">${escapeHtml(dish.name)}</strong>
                </div>
            </div>`;
        }, updateDishFields, 'dishes', '.selection-collage--food');

        renderCards(elements.pelletCards, state.appData.pellets, elements.pelletSelect, pellet => {
            const range = pellet.gcv_range_kcal || [];
            return `
            <div class="flex items-center gap-3 w-full text-left">
                <div class="flex-grow min-w-0">
                    <span class="selection-card__eyebrow block truncate">${escapeHtml(pellet.category)}</span>
                    <strong class="block truncate">${escapeHtml(pellet.name)}</strong>
                    <span class="selection-card__detail block truncate">${range[0]}–${range[1]} kcal/kg</span>
                </div>
            </div>`;
        }, null, null, null);

        // Custom Drill-Down logic for Utensils
        let currentUtensilCategory = null;
        
        function renderUtensilView() {
            const utensilCategories = {};
            state.appData.utensils.forEach(utensil => {
                const cat = getUtensilVisualCategory(utensil.name);
                if (!utensilCategories[cat]) utensilCategories[cat] = [];
                utensilCategories[cat].push(utensil);
            });

            if (!currentUtensilCategory) {
                // Render Categories
                elements.utensilCards.innerHTML = Object.keys(utensilCategories).map(cat => {
                    const avatar = getAvatarProps(cat);
                    const slug = createSlug(cat);
                    const count = utensilCategories[cat].length;
                    return `
                    <button type="button" class="selection-card w-full" data-action="drill" data-category="${escapeHtml(cat)}" data-search="${escapeHtml(cat).toLowerCase().replace(/[^a-z0-9]+/g, '')}" aria-pressed="false">
                        <div class="flex items-center gap-3 w-full text-left">
                            <div class="w-12 h-12 rounded-lg bg-border overflow-hidden shrink-0 relative" style="background-color: ${avatar.color}">
                                <span class="absolute inset-0 flex items-center justify-center text-white font-bold text-sm" aria-hidden="true">${avatar.initials}</span>
                                <img src="/static/img/utensils/${slug}.jpg" alt="" class="absolute inset-0 w-full h-full object-cover z-10" onerror="this.style.display='none'">
                            </div>
                            <div class="flex-grow min-w-0">
                                <strong class="block truncate">${escapeHtml(cat)}</strong>
                                <span class="selection-card__detail block truncate">${count} sizes available</span>
                            </div>
                            <div class="shrink-0 opacity-50">➔</div>
                        </div>
                    </button>`;
                }).join('');
            } else {
                // Render Sizes for currentUtensilCategory
                const items = utensilCategories[currentUtensilCategory];
                const slug = createSlug(currentUtensilCategory);
                
                const backBtn = `
                    <button type="button" class="btn-ghost flex items-center gap-2 mb-4 w-max p-2 -ml-2" data-action="back">
                        <span aria-hidden="true">←</span> Back to Categories
                    </button>
                `;
                
                const cards = items.map(u => {
                    let sizeLabel = u.name.replace(currentUtensilCategory, '').trim();
                    if (currentUtensilCategory === 'Kadhai / Wok') sizeLabel = u.name.replace('Kadhai', '').trim();
                    if (currentUtensilCategory === 'Cast Iron Tawa') sizeLabel = 'Standard';
                    if (currentUtensilCategory === 'Cast Iron BIG PAN') sizeLabel = 'Large';
                    if (sizeLabel === '') sizeLabel = 'Standard';
                    
                    return `
                    <button type="button" class="selection-card w-full" data-action="select" data-value="${escapeHtml(u.name)}" data-search="${escapeHtml(u.name).toLowerCase().replace(/[^a-z0-9]+/g, '')}" aria-pressed="false">
                        <div class="flex items-center gap-3 w-full text-left">
                            <div class="w-12 h-12 rounded-lg bg-border overflow-hidden shrink-0 relative flex items-center justify-center font-bold text-sm bg-black/[0.05]">
                                ${escapeHtml(sizeLabel)}
                            </div>
                            <div class="flex-grow min-w-0">
                                <span class="selection-card__eyebrow block truncate">${escapeHtml(currentUtensilCategory)}</span>
                                <strong class="block truncate">${escapeHtml(u.name)}</strong>
                            </div>
                        </div>
                    </button>`;
                }).join('');
                
                elements.utensilCards.innerHTML = backBtn + cards;
            }
            
            // Update collage immediately when category is selected
            if (currentUtensilCategory) {
                const collage = document.querySelector('.selection-collage--utensils');
                if (collage) {
                    const slug = createSlug(currentUtensilCategory);
                    collage.style.backgroundImage = `linear-gradient(rgba(0,0,0,0.3), rgba(0,0,0,0.6)), url('/static/img/utensils/${slug}.jpg')`;
                }
                
                elements.utensilCards.querySelectorAll('[data-action="select"]').forEach(card => {
                    const active = card.dataset.value === elements.utensilSelect.value;
                    card.classList.toggle('is-active', active);
                    card.setAttribute('aria-pressed', String(active));
                });
            }
            
            // Re-trigger search on the new view if a search term exists
            const searchInput = document.getElementById('search-utensil');
            if (searchInput && searchInput.value) {
                searchInput.dispatchEvent(new Event('input'));
            }
        }

        elements.utensilCards.addEventListener('click', e => {
            const btn = e.target.closest('button');
            if (!btn) return;
            
            if (btn.dataset.action === 'drill') {
                currentUtensilCategory = btn.dataset.category;
                renderUtensilView();
            } else if (btn.dataset.action === 'back') {
                currentUtensilCategory = null;
                renderUtensilView();
            } else if (btn.dataset.action === 'select') {
                elements.utensilSelect.value = btn.dataset.value;
                if (updateUtensilFields) updateUtensilFields();
                renderUtensilView();
            }
        });

        renderUtensilView();
    }

    function getUtensilVisualCategory(name) {
        if (name.includes('AL Pot')) return 'AL Pot';
        if (name.includes('Cooker')) return 'Cooker';
        if (name.startsWith('Kadhai')) return 'Kadhai / Wok';
        if (name.includes('Iron Tawa')) return 'Cast Iron Tawa';
        if (name.includes('Iron BIG PAN')) return 'Cast Iron BIG PAN';
        if (name.includes('Iron Kadhai')) return 'Cast Iron Kadhai';
        if (name.includes('Steel Pot')) return 'Steel Pot';
        if (name.includes('Steel Kadhai')) return 'Steel Kadhai';
        return 'Other';
    }

    function getUtensilCategory(name) {
        if (name.startsWith('Kadhai')) return 'Kadhai / Wok';
        if (name.startsWith('AL Pot')) return 'AL Pot';
        if (name.startsWith('Cooker')) return 'Cooker';
        if (name.startsWith('Iron') || name.startsWith('Cast')) return 'Cast Iron';
        if (name.includes('Steel')) return 'Steel';
        return 'Cooking Vessel';
    }

    // Helper to generate clean slugs for images
    function createSlug(text) {
        return text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
    }

    // 7. renderCards
    function renderCards(container, items, select, content, onChange, imgFolder, collageSelector) {
        container.innerHTML = items.map(item => `
            <button type="button" class="selection-card w-full" data-value="${escapeHtml(item.name)}" data-search="${escapeHtml(item.name).toLowerCase().replace(/[^a-z0-9]+/g, '')}" aria-pressed="false">${content(item)}</button>
        `).join('');
        const sync = () => {
            container.querySelectorAll('.selection-card').forEach(card => {
                const active = card.dataset.value === select.value;
                card.classList.toggle('is-active', active);
                card.setAttribute('aria-pressed', String(active));
            });
            if (imgFolder && collageSelector) {
                const collage = document.querySelector(collageSelector);
                if (collage && select.value) {
                    const slug = createSlug(select.value);
                    // Add gradient overlay + image, but also keep a fallback background color
                    collage.style.backgroundImage = `linear-gradient(rgba(0,0,0,0.3), rgba(0,0,0,0.6)), url('/static/img/${imgFolder}/${slug}.jpg')`;
                }
            }
        };
        container.addEventListener('click', event => {
            const card = event.target.closest('.selection-card');
            if (!card) return;
            select.value = card.dataset.value;
            if (onChange) onChange();
            sync();
        });
        container.addEventListener('scroll', () => {
            const cards = [...container.querySelectorAll('.selection-card')];
            const centre = container.getBoundingClientRect().top + container.clientHeight / 2;
            const nearest = cards.reduce((best, card) => Math.abs(card.getBoundingClientRect().top + card.offsetHeight / 2 - centre) < Math.abs(best.getBoundingClientRect().top + best.offsetHeight / 2 - centre) ? card : best, cards[0]);
            if (nearest && nearest.dataset.value !== select.value) {
                select.value = nearest.dataset.value;
                if (onChange) onChange();
                sync();
            }
        }, { passive: true });
        sync();
    }

    // 8. escapeHtml
    function escapeHtml(value) {
        const node = document.createElement('span');
        node.textContent = value ?? '';
        return node.innerHTML;
    }

    // 9. attachListeners
    function attachListeners() {
        // Start Button
        const btnStart = document.getElementById('btn-start');
        if (btnStart) btnStart.onclick = () => goToStep(1);

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
        const btnBackToForm = document.getElementById('btn-back-to-form');
        if (btnBackToForm) btnBackToForm.onclick = () => goToStep(state.steps.indexOf('lid'));
        
        const btnSimulate = document.getElementById('btn-simulate');
        if (btnSimulate) btnSimulate.onclick = runSimulation;

        // Restart
        const btnRestart = document.getElementById('btn-restart');
        if (btnRestart) btnRestart.onclick = restart;
        if (elements.btnRestartTop) elements.btnRestartTop.onclick = restart;

        // New events
        const btnHeroCalculate = document.getElementById('btn-hero-calculate');
        if (btnHeroCalculate) {
            btnHeroCalculate.onclick = () => {
                if (elements.calculatorSection) {
                    elements.calculatorSection.scrollIntoView({ behavior: 'smooth' });
                }
                goToStep(0);
            };
        }

        if (elements.muteToggle) {
            elements.muteToggle.onclick = toggleMute;
        }

        // Search Handlers
        const setupSearch = (inputId, containerId) => {
            const input = document.getElementById(inputId);
            const container = document.getElementById(containerId);
            if (!input || !container) return;
            
            input.addEventListener('input', (e) => {
                const query = e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, '');
                const cards = container.querySelectorAll('.selection-card');
                let firstVisible = null;
                
                cards.forEach(card => {
                    const searchData = card.dataset.search || '';
                    if (searchData.includes(query)) {
                        card.style.display = '';
                        if (!firstVisible) firstVisible = card;
                    } else {
                        card.style.display = 'none';
                    }
                });
                
                // Optional: auto-select first visible match if query is long enough
                // if (query.length > 2 && firstVisible) {
                //     firstVisible.click();
                //     firstVisible.scrollIntoView({ block: 'nearest' });
                // }
            });
        };
        
        setupSearch('search-dish', 'dish-cards');
        setupSearch('search-pellet', 'pellet-cards');
        setupSearch('search-utensil', 'utensil-cards');
    }

    // 10. goToStep
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
        if (elements.btnRestartTop) elements.btnRestartTop.classList.toggle('hidden', index === 0);
    }

    // 11. nextStep
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

    // 12. prevStep
    function prevStep() {
        let prevIndex = state.currentStepIndex - 1;
        if (prevIndex >= 0) goToStep(prevIndex);
    }

    // 13. validateSection
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

    // 14. updateDishFields
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

    // 15. updateUtensilFields
    function updateUtensilFields() {
        const utensil = state.appData.utensils.find(u => u.name === elements.utensilSelect.value);
        if (utensil) {
            elements.mPotInput.value = utensil.mass_kg;
        }
    }

    // 16. handleToReview
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

    // 17. updateFormData
    function updateFormData() {
        const formData = new FormData(elements.wizardForm);
        state.formData = Object.fromEntries(formData);
    }

    // 18. renderReviewSummary
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

    // 19. renderPreviewStats
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

    // 20. runSimulation
    async function runSimulation() {
        // Set calculating background
        if (elements.calculatingBg) {
            elements.calculatingBg.style.backgroundImage = 'linear-gradient(135deg, #2D4F36 0%, #1A1A1A 100%)';
        }
        
        goToStep(state.steps.indexOf('simulating'));
        playCookingSound();
        
        try {
            const data = await requestJson('/api/simulate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(state.formData)
            });
            state.results = data.receipt;
            stopCookingSound();
            renderReceipt();
            goToStep(state.steps.indexOf('receipt'));
        } catch (err) {
            stopCookingSound();
            alert(err.message);
            goToStep(state.steps.indexOf('review'));
        }
    }

    // 21. renderReceipt
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

    // 22. updateProgress
    function updateProgress() {
        const formSteps = state.steps.slice(1, state.steps.indexOf('review'));
        const currentFormIndex = formSteps.indexOf(state.steps[state.currentStepIndex]);
        
        if (currentFormIndex !== -1 && elements.footer) {
            elements.footer.classList.remove('opacity-0', 'pointer-events-none');
            elements.footer.innerHTML = formSteps.map((_, i) => `
                <div class="progress-dot ${i === currentFormIndex ? 'active' : ''}"></div>
            `).join('');
        } else if (elements.footer) {
            elements.footer.classList.add('opacity-0', 'pointer-events-none');
        }
    }

    // 23. restart
    function restart() {
        elements.wizardForm.reset();
        goToStep(0);
        if (elements.calculatorSection) {
            elements.calculatorSection.scrollIntoView({ behavior: 'smooth' });
        }
    }

    // 24. requestJson
    async function requestJson(url, options = {}) {
        const response = await fetch(url, options);
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.success) {
            throw new Error(data.error || "Request failed");
        }
        return data;
    }

    // 25. SCROLLYTELLING
    function initScrollytelling() {
        const panels = document.querySelectorAll('.scroll-panel');
        if (!panels.length || !elements.scrollImagePanel) return;
        
        const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    // Remove active from all
                    panels.forEach(p => p.classList.remove('is-active'));
                    // Add active to current
                    entry.target.classList.add('is-active');
                    // Swap image
                    const img = entry.target.dataset.image;
                    if (img && elements.scrollImagePanel) {
                        elements.scrollImagePanel.style.backgroundImage = `url('${img}')`;
                    }
                }
            });
        }, {
            threshold: 0.5,
            rootMargin: '-20% 0px -20% 0px'
        });
        
        panels.forEach(panel => observer.observe(panel));
    }

    // 26. SECTION NAVIGATION
    function initSectionNav() {
        // Smooth scroll for nav links
        document.querySelectorAll('.header-nav a[href^="#"]').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const target = document.querySelector(link.getAttribute('href'));
                if (target) target.scrollIntoView({ behavior: 'smooth' });
            });
        });
        
        // Active section tracking with IntersectionObserver
        const sections = [elements.heroSection, elements.learnMore, elements.calculatorSection].filter(Boolean);
        const navLinks = document.querySelectorAll('.header-nav a[data-nav]');
        
        const sectionObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const id = entry.target.id;
                    navLinks.forEach(link => {
                        link.classList.toggle('active', link.getAttribute('href') === '#' + id);
                    });
                }
            });
        }, { threshold: 0.3 });
        
        sections.forEach(s => sectionObserver.observe(s));
        
        // Header background on scroll
        if (elements.siteHeader) {
            window.addEventListener('scroll', () => {
                elements.siteHeader.classList.toggle('scrolled', window.scrollY > 50);
            }, { passive: true });
        }
    }

    // 27. MODAL HANDLING
    function initModals() {
        const licenseLink = document.getElementById('link-license');
        const attribLink = document.getElementById('link-attributions');
        
        if (licenseLink && elements.modalLicense) {
            licenseLink.addEventListener('click', (e) => {
                e.preventDefault();
                elements.modalLicense.classList.add('is-visible');
            });
        }
        if (attribLink && elements.modalAttributions) {
            attribLink.addEventListener('click', (e) => {
                e.preventDefault();
                elements.modalAttributions.classList.add('is-visible');
            });
        }
        
        // Close modals
        document.querySelectorAll('.modal-backdrop').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal || e.target.classList.contains('modal-close')) {
                    modal.classList.remove('is-visible');
                }
            });
        });
    }

    // 28. SOUND MANAGER
    let cookingSoundInterval = null;

    function playCookingSound() {
        // Respect prefers-reduced-motion
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
        if (state.soundMuted) return;
        // Sound infrastructure ready — actual audio file to be added later
        // When a real .mp3 file is placed at /static/audio/cooking-sizzle.mp3,
        // uncomment the Audio playback code below:
        // const audio = new Audio('/static/audio/cooking-sizzle.mp3');
        // audio.loop = true;
        // audio.volume = 0.3;
        // audio.play().catch(() => {});
        // state.cookingAudio = audio;
    }

    function stopCookingSound() {
        // if (state.cookingAudio) { state.cookingAudio.pause(); state.cookingAudio = null; }
    }

    function toggleMute() {
        state.soundMuted = !state.soundMuted;
        if (elements.muteToggle) {
            elements.muteToggle.textContent = state.soundMuted ? '🔇' : '🔊';
        }
        if (state.soundMuted) stopCookingSound();
    }

    // 29. CALL init()
    init();
});
