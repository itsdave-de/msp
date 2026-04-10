frappe.listview_settings["IT Domain"] = {
    onload(listview) {
        listview.page.add_inner_button("Domain Import Wizard", () => {
            show_import_wizard(listview);
        });

        listview.page.add_inner_button("Kunden zuordnen", () => {
            show_assignment_dialog(listview);
        });

        listview.page.add_inner_button("Alle anreichern (DNS/HTTP)", () => {
            frappe.confirm(
                "Alle Domains ohne bisherige Enrichment-Daten per DNS und HTTP abfragen? Das kann einige Minuten dauern.",
                () => {
                    frappe.call({
                        method: "msp.msp.doctype.it_domain.it_domain.enrich_all_domains",
                        freeze: true,
                        freeze_message: "Domains werden abgefragt...",
                        callback(r) {
                            if (r.message) {
                                frappe.msgprint({
                                    title: "Enrichment",
                                    message: `${r.message.enriched} Domains angereichert.`,
                                    indicator: "green",
                                });
                                listview.refresh();
                            }
                        },
                    });
                }
            );
        });
    },

    get_indicator(doc) {
        if (!doc.customer) {
            return ["Nicht zugeordnet", "orange", "customer,is,not set"];
        }
        const now = frappe.datetime.nowdate();
        const in30 = frappe.datetime.add_days(now, 30);
        if (doc.expiry_date && doc.expiry_date < now) {
            return ["Abgelaufen", "red", `expiry_date,<,${now}`];
        }
        if (doc.expiry_date && doc.expiry_date <= in30) {
            return ["Läuft bald ab", "orange", `expiry_date,<=,${in30}`];
        }
    },

    refresh() {
        if (document.getElementById("it-domain-badges-css")) return;
        const style = document.createElement("style");
        style.id = "it-domain-badges-css";
        style.textContent = `
            /* DNS badges */
            .indicator-pill[data-filter*="dns_hosting"][data-filter*="itsdave"] {
                background: #e8f5e9 !important; color: #2e7d32 !important;
            }
            .indicator-pill[data-filter*="dns_hosting"][data-filter*="Cloudflare"] {
                background: #fff3e0 !important; color: #e65100 !important;
            }
            .indicator-pill[data-filter*="dns_hosting"][data-filter*="Hetzner"],
            .indicator-pill[data-filter*="dns_hosting"][data-filter*="INWX"] {
                background: #e3f2fd !important; color: #1565c0 !important;
            }
            /* Mail badges */
            .indicator-pill[data-filter*="mail_routing"][data-filter*="Hornetsecurity"] {
                background: #c6f421 !important; color: #1a1a1a !important;
            }
            .indicator-pill[data-filter*="mail_routing"][data-filter*="Microsoft"] {
                background: #e3f2fd !important; color: #0078d4 !important;
            }
            .indicator-pill[data-filter*="mail_routing"][data-filter*="Google"] {
                background: #fce4ec !important; color: #c62828 !important;
            }
            .indicator-pill[data-filter*="mail_routing"][data-filter*="Self-hosted"] {
                background: #f3e5f5 !important; color: #6a1b9a !important;
            }
        `;
        document.head.appendChild(style);
    },
};


function show_import_wizard(listview) {
    const dialog = new frappe.ui.Dialog({
        title: "Domain Import Wizard",
        size: "large",
        fields: [
            {
                fieldname: "source",
                fieldtype: "Select",
                label: "Quelle",
                options: "Hetzner (CSV)\nDomainReselling.de (API)",
                default: "Hetzner (CSV)",
                reqd: 1,
                change() {
                    const val = dialog.get_value("source");
                    const is_hetzner = val.startsWith("Hetzner");
                    dialog.fields_dict.hetzner_section.$wrapper.toggle(is_hetzner);
                    dialog.fields_dict.dr_section.$wrapper.toggle(!is_hetzner);
                },
            },
            {
                fieldname: "hetzner_section",
                fieldtype: "Section Break",
                label: "Hetzner CSV-Dateien",
            },
            {
                fieldname: "domain_csv",
                fieldtype: "Attach",
                label: "Domain-CSV",
            },
            {
                fieldname: "handle_csv",
                fieldtype: "Attach",
                label: "Handle-CSV (optional)",
            },
            {
                fieldname: "dr_section",
                fieldtype: "Section Break",
                label: "DomainReselling.de Zugangsdaten",
                hidden: 1,
            },
            {
                fieldname: "dr_login",
                fieldtype: "Data",
                label: "Login",
            },
            {
                fieldname: "dr_password",
                fieldtype: "Password",
                label: "Passwort",
            },
            { fieldtype: "Section Break" },
            {
                fieldname: "result_html",
                fieldtype: "HTML",
            },
        ],
        primary_action_label: "Importieren",
        primary_action(values) {
            dialog.disable_primary_action();
            const is_hetzner = values.source.startsWith("Hetzner");

            if (is_hetzner) {
                if (!values.domain_csv) {
                    frappe.msgprint("Bitte Domain-CSV hochladen");
                    dialog.enable_primary_action();
                    return;
                }
                run_hetzner_import(dialog, listview, values);
            } else {
                if (!values.dr_login || !values.dr_password) {
                    frappe.msgprint("Bitte Login und Passwort eingeben");
                    dialog.enable_primary_action();
                    return;
                }
                run_dr_import(dialog, listview, values);
            }
        },
    });
    dialog.show();
}


