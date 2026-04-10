frappe.ui.form.on("IT Domain", {
    refresh(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button("Enrich (DNS/HTTP/SSL)", () => {
                frappe.call({
                    method: "msp.msp.doctype.it_domain.it_domain.enrich_domain",
                    args: { name: frm.doc.name },
                    freeze: true,
                    freeze_message: `Resolving ${frm.doc.domain}...`,
                    callback(r) {
                        frm.reload_doc();
                        if (r.message) {
                            frappe.show_alert({
                                message: `${frm.doc.domain}: ${r.message.website_title || "kein Titel"} (${r.message.resolved_ip || "keine IP"})`,
                                indicator: "green",
                            });
                        }
                    },
                });
            });
        }
    },
});
