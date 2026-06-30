(function () {
    const DRIVER_CSS_ID = 'transfer-reception-driver-css';
    const DRIVER_SCRIPT_ID = 'transfer-reception-driver-script';
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
            '[data-tour="transfer-reception-title"]',
            'Recepción de traslado',
            'Aquí comienzas el proceso buscando una operación que ya salió en tránsito.'
        );
        addStep(
            steps,
            '[data-tour="transfer-reception-search-card"]',
            'Buscar traslado',
            'Ingresa el correlativo para cargar la operación y pasar al modo de recepción.',
            'right'
        );
        addStep(
            steps,
            '[data-tour="transfer-reception-input"]',
            'Correlativo',
            'Escribe el número del traslado que quieres recibir.'
        );
        addStep(
            steps,
            '[data-tour="transfer-reception-search-button"]',
            'Buscar traslado',
            'Con este botón el sistema carga la orden y habilita la pantalla de recepción.',
            'top'
        );
        return steps;
    }

    function buildOperationalSteps() {
        const steps = [];
        addStep(
            steps,
            '[data-tour="transfer-reception-summary"]',
            'Resumen del traslado',
            'Confirma correlativo, fecha, descripción y estado antes de seguir.',
            'right'
        );
        addStep(
            steps,
            '[data-tour="transfer-reception-new-search"]',
            'Nueva búsqueda',
            'Si cargaste la orden equivocada, vuelve al inicio para buscar otra.',
            'top'
        );
        addStep(
            steps,
            '[data-tour="transfer-reception-product-search-button"]',
            'Buscar producto',
            'Usa este campo para abrir el modal de conteo de un producto específico.',
            'bottom'
        );
        addStep(
            steps,
            '[data-tour="transfer-reception-close-card"]',
            'Cierre de recepción',
            'Cuando todos los productos estén registrados, esta sección habilita el cierre.',
            'right'
        );
        addStep(
            steps,
            '[data-tour="transfer-reception-products-table"]',
            'Tabla de recepción',
            'Aquí ves cantidades esperadas, contadas y diferencias de cada producto.',
            'top'
        );
        addStep(
            steps,
            '[data-tour="transfer-reception-close-button"]',
            'Cerrar, recepcionar y procesar',
            'Este botón finaliza el flujo cuando ya no quedan diferencias pendientes.',
            'left'
        );
        return steps;
    }

    function getTourSteps() {
        const hasOperationLoaded = !!document.querySelector('[data-tour="transfer-reception-summary"]');
        return hasOperationLoaded ? buildOperationalSteps() : buildSearchSteps();
    }

    function startTransferReceptionTour() {
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

    if (!window.__transferReceptionTourListenerAttached) {
        document.addEventListener('click', function (event) {
            const tourButton = event.target.closest('[data-tour-start="transfer-reception"]');
            if (!tourButton) {
                return;
            }

            event.preventDefault();
            startTransferReceptionTour();
        });

        window.__transferReceptionTourListenerAttached = true;
    }
})();