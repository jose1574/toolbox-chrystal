(function () {
    const DRIVER_CSS_ID = 'manual-order-driver-css';
    const DRIVER_SCRIPT_ID = 'manual-order-driver-script';
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
            '[data-tour="manual-order-title"]',
            'Orden manual de recoleccion',
            'Esta pantalla permite crear una orden manual para mover productos entre depositos.'
        );
        addStep(
            steps,
            '[data-tour="manual-order-store-form"]',
            'Primer paso',
            'Selecciona deposito origen y destino para habilitar buscador, detalle y carrito.',
            'right'
        );
        addStep(
            steps,
            '[data-tour="manual-order-store-origin"]',
            'Deposito origen',
            'Desde aqui se descuenta el stock cuando confirmas la orden.'
        );
        addStep(
            steps,
            '[data-tour="manual-order-store-destination"]',
            'Deposito destino',
            'Aqui se trasladaran los productos al confirmar la orden.'
        );
        addStep(
            steps,
            '[data-tour="manual-order-store-submit"]',
            'Continuar',
            'Al continuar se carga el flujo operativo completo. Luego puedes usar Ver recorrido nuevamente.',
            'top'
        );
        return steps;
    }

    function buildOperationalSteps() {
        const steps = [];
        addStep(
            steps,
            '[data-tour="manual-order-title"]',
            'Orden manual activa',
            'Ya tienes un origen y destino seleccionados para operar.'
        );
        addStep(
            steps,
            '[data-tour="manual-order-active-stores"]',
            'Contexto de traslado',
            'Valida aqui los depositos actuales antes de cargar productos.'
        );
        addStep(
            steps,
            '[data-tour="manual-order-barcode-form"]',
            'Escaneo rapido',
            'Esta opcion es alternativa: si tienes scanner, puedes buscar directo por codigo.',
            'right'
        );
        addStep(
            steps,
            '[data-tour="manual-order-filters"]',
            'Filtros',
            'Refina por marca, departamento y estado de stock para acotar resultados.',
            'right'
        );
        addStep(
            steps,
            '[data-tour="manual-order-search-input"]',
            'Busqueda principal',
            'Escribe descripcion o codigo. La lista se actualiza automaticamente con HTMX.'
        );
        addStep(
            steps,
            '[data-tour="manual-order-search-results"]',
            'Resultados',
            'Selecciona un producto para actualizar el panel de detalle.',
            'right'
        );
        addStep(
            steps,
            '[data-tour="manual-order-detail-panel-root"]',
            'Detalle del producto',
            'Aqui revisas existencias y parametros del producto en origen y destino.'
        );
        addStep(
            steps,
            '[data-tour="manual-order-quantity-form"]',
            'Cantidad a ordenar',
            'Usa los controles +/- o edita el valor manualmente antes de agregar al carrito.',
            'left'
        );
        addStep(
            steps,
            '[data-tour="manual-order-add-button"]',
            'Agregar a la orden',
            'Este boton envia el producto y cantidad al carrito de la derecha.',
            'left'
        );
        addStep(
            steps,
            '[data-tour="manual-order-cart-root"]',
            'Carrito de orden',
            'Aqui validas y ajustas lineas antes de confirmar.',
            'left'
        );
        addStep(
            steps,
            '[data-tour="manual-order-confirm-button"]',
            'Cierre del proceso',
            'Cuando termines de validar, confirma la orden. El recorrido termina aqui antes del envio.',
            'left'
        );
        return steps;
    }

    function getTourSteps() {
        const hasStoreForm = !!document.querySelector('[data-tour="manual-order-store-form"]');
        return hasStoreForm ? buildStoreSelectionSteps() : buildOperationalSteps();
    }

    function startManualOrderTour() {
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
                // Intentionally silent to avoid breaking the inventory flow if CDN fails.
            });
    }

    if (!window.__manualOrderTourListenerAttached) {
        document.addEventListener('click', function (event) {
            const tourButton = event.target.closest('[data-tour-start="manual-order"]');
            if (!tourButton) {
                return;
            }

            event.preventDefault();
            startManualOrderTour();
        });
        window.__manualOrderTourListenerAttached = true;
    }

    if (!window.__openPdfListenerAttached) {
        window.addEventListener('open-pdf', function (e) {
            if (e.detail && e.detail.url) {
                window.open(e.detail.url, '_blank');
            }
        });
        window.__openPdfListenerAttached = true;
    }

    document.addEventListener('click', function (event) {
        const button = event.target.closest('[data-qty-action]');
        if (!button) {
            return;
        }

        const form = button.closest('form');
        if (!form) {
            return;
        }

        const input = form.querySelector('#manual-product-quantity');
        if (!input) {
            return;
        }

        const currentValue = parseFloat(input.value || '0');
        const safeValue = Number.isFinite(currentValue) ? currentValue : 0;
        const delta = button.dataset.qtyAction === 'increment' ? 1 : -1;
        const nextValue = Math.max(0, safeValue + delta);

        input.value = nextValue.toFixed(2);
        input.dispatchEvent(new Event('change', { bubbles: true }));
    });
})();
