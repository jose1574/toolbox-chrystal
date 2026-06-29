(function () {
    const alertRoot = document.getElementById('v2-party-alert');
    if (!alertRoot || window.__dashboardPartyAttached) {
        return;
    }

    const triggerButton = document.getElementById('v2-party-trigger');
    const chipNew = alertRoot.querySelector('[data-party-chip="new"]');
    const chipVersion = alertRoot.querySelector('[data-party-chip="version"]');
    const rootElement = document.documentElement;
    const LAYER_ID = 'v2-confetti-layer';
    const SHOW_DURATION_MS = 10000;
    const WAVE_INTERVAL_MS = 420;

    function isDarkThemeActive() {
        return (rootElement.getAttribute('data-bs-theme') || '').toLowerCase() === 'dark';
    }

    function getConfettiColors() {
        if (isDarkThemeActive()) {
            return ['#ff8787', '#ffd43b', '#63e6be', '#74c0fc', '#b197fc', '#f783ac'];
        }

        return ['#ff6b6b', '#f06595', '#ffd43b', '#69db7c', '#4dabf7', '#845ef7'];
    }

    function applyThemeStyles() {
        if (isDarkThemeActive()) {
            alertRoot.style.background = 'linear-gradient(135deg, rgba(52, 58, 64, 0.95) 0%, rgba(73, 80, 87, 0.92) 45%, rgba(33, 37, 41, 0.95) 100%)';
            alertRoot.style.border = '1px solid rgba(255, 193, 7, 0.35)';

            if (chipNew) {
                chipNew.className = 'badge text-bg-warning text-dark';
            }
            if (chipVersion) {
                chipVersion.className = 'badge text-bg-info text-dark';
            }
            if (triggerButton) {
                triggerButton.className = 'btn btn-sm btn-warning text-dark';
            }
            return;
        }

        alertRoot.style.background = 'linear-gradient(135deg, #fff3cd 0%, #ffe8a3 45%, #ffd6a5 100%)';
        alertRoot.style.border = '1px solid rgba(33, 37, 41, 0.08)';

        if (chipNew) {
            chipNew.className = 'badge text-bg-dark';
        }
        if (chipVersion) {
            chipVersion.className = 'badge text-bg-danger';
        }
        if (triggerButton) {
            triggerButton.className = 'btn btn-sm btn-dark';
        }
    }

    function ensureLayer() {
        let layer = document.getElementById(LAYER_ID);
        if (layer) {
            return layer;
        }

        layer = document.createElement('div');
        layer.id = LAYER_ID;
        layer.setAttribute('aria-hidden', 'true');
        document.body.appendChild(layer);
        return layer;
    }

    function ensureStyles() {
        if (document.getElementById('dashboard-party-style')) {
            return;
        }

        const style = document.createElement('style');
        style.id = 'dashboard-party-style';
        style.textContent = '' +
            '#v2-confetti-layer {' +
            'position: fixed;' +
            'inset: 0;' +
            'pointer-events: none;' +
            'overflow: hidden;' +
            'z-index: 2000;' +
            '}' +
            '.v2-confetti-piece {' +
            'position: fixed;' +
            'top: -12px;' +
            'width: 10px;' +
            'height: 14px;' +
            'opacity: 0.92;' +
            'border-radius: 2px;' +
            'pointer-events: none;' +
            'animation: v2-confetti-fall linear forwards;' +
            '}' +
            '@keyframes v2-confetti-fall {' +
            '0% { transform: translate3d(0, 0, 0) rotate(0deg); opacity: 1; }' +
            '100% { transform: translate3d(var(--drift-x, 0px), 110vh, 0) rotate(var(--spin, 720deg)); opacity: 0; }' +
            '}';
        document.head.appendChild(style);
    }

    function emitWave(layer, count, width, topLimit) {
        const pieces = count || 28;
        const topBoundary = Math.max(0, topLimit || 0);
        const colors = getConfettiColors();

        for (let i = 0; i < pieces; i += 1) {
            const piece = document.createElement('span');
            const color = colors[Math.floor(Math.random() * colors.length)];
            const duration = 1500 + Math.round(Math.random() * 900);
            const delay = Math.round(Math.random() * 140);
            const left = Math.round(Math.random() * width);
            const size = 8 + Math.round(Math.random() * 7);
            const drift = Math.round((Math.random() - 0.5) * 180);
            const spin = 540 + Math.round(Math.random() * 540);

            piece.className = 'v2-confetti-piece';
            piece.style.left = left + 'px';
            piece.style.top = (topBoundary > 0 ? Math.round(Math.random() * topBoundary) : -12) + 'px';
            piece.style.backgroundColor = color;
            piece.style.width = size + 'px';
            piece.style.height = Math.max(10, size + 4) + 'px';
            piece.style.animationDuration = duration + 'ms';
            piece.style.animationDelay = delay + 'ms';
            piece.style.setProperty('--drift-x', drift + 'px');
            piece.style.setProperty('--spin', spin + 'deg');

            layer.appendChild(piece);

            const cleanupTime = duration + delay + 220;
            setTimeout(function () {
                piece.remove();
            }, cleanupTime);
        }
    }

    function createConfettiBurst(amount) {
        const burstSize = amount || 36;
        const layer = ensureLayer();
        const width = Math.max(window.innerWidth, 320);
        const startTime = Date.now();

        emitWave(layer, burstSize, width, 0);

        const intervalId = setInterval(function () {
            const elapsed = Date.now() - startTime;
            if (elapsed >= SHOW_DURATION_MS) {
                clearInterval(intervalId);
                return;
            }

            const extraPieces = Math.max(12, Math.round(burstSize * 0.55));
            emitWave(layer, extraPieces, width, 90);
        }, WAVE_INTERVAL_MS);

        setTimeout(function () {
            clearInterval(intervalId);
        }, SHOW_DURATION_MS + WAVE_INTERVAL_MS);
    }

    applyThemeStyles();
    const themeObserver = new MutationObserver(function () {
        applyThemeStyles();
    });
    themeObserver.observe(rootElement, { attributes: true, attributeFilter: ['data-bs-theme'] });

    ensureStyles();
    createConfettiBurst(42);

    if (triggerButton) {
        triggerButton.addEventListener('click', function () {
            createConfettiBurst(56);
        });
    }

    window.__dashboardPartyAttached = true;
})();
