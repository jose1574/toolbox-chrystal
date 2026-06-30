(function () {
    const DRIVER_CSS_ID = 'check-order-driver-css';
    const DRIVER_SCRIPT_ID = 'check-order-driver-script';
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

    function buildLoadOrderSteps() {
        const steps = [];
        addStep(
            steps,
            '[data-tour="check-order-title"]',
            'Chequeo de orden de recoleccion',
            'Desde esta pantalla cargas una orden para iniciar el conteo de productos.'
        );
        addStep(
            steps,
            '[data-tour="check-order-load-card"]',
            'Ingreso de correlativo',
            'Primero necesitas el correlativo de la orden emitida.',
            'right'
        );
        addStep(
            steps,
            '[data-tour="check-order-input"]',
            'Correlativo',
            'Escribe el numero de orden para cargar su detalle y comenzar el chequeo.'
        );
        addStep(
            steps,
            '[data-tour="check-order-load-button"]',
            'Cargar orden',
            'Al cargar, el sistema trae los productos y abre automaticamente un bulto inicial.',
            'top'
        );
        return steps;
    }

    function buildOperationalSteps() {
        const steps = [];
        addStep(
            steps,
            '[data-tour="check-order-title"]',
            'Orden en chequeo',
            'Aqui trabajas sobre una orden activa de recoleccion.'
        );
        addStep(
            steps,
            '[data-tour="check-order-route-info"]',
            'Ruta del traslado',
            'Valida deposito de origen y destino antes de contar productos.'
        );
        addStep(
            steps,
            '[data-tour="check-order-product-search"]',
            'Busqueda por codigo',
            'Escanea o escribe un codigo para abrir el modal de conteo del producto.',
            'bottom'
        );
        addStep(
            steps,
            '[data-tour="check-order-package-toggle"]',
            'Control de bulto',
            'Este boton alterna entre abrir y cerrar bulto segun el estado actual.',
            'left'
        );
        addStep(
            steps,
            '[data-tour="check-order-package-progress"]',
            'Estado de embalaje',
            'Muestra el bulto abierto y el acumulado de productos y unidades embaladas.'
        );
        addStep(
            steps,
            '[data-tour="check-order-view-packages"]',
            'Historial de bultos',
            'Abre el listado de bultos generados para esta orden.',
            'left'
        );
        addStep(
            steps,
            '[data-tour="check-order-products-table"]',
            'Tabla de chequeo',
            'Aqui comparas cantidad ordenada, cantidad contada y estado por producto.',
            'top'
        );
        addStep(
            steps,
            '[data-tour="check-order-confirm-button"]',
            'Confirmar chequeo',
            'Cuando todo este validado, confirma el chequeo para cerrar el proceso.',
            'top'
        );
        return steps;
    }

    function getTourSteps() {
        const hasLoadCard = !!document.querySelector('[data-tour="check-order-load-card"]');
        return hasLoadCard ? buildLoadOrderSteps() : buildOperationalSteps();
    }

    function startCheckOrderTour() {
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
                // Keep the module usable even if the CDN is unavailable.
            });
    }

    if (!window.__checkOrderTourListenerAttached) {
        document.addEventListener('click', function (event) {
            const tourButton = event.target.closest('[data-tour-start="check-order"]');
            if (!tourButton) {
                return;
            }

            event.preventDefault();
            startCheckOrderTour();
        });

        window.__checkOrderTourListenerAttached = true;
    }
})();
