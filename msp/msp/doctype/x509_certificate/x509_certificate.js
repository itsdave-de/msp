// Copyright (c) 2024, itsdave GmbH and Contributors
// For license information, please see license.txt


//-------------------------------------------------------------------------------------------------------------------------------
frappe.ui.form.on('x509_certificate', {
    after_save: function(frm) {
        loadCertificateInformation(frm);
    }
});

// Function to load certificate information
function loadCertificateInformation(frm) {
    frappe.call({
        method: 'msp.msp.doctype.x509_certificate.x509_certificate.read_cert_data',
        args: {
            certificate_name: frm.doc.name,
            doc: frm.doc
        },
        callback: function(response) {
            if (response.message) {
                if (response.message.error) {
                    if (response.message.error === 'Invalid certificate format') {
                        frappe.msgprint("Invalid Certificate Data");
                    } else {
                        frappe.msgprint(response.message.error);
                    }
                    return;
                }

                var parsedSubject = response.message.subject;
                var parsedIssuer = parseIssuerInfo(response.message.issuer);

                var certificateInfo = "<strong>Subject:</strong><br>" +
                                      "- <strong>Common Name:</strong> " + (parsedSubject.common_name || 'N/A') + "<br>" +
                                      "- <strong>Country:</strong> " + (parsedSubject.country || 'N/A') + "<br>" +
                                      "- <strong>State/Province:</strong> " + (parsedSubject.state || 'N/A') + "<br>" +
                                      "- <strong>City:</strong> " + (parsedSubject.city || 'N/A') + "<br>" +
                                      "- <strong>Organization:</strong> " + (parsedSubject.organization || 'N/A') + "<br>" +
                                      "- <strong>Organizational Unit:</strong> " + (parsedSubject.organization_unit || 'N/A') + "<br>" +
                                      "<strong>Issuer:</strong> " + (parsedIssuer.commonName || 'N/A') + "<br>" +
                                      "<strong>Subject Alternative Name:</strong> " + (response.message.subject_alt_names || 'N/A') + "<br>" +
                                      "<strong>Validity Period:</strong><br>" +
                                      "- <strong>Not Before:</strong> " + response.message.not_valid_before + "<br>" +
                                      "- <strong>Not After:</strong> " + response.message.not_valid_after + "<br>" +
                                      "<strong>Serial Number:</strong> " + response.message.serial_number;

                frappe.msgprint("Setting information field with: " + frm.doc.name + "<br>" + certificateInfo);
                frm.set_value('certificate_information', certificateInfo);

                // Check if private key is empty
                if (!frm.doc.private_key) {
                    frappe.msgprint("Private Key is empty");
                } else {
                    // Check if private key is valid
                    frappe.msgprint(response.message.private_key_valid ? "Private Key is correct" : "Private Key is not valid");
                }

                // Set the create_date and expiry_date fields
                frm.set_value('not_valid_before', response.message.not_valid_before);
                frm.set_value('not_valid_after', response.message.not_valid_after);

                // Refresh the form to show updated values
                frm.refresh_field('not_valid_before');
                frm.refresh_field('not_valid_after');
                frm.refresh_field('certificate_information');
            } else {
                frappe.msgprint("Can't fetch certificate information.");
            }
        }
    });
}

function parseSubjectInfo(subjectInfo) {
    if (subjectInfo) {
        // Regular expression to extract Common Name (CN) from subject
        var parenthesesPattern = /CN=([^,]+)/;
        var cnMatch = subjectInfo.match(parenthesesPattern);
        var commonName = cnMatch ? cnMatch[1] : null;
        return {
            commonName: commonName
        };
    }
    return null;
}

function parseIssuerInfo(issuerInfo) {
    if (issuerInfo) {
        var parenthesesPattern = /CN=([^,]+)/;
        var cnMatch = issuerInfo.match(parenthesesPattern);
        var commonName = cnMatch ? cnMatch[1] : null;
        return {
            commonName: commonName
        };
    }
    return null;
}

// Function to format Subject Alternative Name
function formatSubjectAltName(subjectAltName) {
    if (subjectAltName) {
        return subjectAltName !== 'No more' ? subjectAltName : 'No hay nombres alternativos';
    }
    return 'No hay nombres alternativos';
}