frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        // Buttons nur bei Entwürfen anzeigen
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__('📅 Rechnungsdatum auf heute'), function() {
                set_posting_date_to_today(frm);
            }, __("Aktionen"));

            frm.add_custom_button(__('🎁 Selektiere Artikel ohne Berechnung'), function() {
                show_ohne_berechnung_dialog(frm);
            }, __("Aktionen"));

            style_actions_button(frm);
        }
    }
});

function style_actions_button(frm) {
    setTimeout(() => {
        frm.$wrapper
            .find('.inner-group-button[data-label="' + __("Aktionen") + '"] > .btn')
            .css({
                "background-color": "#e73249",
                "border-color": "#e73249",
                "color": "#fff",
            });
    }, 100);
}

function set_posting_date_to_today(frm) {
    const today = frappe.datetime.get_today();
    const old_date = frm.doc.posting_date;

    // Aktiviere "Edit Posting Date and Time"
    frm.set_value('set_posting_time', 1);

    // Setze Rechnungsdatum auf heute
    frm.set_value('posting_date', today);

    // Payment Schedule neu berechnen
    if (frm.doc.payment_terms_template) {
        // Wenn Payment Terms Template vorhanden, neu berechnen
        frappe.call({
            method: "erpnext.controllers.accounts_controller.get_payment_terms",
            args: {
                terms_template: frm.doc.payment_terms_template,
                posting_date: today,
                grand_total: frm.doc.rounded_total || frm.doc.grand_total,
                base_grand_total: frm.doc.base_rounded_total || frm.doc.base_grand_total,
                bill_date: frm.doc.bill_date
            },
            callback: function(r) {
                if (r.message && !r.exc) {
                    frm.set_value("payment_schedule", r.message);

                    // due_date auf das späteste Datum der Payment Schedule setzen
                    let max_due_date = today;
                    r.message.forEach(function(row) {
                        if (row.due_date && row.due_date > max_due_date) {
                            max_due_date = row.due_date;
                        }
                    });
                    frm.set_value('due_date', max_due_date);

                    frappe.show_alert({
                        message: __('Rechnungsdatum von {0} auf {1} geändert. Zahlungsbedingungen wurden aktualisiert.',
                            [frappe.datetime.str_to_user(old_date), frappe.datetime.str_to_user(today)]),
                        indicator: 'green'
                    }, 5);
                }
            }
        });
    } else {
        // Kein Template: due_date direkt auf heute setzen
        frm.set_value('due_date', today);

        // Falls payment_schedule Einträge existieren, Datum dort auch aktualisieren
        if (frm.doc.payment_schedule && frm.doc.payment_schedule.length > 0) {
            frm.doc.payment_schedule.forEach(function(row) {
                frappe.model.set_value(row.doctype, row.name, 'due_date', today);
            });
        }

        frappe.show_alert({
            message: __('Rechnungsdatum von {0} auf {1} geändert.',
                [frappe.datetime.str_to_user(old_date), frappe.datetime.str_to_user(today)]),
            indicator: 'green'
        }, 5);
    }

    frm.refresh_fields();
}

