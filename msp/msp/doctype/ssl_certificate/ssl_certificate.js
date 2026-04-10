function copy_to_clipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
        return navigator.clipboard.writeText(text);
    }
    // Fallback for non-HTTPS contexts
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    document.body.removeChild(textarea);
    return Promise.resolve();
}

frappe.ui.form.on("SSL Certificate", {
    refresh(frm) {
        if (!frm.is_new() && frm.doc.certificate_data) {
            frm.trigger("render_downloads");
        }
    },

    render_downloads(frm) {
        const cn = frm.doc.common_name || frm.doc.name;
        const has_key = !!frm.doc.private_key;
        const has_ca = !!frm.doc.ca_chain;
        const has_csr = !!frm.doc.csr_data;

        const btn = (label, icon, format_type, disabled) => {
            const cls = disabled ? "btn-default disabled" : "btn-primary-light";
            const title = disabled ? 'title="Nicht vorhanden"' : "";
            return `<button class="btn btn-sm ${cls} mr-2 mb-2" ${title}
                data-format="${format_type}" ${disabled ? "disabled" : ""}>
                <i class="fa fa-${icon}"></i> ${label}
            </button>`;
        };

        const copy_btn = (label, format_type, disabled) => {
            const cls = disabled ? "btn-default disabled" : "btn-default";
            const title = disabled ? 'title="Nicht vorhanden"' : "";
            return `<button class="btn btn-sm ${cls} mr-2 mb-2 copy-btn" ${title}
                data-format="${format_type}" ${disabled ? "disabled" : ""}>
                <i class="fa fa-clipboard"></i> ${label}
            </button>`;
        };

        const html = `
        <div>
            <div class="mb-3">
                <strong class="text-muted d-block mb-2">Download</strong>
                ${btn("Certificate", "certificate", "cert", false)}
                ${btn("Private Key", "key", "key", !has_key)}
                ${btn("Fullchain", "link", "fullchain", false)}
                ${btn("Cert + Key", "files-o", "cert_key", !has_key)}
                ${btn("CA Chain", "sitemap", "ca", !has_ca)}
                ${btn("CSR", "file-text-o", "csr", !has_csr)}
            </div>
            <div>
                <strong class="text-muted d-block mb-2">Copy to Clipboard</strong>
                ${copy_btn("Certificate", "cert", false)}
                ${copy_btn("Private Key", "key", !has_key)}
                ${copy_btn("Fullchain", "fullchain", false)}
                ${copy_btn("CA Chain", "ca", !has_ca)}
                ${copy_btn("CSR", "csr", !has_csr)}
            </div>
        </div>`;

        frm.fields_dict.downloads_html.$wrapper.html(html);

        // Download handlers
        frm.fields_dict.downloads_html.$wrapper.find("button[data-format]:not(.copy-btn):not(:disabled)").on("click", function () {
            const format_type = $(this).data("format");
            frappe.call({
                method: "msp.msp.doctype.ssl_certificate.ssl_certificate.get_certificate_pem",
                args: { name: frm.doc.name, format_type },
                callback(r) {
                    if (r.message) {
                        const blob = new Blob([r.message.content], { type: "application/x-pem-file" });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = r.message.filename;
                        a.click();
                        URL.revokeObjectURL(url);
                        frappe.show_alert({ message: `${r.message.filename} heruntergeladen`, indicator: "green" });
                    }
                },
            });
        });

        // Copy handlers
        frm.fields_dict.downloads_html.$wrapper.find(".copy-btn:not(:disabled)").on("click", function () {
            const format_type = $(this).data("format");
            const btn_el = $(this);
            frappe.call({
                method: "msp.msp.doctype.ssl_certificate.ssl_certificate.get_certificate_pem",
                args: { name: frm.doc.name, format_type },
                callback(r) {
                    if (r.message) {
                        copy_to_clipboard(r.message.content).then(() => {
                            const orig = btn_el.html();
                            btn_el.html('<i class="fa fa-check"></i> Copied!');
                            setTimeout(() => btn_el.html(orig), 2000);
                            frappe.show_alert({ message: "In Zwischenablage kopiert", indicator: "green" });
                        });
                    }
                },
            });
        });
    },
});
