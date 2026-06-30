(function () {
    const DRIVER_CSS_ID = 'transfer-operation-driver-css';
    const DRIVER_SCRIPT_ID = 'transfer-operation-driver-script';
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

    function buildSearchSteps() {
        const steps = [];
        addStep(
            steps,
            '[data-tour="transfer-operation-title"]',
            'Inicio de traslado',
            'Esta pantalla permite localizar una orden chequeada y habilitar el inicio de la carga.'
        );
        addStep(
            steps,
            '[data-tour="transfer-operation-search-card"]',
            'Búsqueda del traslado',
            'Ingresa el correlativo del traslado chequeado para cargar su información.',
            'right'
        );
        addStep(
            steps,
            '[data-tour="transfer-operation-input"]',
            'Correlativo',
            'Escribe el número exacto del traslado ya chequeado.'
        );
        addStep(
            steps,
            '[data-tour="transfer-operation-search-button"]',
            'Buscar traslado',
            'Con este botón se consulta la operación y se muestra el detalle asociado.',
            'top'
        );
        return steps;
    }

    function buildOperationalSteps() {
        const steps = [];
        addStep(
            steps,
            '[data-tour="transfer-operation-title"]',
            'Traslado cargado',
            'Aquí revisas el resumen de la orden antes de iniciar la salida.'
        );
        addStep(
            steps,
            '[data-tour="transfer-operation-summary"]',
            'Resumen del traslado',
            'Verifica correlativo, estado y cantidad de bultos antes de continuar.',
            'right'
        );
        addStep(
            steps,
            '[data-tour="transfer-operation-details-table"]',
            'Detalle de productos',
            'Este bloque muestra los productos y cantidades que deben salir en el traslado.',
            'top'
        );
        addStep(
            steps,
            '[data-tour="transfer-operation-start-card"]',
            'Inicio formal del traslado',
            'Completa los datos del responsable o deja el inicio asociado a tu usuario actual.',
            'right'
        );
        addStep(
            steps,
            '[data-tour="transfer-operation-user"]',
            'Usuario responsable',
            'Opcionalmente, registra quién firma la salida.'
        );
        addStep(
            steps,
            '[data-tour="transfer-operation-password"]',
            'Clave',
            'Usa la clave del responsable si quieres autenticar la firma manualmente.'
        );
        addStep(
            steps,
            '[data-tour="transfer-operation-start-button"]',
            'Iniciar traslado',
            'Al confirmar, la operación pasa a estado de traslado en tránsito.',
            'top'
        );
        return steps;
    }

    function getTourSteps() {
        const hasLoadedOperation = !!document.querySelector('[data-tour="transfer-operation-summary"]');
        return hasLoadedOperation ? buildOperationalSteps() : buildSearchSteps();
    }

    function startTransferOperationTour() {
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

    if (!window.__transferOperationTourListenerAttached) {
        document.addEventListener('click', function (event) {
            const tourButton = event.target.closest('[data-tour-start="transfer-operation"]');
            if (!tourButton) {
                return;
            }

            event.preventDefault();
            startTransferOperationTour();
        });

        window.__transferOperationTourListenerAttached = true;
    }
})();