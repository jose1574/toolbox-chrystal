(function () {
    function getRoot() {
        return document.getElementById('document-manager-page');
    }

    function getState(root) {
        if (!root) return null;

        return {
            selectAllCheckbox: root.querySelector('#select-all-operations'),
            rowCheckboxes: Array.from(root.querySelectorAll('.operation-checkbox')),
            deleteBtn: root.querySelector('#delete-btn'),
            selectedCountSpan: root.querySelector('#selected-count'),
        };
    }

    function updateUI() {
        const root = getRoot();
        const state = getState(root);
        if (!state) return;

        const { selectAllCheckbox, rowCheckboxes, deleteBtn, selectedCountSpan } = state;
        const total = rowCheckboxes.length;
        const checked = rowCheckboxes.filter((cb) => cb.checked).length;

        if (selectedCountSpan) {
            selectedCountSpan.textContent = String(checked);
        }

        if (deleteBtn) {
            deleteBtn.disabled = checked === 0;
        }

        if (selectAllCheckbox) {
            selectAllCheckbox.indeterminate = checked > 0 && checked < total;
            selectAllCheckbox.checked = total > 0 && checked === total;
        }
    }

    function setAllRowsChecked(checked) {
        const root = getRoot();
        const state = getState(root);
        if (!state) return;

        state.rowCheckboxes.forEach((cb) => {
            cb.checked = checked;
        });

        updateUI();
    }

    function getSelectedCorrelatives() {
        const root = getRoot();
        const state = getState(root);
        if (!state) return [];

        return state.rowCheckboxes
            .filter((cb) => cb.checked)
            .map((cb) => cb.value)
            .filter((value) => value !== null && value !== undefined && String(value).trim() !== '');
    }

    function deleteSelected() {
        const root = getRoot();
        const state = getState(root);
        if (!state || !state.deleteBtn) return;

        const selected = getSelectedCorrelatives();
        if (selected.length === 0) return;

        const url = state.deleteBtn.getAttribute('data-delete-url');
        if (!url) {
            console.error('No se encontró data-delete-url para eliminar.');
            return;
        }

        if (!confirm('¿Estás seguro de que quieres eliminar las operaciones seleccionadas?')) {
            return;
        }

        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ correlatives: selected }),
        })
            .then((response) =>
                response.json().then((data) => ({ ok: response.ok, data }))
            )
            .then(({ ok, data }) => {
                if (ok && data && data.status === 'success') {
                    window.location.reload();
                    return;
                }

                const message = (data && (data.message || data.detail)) || 'Ocurrió un error al intentar eliminar.';
                alert('Error: ' + message);
            })
            .catch((error) => {
                console.error('Error:', error);
                alert('Ocurrió un error al intentar eliminar las operaciones.');
            });
    }

    // Delegated events so it works with HTMX swaps.
    document.addEventListener('change', function (event) {
        const root = getRoot();
        if (!root) return;

        const target = event.target;
        if (!(target instanceof Element)) return;
        if (!root.contains(target)) return;

        if (target.id === 'select-all-operations') {
            setAllRowsChecked(target.checked);
            return;
        }

        if (target.classList.contains('operation-checkbox')) {
            updateUI();
        }
    });

    document.addEventListener('click', function (event) {
        const root = getRoot();
        if (!root) return;

        const target = event.target;
        if (!(target instanceof Element)) return;

        const deleteBtn = target.closest('#delete-btn');
        if (!deleteBtn) return;
        if (!root.contains(deleteBtn)) return;

        event.preventDefault();
        deleteSelected();
    });

    document.addEventListener('DOMContentLoaded', updateUI);

    // When content is swapped in via HTMX, refresh the UI state.
    document.body.addEventListener('htmx:load', updateUI);
    document.body.addEventListener('htmx:afterSwap', updateUI);
})();
