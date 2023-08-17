
import frappe

@frappe.whitelist()
def copy_attachments(source_doctype, source_docname, target_doctype, target_docname):
    attachments = frappe.get_all("File", filters={"attached_to_doctype": source_doctype, "attached_to_name": source_docname})

    for attachment in attachments:
        # Überprüfen Sie den Datei-URL-Wert
        file_url = frappe.db.get_value("File", attachment.name, "file_url")
        
        # Überprüfen, ob ein Anhang mit derselben URL bereits für das Ziel-Dokument existiert
        exists = frappe.db.exists({
            "doctype": "File",
            "file_url": file_url,
            "attached_to_doctype": target_doctype,
            "attached_to_name": target_docname
        })

        if not exists:
            # Wenn nicht existiert, dann Anhang zum Ziel-Dokument kopieren
            attach = frappe.get_doc({
                "doctype": "File",
                "file_url": file_url,
                "attached_to_doctype": target_doctype,
                "attached_to_name": target_docname
            })
            attach.insert(ignore_permissions=True)

""" Benötigt das folgende Client Script für Quotation Form

frappe.ui.form.on('Quotation', {
    refresh: function(frm) {
        frm.add_custom_button(__('Anhänge hinzufügen'), function() {
            attach_item_attachments_to_quotation(frm);
        }, "Aktionen");
    }
});

function attach_item_attachments_to_quotation(frm) {
    frm.doc.items.forEach(item_row => {
        frappe.call({
            method: 'msp.quotation_tools.copy_attachments',
            args: {
                'source_doctype': 'Item',
                'source_docname': item_row.item_code, // Verwenden Sie item_code, um den Anhang vom Artikel zu kopieren
                'target_doctype': 'Quotation',
                'target_docname': frm.doc.name
            },
            callback: function(response) {
                if (!response.exc) {
                    frm.reload_doc();
                }
            }
        });
    });
    frappe.msgprint(__('Anhänge wurden hinzugefügt.'));
}
 """