function run_hetzner_import(dialog, listview, values) {
    fetch_file_and_call(
        values.domain_csv,
        "msp.msp.doctype.it_domain.it_domain.import_hetzner_csv",
        "file_content"
    ).then((domain_result) => {
        let html = format_import_result("Hetzner Domain-Import", domain_result);

        const handle_promise = values.handle_csv
            ? fetch_file_and_call(
                  values.handle_csv,
                  "msp.msp.doctype.it_domain.it_domain.import_hetzner_handles_csv",
                  "file_content"
              )
            : Promise.resolve(null);

        return handle_promise.then((handle_result) => {
            if (handle_result) {
                html += format_import_result("Handle-Import", handle_result);
            }
            finish_import(dialog, listview, html);
        });
    }).catch((err) => {
        dialog.enable_primary_action();
        frappe.msgprint({ title: "Fehler", message: String(err), indicator: "red" });
    });
}


function run_dr_import(dialog, listview, values) {
    frappe.call({
        method: "msp.msp.doctype.it_domain.it_domain.import_domainreselling",
        args: { login: values.dr_login, password: values.dr_password },
        callback(r) {
            if (r.message) {
                const html = format_import_result("DomainReselling.de Import", r.message);
                finish_import(dialog, listview, html);
            }
        },
        error() {
            dialog.enable_primary_action();
        },
    });
}


function finish_import(dialog, listview, html) {
    html += `<div class="mt-3">
        <button class="btn btn-primary btn-sm wizard-next-btn">
            Weiter zur Kundenzuordnung &rarr;
        </button>
    </div>`;
    dialog.fields_dict.result_html.$wrapper.html(html);
    dialog.set_primary_action("Schliessen", () => {
        dialog.hide();
        listview.refresh();
    });
    dialog.$wrapper.find(".wizard-next-btn").on("click", () => {
        dialog.hide();
        listview.refresh();
        show_assignment_dialog(listview);
    });
}