function show_ohne_berechnung_dialog(frm) {
    // Sammle ausgewählte Artikel
    const items_grid_wrapper = frm.fields_dict['items'].grid.wrapper;
    const grid_rows = items_grid_wrapper.find('.grid-row');
    let selected_items = [];

    grid_rows.each(function() {
        const $row = $(this);
        const is_checked = $row.find('.grid-row-check').is(':checked');
        const row_idx = $row.attr('data-idx');

        // Nur Zeilen mit gültigem data-idx verarbeiten (Header-Zeile überspringen)
        if (is_checked && row_idx) {
            const row_index = parseInt(row_idx) - 1;
            const item = frm.doc.items[row_index];

            if (item) {
                selected_items.push({
                    idx: item.idx,
                    item_code: item.item_code,
                    item_name: item.item_name,
                    qty: item.qty,
                    rate: item.rate,
                    amount: item.amount,
                    doctype: item.doctype,
                    name: item.name,
                    description: item.description
                });
            }
        }
    });

    if (selected_items.length === 0) {
        frappe.msgprint(__('Bitte wählen Sie mindestens einen Artikel aus.'));
        return;
    }

    // Summen berechnen
    const total_qty = selected_items.reduce((sum, item) => sum + item.qty, 0);
    const total_amount = selected_items.reduce((sum, item) => sum + item.amount, 0);

    // Tabelle erstellen
    let rows = selected_items.map(item => {
        return `<tr>
            <td style="padding: 8px;">${item.idx}</td>
            <td style="padding: 8px;">${item.item_code}</td>
            <td style="padding: 8px;">${item.item_name || ''}</td>
            <td style="padding: 8px; text-align: right;">${item.qty}</td>
            <td style="padding: 8px; text-align: right;">${format_currency(item.rate)}</td>
            <td style="padding: 8px; text-align: right;">${format_currency(item.amount)}</td>
        </tr>`;
    }).join('');

    const table_html = `
        <div style="margin-bottom: 15px;">
            <p style="font-size: 14px; margin-bottom: 10px;">
                Die folgenden <strong>${selected_items.length} Artikel</strong> werden auf <strong>100% Rabatt</strong> gesetzt
                und mit dem Hinweis <strong>"ohne Berechnung"</strong> versehen:
            </p>
        </div>
        <div style="max-height: 400px; overflow-y: auto;">
            <table class="table table-bordered" style="margin-bottom: 0;">
                <thead style="background-color: var(--bg-light-gray);">
                    <tr>
                        <th style="padding: 8px; width: 40px;">#</th>
                        <th style="padding: 8px;">Artikelcode</th>
                        <th style="padding: 8px;">Bezeichnung</th>
                        <th style="padding: 8px; text-align: right; width: 80px;">Menge</th>
                        <th style="padding: 8px; text-align: right; width: 100px;">Preis</th>
                        <th style="padding: 8px; text-align: right; width: 120px;">Betrag</th>
                    </tr>
                </thead>
                <tbody>
                    ${rows}
                </tbody>
                <tfoot style="background-color: var(--bg-light-gray); font-weight: bold;">
                    <tr>
                        <td colspan="3" style="padding: 8px;">Summe</td>
                        <td style="padding: 8px; text-align: right;">${total_qty}</td>
                        <td style="padding: 8px;"></td>
                        <td style="padding: 8px; text-align: right;">${format_currency(total_amount)}</td>
                    </tr>
                </tfoot>
            </table>
        </div>
        <div style="margin-top: 15px; padding: 10px; background-color: var(--alert-bg-warning); border-radius: 4px;">
            <strong>Hinweis:</strong> Diese Aktion kann nicht rückgängig gemacht werden.
            Der Rabatt muss manuell zurückgesetzt werden.
        </div>
    `;

    const dialog = new frappe.ui.Dialog({
        title: __('Artikel ohne Berechnung'),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'items_table',
                options: table_html
            }
        ],
        primary_action_label: __('Bestätigen'),
        primary_action: function() {
            apply_ohne_berechnung(frm, selected_items);
            dialog.hide();
        },
        secondary_action_label: __('Abbrechen')
    });

    dialog.show();
}

function apply_ohne_berechnung(frm, selected_items) {
    // Werte direkt auf den Doc-Objekten setzen (ohne einzelne set_value-Events)
    selected_items.forEach(item => {
        const doc_item = locals[item.doctype][item.name];
        if (!doc_item) return;

        // 100% Rabatt setzen
        doc_item.discount_percentage = 100;
        doc_item.discount_amount = 0;
        doc_item.rate = 0;
        doc_item.amount = 0;

        // Beschreibung bereinigen und "ohne Berechnung" genau einmal anhängen
        let desc = item.description || '';

        // Alle denkbaren Vorkommen entfernen
        const patterns = [
            /<p[^>]*>\s*<strong[^>]*>\s*ohne\s+berechnung\s*<\/strong>\s*<\/p>/gi,
            /<p[^>]*>\s*ohne\s+berechnung\s*<\/p>/gi,
            /<strong[^>]*>\s*ohne\s+berechnung\s*<\/strong>/gi,
            /\bohne\s+berechnung\b/gi
        ];
        patterns.forEach(re => { desc = desc.replace(re, ''); });

        // Leere Absätze beseitigen
        desc = desc.replace(/(<p[^>]*>\s*<\/p>)+/gi, '').trim();

        // Standard-Zeile einmal anhängen
        const stamp = '<p><strong>ohne Berechnung</strong></p>';
        doc_item.description = (desc ? desc + stamp : stamp);
    });

    // Einmalig Formular neu berechnen und aktualisieren
    frm.dirty();
    frm.script_manager.trigger('calculate_taxes_and_totals');
    frm.refresh_fields();

    frappe.show_alert({
        message: __("{0} Artikel wurden auf 'ohne Berechnung' gesetzt.", [selected_items.length]),
        indicator: 'green'
    }, 5);
}
