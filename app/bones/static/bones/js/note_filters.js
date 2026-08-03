(function () {
    function initializeSelect2(scope) {
        if (!window.jQuery || !window.jQuery.fn.select2) return;
        window.jQuery(scope).find('.bones-select2').each(function () {
            const field = window.jQuery(this);
            if (!field.data('select2')) {
                field.select2({
                    width: '100%',
                    placeholder: field.data('placeholder') || '',
                    allowClear: !field.prop('multiple')
                });
            }
        });
    }

    document.querySelectorAll('[data-note-filter-group]').forEach(function (group) {
        const list = group.querySelector('[data-note-filter-list]');
        const addButton = group.querySelector('[data-note-filter-add]');
        const prefix = group.dataset.noteFilterPrefix;
        const mapElement = document.getElementById(list.dataset.noteResponseMapId);
        const responseMap = mapElement ? JSON.parse(mapElement.textContent) : {};

        function setResponses(row, selectedValues) {
            const note = row.querySelector('[data-note-field="note"]');
            const responses = row.querySelector('[data-note-field="response"]');
            const selected = new Set(selectedValues || []);
            responses.innerHTML = '';
            (responseMap[note.value] || []).forEach(function (choice) {
                const option = document.createElement('option');
                option.value = choice[0];
                option.textContent = choice[1];
                option.selected = selected.has(choice[0]);
                responses.appendChild(option);
            });
            if (window.jQuery && window.jQuery.fn.select2) {
                window.jQuery(responses).trigger('change');
            }
        }

        function handleNoteChange(noteField) {
            setResponses(noteField.closest('[data-note-filter-row]'), []);
        }

        if (window.jQuery) {
            window.jQuery(list).on(
                'change',
                '[data-note-field="note"]',
                function () { handleNoteChange(this); }
            );
        } else {
            list.addEventListener('change', function (event) {
                if (event.target.matches('[data-note-field="note"]')) {
                    handleNoteChange(event.target);
                }
            });
        }
        list.addEventListener('click', function (event) {
            const button = event.target.closest('[data-note-filter-remove]');
            if (!button) return;
            const rows = list.querySelectorAll('[data-note-filter-row]');
            const row = button.closest('[data-note-filter-row]');
            if (rows.length > 1) {
                row.remove();
            } else {
                row.querySelector('[data-note-field="note"]').value = '';
                setResponses(row, []);
            }
        });
        addButton.addEventListener('click', function () {
            const rows = list.querySelectorAll('[data-note-filter-row]');
            if (rows.length >= Number(addButton.dataset.noteFilterMax || 10)) return;
            const clone = rows[rows.length - 1].cloneNode(true);
            clone.querySelectorAll('.select2').forEach(function (element) { element.remove(); });
            clone.querySelectorAll('[data-note-field]').forEach(function (field) {
                const id = prefix + rows.length + '_' + field.dataset.noteField;
                field.name = id;
                field.id = id;
                field.removeAttribute('data-select2-id');
                field.classList.remove('select2-hidden-accessible');
                field.removeAttribute('tabindex');
                field.removeAttribute('aria-hidden');
                const label = field.closest('.w3-col').querySelector('label');
                if (label) label.htmlFor = id;
            });
            clone.querySelector('[data-note-field="note"]').value = '';
            setResponses(clone, []);
            list.appendChild(clone);
            initializeSelect2(clone);
        });
        initializeSelect2(group);
    });
})();
