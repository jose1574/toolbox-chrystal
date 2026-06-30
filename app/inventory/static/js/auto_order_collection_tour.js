(function () {
    const DRIVER_CSS_ID = 'auto-order-driver-css';
    const DRIVER_SCRIPT_ID = 'auto-order-driver-script';
    const DRIVER_CSS_URL = 'https://cdn.jsdelivr.net/npm/driver.js@1.3.6/dist/driver.css';
    const DRIVER_SCRIPT_URL = 'https://cdn.jsdelivr.net/npm/driver.js@1.3.6/dist/driver.js.iife.js';

    function ensureDriverCss() {
        if (document.getElementById(DRIVER_CSS_ID)) {
            return;
        }

        const cssLink = document.createElement('link');
        cssLink.id = DRIVER_CSS_ID;
        cssLink.rel = 'stylesheet';
        cssLink.href = DRIVER_CSS_URL;
        document.head.appendChild(cssLink);
    }

    function ensureDriverScript() {
        if (window.driver && window.driver.js && typeof window.driver.js.driver === 'function') {
            return Promise.resolve();
        }

        const existingScript = document.getElementById(DRIVER_SCRIPT_ID);
        if (existingScript && existingScript.dataset.loaded === 'true') {
            return Promise.resolve();
        }

        if (existingScript) {
            return new Promise(function (resolve, reject) {
                existingScript.addEventListener('load', resolve, { once: true });
                existingScript.addEventListener('error', reject, { once: true });
            });
        }

        return new Promise(function (resolve, reject) {
            const script = document.createElement('script');
            script.id = DRIVER_SCRIPT_ID;
            script.src = DRIVER_SCRIPT_URL;
            script.defer = true;
            script.addEventListener('load', function () {
                script.dataset.loaded = 'true';
                resolve();
            }, { once: true });
            script.addEventListener('error', reject, { once: true });
            document.head.appendChild(script);
        });
    }

    function addStep(steps, selector, title, description, side) {
        const element = document.querySelector(selector);
        if (!element) {
            return;
        }

        steps.push({
            element: element,
            popover: {
                title: title,
                description: description,
                side: side || 'bottom',
                align: 'start'
            }
        });
    }

    function buildStoreSelectionSteps() {
        const steps = [];
        addStep(
            steps,
            '[data-tour="auto-order-title"]',
            'Orden automatica de recoleccion',
            'En esta pantalla defines origen y destino para generar una orden basada en faltantes de stock.'
        );
        addStep(
            steps,
            '[data-tour="auto-order-store-form"]',
            'Seleccion de depositos',
            'Primero selecciona los dos depositos para cargar la lista de productos sugeridos.',
            'right'
        );
        addStep(
            steps,
            '[data-tour="auto-order-store-origin"]',
            'Deposito origen',
            'Aqui se toma el stock disponible para transferir.'
        );
        addStep(
            steps,
            '[data-tour="auto-order-store-destination"]',
            'Deposito destino',
            'Aqui se recibiran los productos transferidos.'
        );
        addStep(
            steps,
            '[data-tour="auto-order-store-submit"]',
            'Aplicar seleccion',
            'Al aplicar se cargan filtros, tabla y cantidades a transferir.',
            'top'
        );
        return steps;
    }

    function buildOperationalSteps() {
        const steps = [];
        addStep(
            steps,
            '[data-tour="auto-order-title"]',
            'Orden automatica activa',
            'Ya puedes revisar y ajustar la propuesta de transferencia.'
        );
        addStep(
            steps,
            '[data-tour="auto-order-active-stores"]',
            'Contexto actual',
            'Verifica el par de depositos antes de generar la orden.'
        );
        addStep(
            steps,
            '[data-tour="auto-order-stores-card"]',
            'Resumen de depositos',
            'Este bloque deja visible origen y destino durante la operacion.'
        );
        addStep(
            steps,
            '[data-tour="auto-order-filter-panel"]',
            'Panel de filtros',
            'Usa busqueda, departamento y marca para acotar la lista de productos.',
            'right'
        );
        addStep(
            steps,
            '[data-tour="auto-order-search-input"]',
            'Busqueda rapida',
            'Filtra por codigo o descripcion en tiempo real.'
        );
        addStep(
            steps,
            '[data-tour="auto-order-clear-filters"]',
            'Limpiar filtros',
            'Restablece la busqueda y todos los checks de filtros.',
            'left'
        );
        addStep(
            steps,
            '[data-tour="auto-order-results-table"]',
            'Tabla de sugerencias',
            'Selecciona productos y valida la cantidad sugerida en A Transferir.',
            'top'
        );
        addStep(
            steps,
            '[data-tour="auto-order-generate-button"]',
            'Generar orden',
            'Cuando termines de validar seleccion y cantidades, genera la orden para continuar el proceso.',
            'left'
        );
        return steps;
    }

    function getTourSteps() {
        const hasStoreForm = !!document.querySelector('[data-tour="auto-order-store-form"]');
        return hasStoreForm ? buildStoreSelectionSteps() : buildOperationalSteps();
    }

    function startAutoOrderTour() {
        ensureDriverCss();
        ensureDriverScript()
            .then(function () {
                if (!window.driver || !window.driver.js || typeof window.driver.js.driver !== 'function') {
                    return;
                }

                const steps = getTourSteps();
                if (!steps.length) {
                    return;
                }

                const tour = window.driver.js.driver({
                    showProgress: true,
                    allowClose: true,
                    overlayClickBehavior: 'close',
                    doneBtnText: 'Finalizar',
                    nextBtnText: 'Siguiente',
                    prevBtnText: 'Anterior'
                });

                tour.setSteps(steps);
                tour.drive();
            })
            .catch(function () {
                // Keep the screen usable if the external tour library is unavailable.
            });
    }

    if (!window.__autoOrderTourListenerAttached) {
        document.addEventListener('click', function (event) {
            const tourButton = event.target.closest('[data-tour-start="auto-order"]');
            if (!tourButton) {
                return;
            }

            event.preventDefault();
            startAutoOrderTour();
        });

        window.__autoOrderTourListenerAttached = true;
    }
})();
