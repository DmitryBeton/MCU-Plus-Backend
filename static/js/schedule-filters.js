const filtersForm = document.querySelector('[data-schedule-filters]');

if (filtersForm) {
    const instituteSelect = filtersForm.querySelector('[data-filter-field="institute"]');
    const courseSelect = filtersForm.querySelector('[data-filter-field="course"]');
    const groupSelect = filtersForm.querySelector('[data-filter-field="group"]');

    instituteSelect?.addEventListener('change', () => {
        if (courseSelect) {
            courseSelect.value = '';
        }
        if (groupSelect) {
            groupSelect.value = '';
        }
        filtersForm.requestSubmit();
    });

    courseSelect?.addEventListener('change', () => {
        if (groupSelect) {
            groupSelect.value = '';
        }
        filtersForm.requestSubmit();
    });

    groupSelect?.addEventListener('change', () => {
        filtersForm.requestSubmit();
    });
}

document.querySelectorAll('[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => {
        if (!window.confirm(form.dataset.confirm)) {
            event.preventDefault();
        }
    });
});