function show_assignment_dialog(listview) {
    frappe.call({
        method: "msp.msp.doctype.it_domain.it_domain.suggest_customers",
        freeze: true,
        freeze_message: "Analysiere Domains...",
        callback(r) {
            if (!r.message || !r.message.length) {
                frappe.msgprint("Alle Domains sind bereits zugeordnet.");
                return;
            }

            const all = r.message;
            const high = all.filter(s => s.confidence === "high");
            const rest = all.filter(s => s.confidence !== "high");

            let rows = all.map((s, idx) => {
                const conf_badge = s.confidence
                    ? `<span class="indicator-pill ${
                          { high: "green", medium: "orange", low: "gray" }[s.confidence]
                      }">${s.confidence}</span>`
                    : "";

                const registrant = s.registrant_name
                    ? `<br><small class="text-muted">${frappe.utils.escape_html(s.registrant_name)}</small>`
                    : "";

                const customer_cell = s.suggested_customer
                    ? `<span>${s.suggested_customer}</span>
                       <button class="btn btn-xs btn-default ml-1 change-customer" data-idx="${idx}" title="Aendern">
                           <i class="fa fa-pencil"></i>
                       </button>`
                    : `<button class="btn btn-xs btn-default pick-customer" data-idx="${idx}">
                           <i class="fa fa-search"></i> Waehlen
                       </button>`;

                const actions = s.suggested_customer
                    ? `<button class="btn btn-xs btn-primary apply-one" data-idx="${idx}" title="Zuweisen">
                           <i class="fa fa-check"></i>
                       </button>
                       <button class="btn btn-xs btn-default skip-one ml-1" data-idx="${idx}" title="Ueberspringen">
                           <i class="fa fa-times"></i>
                       </button>`
                    : "";

                return `<tr data-idx="${idx}" data-domain="${s.domain}">
                    <td><a href="/app/it-domain/${s.domain}" target="_blank">${s.domain}</a>${registrant}</td>
                    <td>${customer_cell}</td>
                    <td class="text-center">${s.match_type || ""} ${conf_badge}</td>
                    <td class="text-center action-cell">${actions}</td>
                </tr>`;
            });

            const dialog = new frappe.ui.Dialog({
                title: `Kundenzuordnung — ${all.length} Domains offen`,
                size: "extra-large",
                fields: [{
                    fieldtype: "HTML",
                    fieldname: "assign_html",
                    options: `
                    ${high.length ? `<div class="mb-3">
                        <button class="btn btn-sm btn-primary apply-all-high">
                            <i class="fa fa-check-circle"></i> Alle ${high.length} sicheren Vorschlaege zuweisen
                        </button>
                    </div>` : ""}
                    <div style="max-height:500px;overflow-y:auto">
                    <table class="table table-sm table-bordered" style="font-size:13px">
                        <thead><tr>
                            <th style="width:35%">Domain / Inhaber</th>
                            <th style="width:30%">Kunde</th>
                            <th style="width:15%">Match</th>
                            <th style="width:20%"></th>
                        </tr></thead>
                        <tbody>${rows.join("")}</tbody>
                    </table>
                    </div>`,
                }],
                primary_action_label: "Schliessen",
                primary_action() {
                    dialog.hide();
                    listview.refresh();
                },
            });

            // Single assign
            dialog.$wrapper.on("click", ".apply-one", function () {
                const idx = $(this).data("idx");
                const s = all[idx];
                if (!s.suggested_customer) return;
                apply_single(s.domain, s.suggested_customer, $(this).closest("tr"));
            });

            // Skip
            dialog.$wrapper.on("click", ".skip-one", function () {
                $(this).closest("tr").fadeOut(200);
            });

            // Pick / change customer
            dialog.$wrapper.on("click", ".pick-customer, .change-customer", function () {
                const idx = $(this).data("idx");
                const s = all[idx];
                frappe.prompt(
                    {
                        fieldname: "customer",
                        fieldtype: "Link",
                        options: "Customer",
                        label: `Kunde fuer ${s.domain}`,
                        description: s.registrant_name ? `Inhaber: ${s.registrant_name}` : "",
                    },
                    (values) => {
                        if (values.customer) {
                            s.suggested_customer = values.customer;
                            apply_single(s.domain, values.customer, dialog.$wrapper.find(`tr[data-idx="${idx}"]`));
                        }
                    },
                    "Kunde zuweisen"
                );
            });

            // Bulk assign high
            dialog.$wrapper.on("click", ".apply-all-high", function () {
                const btn = $(this);
                btn.prop("disabled", true).html('<i class="fa fa-spinner fa-spin"></i> Wird zugewiesen...');

                const promises = high.map(s =>
                    frappe.call({
                        method: "frappe.client.set_value",
                        args: { doctype: "IT Domain", name: s.domain, fieldname: "customer", value: s.suggested_customer },
                    }).then(() => {
                        dialog.$wrapper.find(`tr[data-domain="${s.domain}"]`).each(function () {
                            mark_done($(this));
                        });
                    })
                );

                Promise.all(promises).then(() => {
                    btn.replaceWith(`<span class="text-success"><i class="fa fa-check"></i> ${high.length} Domains zugewiesen</span>`);
                    frappe.show_alert({ message: `${high.length} Domains zugewiesen`, indicator: "green" });
                });
            });

            dialog.show();
        },
    });
}


function apply_single(domain, customer, tr_el) {
    frappe.call({
        method: "frappe.client.set_value",
        args: { doctype: "IT Domain", name: domain, fieldname: "customer", value: customer },
        callback() { mark_done(tr_el); },
    });
}


function mark_done(tr_el) {
    tr_el.find(".action-cell").html('<span class="text-success"><i class="fa fa-check"></i></span>');
    tr_el.css("opacity", "0.5");
}


function fetch_file_and_call(file_url, method, arg_name) {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("GET", file_url, true);
        xhr.onload = function () {
            if (xhr.status !== 200) {
                reject("Datei konnte nicht gelesen werden");
                return;
            }
            frappe.call({
                method,
                args: { [arg_name]: xhr.responseText },
                callback(r) { resolve(r.message); },
                error: reject,
            });
        };
        xhr.onerror = () => reject("Netzwerkfehler");
        xhr.send();
    });
}


function format_import_result(title, result) {
    if (result.created !== undefined) {
        let html = `<div class="alert alert-success mt-2">
            <strong>${title}:</strong>
            ${result.created} erstellt, ${result.updated} aktualisiert, ${result.skipped} unveraendert`;
        if (result.errors && result.errors.length) {
            html += `<br><small class="text-danger">${result.errors.length} Fehler</small>`;
        }
        return html + "</div>";
    }
    if (result.handles_parsed !== undefined) {
        return `<div class="alert alert-success mt-2">
            <strong>${title}:</strong>
            ${result.handles_parsed} Handles gelesen, ${result.domains_updated} Domains aktualisiert
        </div>`;
    }
    return "";
}
