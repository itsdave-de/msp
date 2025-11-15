// Copyright (c) 2023, itsdave GmbH and contributors
// For license information, please see license.txt


frappe.ui.form.on('MSP Documentation', {
	refresh(frm) {
            frm.add_custom_button('1. Get Tactical Agents', function(){
                frappe.dom.freeze('Fetching Tactical Agents...');
                frappe.call({ 
                    method: 'msp.tactical-rmm.get_agents_pretty', 
                    args: { documentation: frm.doc.name },
                    callback: function(r) {
                        frappe.dom.unfreeze();
                        if (r.exc) {
                            frappe.msgprint({
                                title: __('Error'),
                                indicator: 'red',
                                message: __('Failed to fetch tactical agents. Please try again.')
                            });
                            return;
                        }
                        frappe.show_alert({
                            message: __('Successfully fetched tactical agents'),
                            indicator: 'green'
                        });
                        frm.reload_doc();
                    }
                });
            }, 'Workflow');

            frm.add_custom_button('2. Office Search', function(){
                frappe.dom.freeze('Searching for Office installations...');
                frappe.call({ 
                    method: 'msp.tactical-rmm.search_office', 
                    args: { documentation: frm.doc.name },
                    callback: function(r) {
                        frappe.dom.unfreeze();
                        if (r.exc) {
                            frappe.msgprint({
                                title: __('Error'),
                                indicator: 'red',
                                message: __('Failed to complete Office search. Please try again.')
                            });
                            return;
                        }
                        frappe.show_alert({
                            message: __('Office search completed'),
                            indicator: 'green'
                        });
                        frm.reload_doc();
                    }
                });
            }, 'Workflow');

            // Add new button for IT Objects documentation
            frm.add_custom_button('3. Generate IT Objects', function(){
                frappe.dom.freeze('Generating IT Objects documentation...');
                frappe.call({ 
                    method: 'msp.tools.get_documentation_html',
                    args: { 
                        it_landscape: frm.doc.landscape 
                    },
                    callback: function(r) {
                        frappe.dom.unfreeze();
                        if (r.exc) {
                            frappe.msgprint({
                                title: __('Error'),
                                indicator: 'red',
                                message: __('Failed to generate IT Objects documentation. Please try again.')
                            });
                            return;
                        }
                        if (r.message) {
                            frm.set_value('it_objects', r.message);
                            frm.save().then(() => {
                                frappe.show_alert({
                                    message: __('IT Objects documentation generated successfully'),
                                    indicator: 'green'
                                });
                            });
                        }
                    }
                });
            }, 'Workflow');

            // Add button to fetch and store all RMM agent data as JSON
            frm.add_custom_button('4. RMM Daten speichern', function(){
                frappe.dom.freeze('RMM-Daten werden abgerufen und gespeichert...');
                frappe.call({ 
                    method: 'msp.tactical-rmm.fetch_and_store_all_agent_data',
                    args: { 
                        documentation_name: frm.doc.name 
                    },
                    callback: function(r) {
                        frappe.dom.unfreeze();
                        if (r.exc) {
                            frappe.msgprint({
                                title: __('Fehler'),
                                indicator: 'red',
                                message: __('RMM-Daten konnten nicht gespeichert werden. Bitte versuchen Sie es erneut.')
                            });
                            return;
                        }
                        if (r.message && r.message.success) {
                            frappe.show_alert({
                                message: r.message.message || __('RMM-Daten erfolgreich gespeichert'),
                                indicator: 'green'
                            });
                            frm.reload_doc();
                        }
                    }
                });
            }, 'Workflow');

            // Add button to fetch and store Active Directory computer data as JSON
            frm.add_custom_button('5. AD Computer-Daten speichern', function(){
                frappe.dom.freeze('AD-Computer-Daten werden abgerufen und gespeichert...');
                frappe.call({ 
                    method: 'msp.tactical-rmm.fetch_and_store_ad_computer_data',
                    args: { 
                        documentation_name: frm.doc.name 
                    },
                    callback: function(r) {
                        frappe.dom.unfreeze();
                        if (r.exc) {
                            frappe.msgprint({
                                title: __('Fehler'),
                                indicator: 'red',
                                message: __('AD-Computer-Daten konnten nicht gespeichert werden. Bitte versuchen Sie es erneut.')
                            });
                            return;
                        }
                        if (r.message && r.message.success) {
                            frappe.show_alert({
                                message: r.message.message || __('AD-Computer-Daten erfolgreich gespeichert'),
                                indicator: 'green'
                            });
                            frm.reload_doc();
                        }
                    }
                });
            }, 'Workflow');

            // Add button to fetch and store Active Directory user data as JSON
            frm.add_custom_button('6. AD Benutzer-Daten speichern', function(){
                frappe.dom.freeze('AD-Benutzer-Daten werden abgerufen und gespeichert...');
                frappe.call({ 
                    method: 'msp.tactical-rmm.fetch_and_store_ad_user_data',
                    args: { 
                        documentation_name: frm.doc.name 
                    },
                    callback: function(r) {
                        frappe.dom.unfreeze();
                        if (r.exc) {
                            frappe.msgprint({
                                title: __('Fehler'),
                                indicator: 'red',
                                message: __('AD-Benutzer-Daten konnten nicht gespeichert werden. Bitte versuchen Sie es erneut.')
                            });
                            return;
                        }
                        if (r.message && r.message.success) {
                            frappe.show_alert({
                                message: r.message.message || __('AD-Benutzer-Daten erfolgreich gespeichert'),
                                indicator: 'green'
                            });
                            frm.reload_doc();
                        }
                    }
                });
            }, 'Workflow');

            // Add button to compare RMM and AD data
            frm.add_custom_button('7. RMM ↔ AD Abgleich', function(){
                frappe.dom.freeze('RMM- und AD-Daten werden abgeglichen...');
                frappe.call({ 
                    method: 'msp.tactical-rmm.compare_rmm_and_ad_data',
                    args: { 
                        documentation_name: frm.doc.name 
                    },
                    callback: function(r) {
                        frappe.dom.unfreeze();
                        if (r.exc) {
                            frappe.msgprint({
                                title: __('Fehler'),
                                indicator: 'red',
                                message: __('Datenabgleich konnte nicht durchgeführt werden. Bitte versuchen Sie es erneut.')
                            });
                            return;
                        }
                        if (r.message && r.message.success) {
                            let stats = r.message.stats;
                            let details = `${stats.total_computers} Computer analysiert: ` +
                                        `${stats.in_both} in beiden Systemen, ` +
                                        `${stats.only_in_rmm} nur RMM, ` +
                                        `${stats.only_in_ad} nur AD`;
                            
                            frappe.show_alert({
                                message: __('Datenabgleich erfolgreich abgeschlossen. ') + details,
                                indicator: 'green'
                            });
                            frm.reload_doc();
                        }
                    }
                });
            }, 'Workflow');

            // Add button for Windows 11 compatibility check
            frm.add_custom_button('8. Windows 11 Check', function(){
                frappe.dom.freeze('Windows 11 CPU-Kompatibilität wird geprüft...');
                frappe.call({ 
                    method: 'msp.tactical-rmm.check_windows11_compatibility',
                    args: { 
                        documentation_name: frm.doc.name 
                    },
                    callback: function(r) {
                        frappe.dom.unfreeze();
                        if (r.exc) {
                            frappe.msgprint({
                                title: __('Fehler'),
                                indicator: 'red',
                                message: __('Windows 11 Kompatibilitätsprüfung konnte nicht durchgeführt werden. Bitte versuchen Sie es erneut.')
                            });
                            return;
                        }
                        if (r.message && r.message.success) {
                            let stats = r.message.stats;
                            let details = `${stats.total_non_win11} Systeme ohne Windows 11 analysiert: ` +
                                        `${stats.compatible_cpus} kompatible CPUs, ` +
                                        `${stats.incompatible_cpus} inkompatible CPUs, ` +
                                        `${stats.unknown_cpus} unbekannte CPUs`;
                            
                            frappe.show_alert({
                                message: __('Windows 11 Kompatibilitätsprüfung abgeschlossen. ') + details,
                                indicator: 'green'
                            });
                            frm.reload_doc();
                        }
                    }
                });
            }, 'Workflow');

            // Add debug button for CPU compatibility
            frm.add_custom_button('🔍 CPU Debug', function(){
                frappe.prompt([
                    {
                        'fieldname': 'test_cpu',
                        'label': 'Test CPU (leer = automatisch)',
                        'fieldtype': 'Data',
                        'reqd': 0,
                        'description': 'Z.B: Intel(R) Core(TM) i3-8100 CPU @ 3.60GHz, 4C/4T'
                    }
                ], function(values) {
                    frappe.dom.freeze('CPU-Kompatibilität wird debuggt...');
                    frappe.call({ 
                        method: 'msp.tactical-rmm.debug_cpu_compatibility',
                        args: { 
                            documentation_name: frm.doc.name,
                            test_cpu_string: values.test_cpu || null
                        },
                        callback: function(r) {
                            frappe.dom.unfreeze();
                            if (r.exc) {
                                frappe.msgprint({
                                    title: __('Fehler'),
                                    indicator: 'red',
                                    message: __('CPU-Debug konnte nicht durchgeführt werden: ') + r.exc
                                });
                                return;
                            }
                            if (r.message && r.message.success) {
                                let debug_info = r.message.debug_info;
                                let result = r.message.result;
                                let test_cpu = r.message.test_cpu;
                                
                                // Debug-Dialog erstellen
                                let debug_html = `
                                    <div style="font-family: monospace; font-size: 12px;">
                                        <h4>🔍 CPU-Kompatibilitäts Debug</h4>
                                        <div><strong>Test-CPU:</strong> ${test_cpu}</div>
                                        <div><strong>System-CPU (uppercase):</strong> ${debug_info.system_cpu_upper || 'N/A'}</div>
                                        <div><strong>Vendor:</strong> ${debug_info.vendor || 'N/A'}</div>
                                        <div><strong>Suchset-Größe:</strong> ${debug_info.search_set_size || 0}</div>
                                        <div><strong>Ergebnis:</strong> <span style="color: ${result.compatible ? 'green' : 'red'}">
                                            ${result.compatible ? '✅ KOMPATIBEL' : '❌ NICHT KOMPATIBEL'} (${result.status})
                                        </span></div>
                                        ${debug_info.match_found ? `<div><strong>Gefundene CPU:</strong> ${debug_info.matching_cpu}</div>` : ''}
                                        
                                        <h5>📁 Dateipfad-Informationen:</h5>
                                        <div style="margin-bottom: 15px; padding: 10px; background: #f8f9fa; border-radius: 5px;">
                                            <div><strong>App-Pfad:</strong> ${debug_info.app_path || 'N/A'}</div>
                                            ${debug_info.files_info ? Object.keys(debug_info.files_info).map(vendor => {
                                                const info = debug_info.files_info[vendor];
                                                const statusColor = info.exists ? 'green' : 'red';
                                                const statusIcon = info.exists ? '✅' : '❌';
                                                return `
                                                    <div style="margin-top: 8px;">
                                                        <div><strong>${vendor.toUpperCase()} CPUs:</strong> ${statusIcon}</div>
                                                        <div style="font-size: 11px; color: #666; margin-left: 10px;">
                                                            Pfad: ${info.path}<br>
                                                            Existiert: <span style="color: ${statusColor}">${info.exists ? 'Ja' : 'Nein'}</span><br>
                                                            ${info.exists ? `Dateigröße: ${info.size} Bytes` : ''}
                                                        </div>
                                                    </div>
                                                `;
                                            }).join('') : 'Keine Dateipfad-Informationen verfügbar'}
                                            ${debug_info.loaded_counts ? `
                                                <div style="margin-top: 8px;">
                                                    <strong>Geladene CPUs:</strong> 
                                                    AMD: ${debug_info.loaded_counts.amd}, 
                                                    Intel: ${debug_info.loaded_counts.intel}
                                                </div>
                                            ` : ''}
                                            ${debug_info.error ? `
                                                <div style="color: red; margin-top: 8px;">
                                                    <strong>Fehler:</strong> ${debug_info.error}
                                                </div>
                                            ` : ''}
                                        </div>
                                        
                                        <h5>🔎 Vergleiche (erste ${debug_info.comparisons ? debug_info.comparisons.length : 0}):</h5>
                                        <div style="max-height: 400px; overflow-y: auto; border: 1px solid #ddd; padding: 10px;">
                                `;
                                
                                if (debug_info.comparisons) {
                                    debug_info.comparisons.forEach((comp, i) => {
                                        let color = comp.match_result ? 'green' : '#666';
                                        let icon = comp.match_result ? '✅' : '❌';
                                        debug_html += `
                                            <div style="margin-bottom: 8px; padding: 5px; border-left: 3px solid ${color};">
                                                <div><strong>${icon} ${comp.match_type}:</strong> ${comp.supported_cpu}</div>
                                                ${comp.extracted_part ? `<div><em>Extrahiert:</em> ${comp.extracted_part}</div>` : ''}
                                                <div><em>Details:</em> ${comp.details}</div>
                                            </div>
                                        `;
                                    });
                                }
                                
                                if (debug_info.truncated) {
                                    debug_html += '<div style="color: orange;"><em>... weitere Vergleiche abgeschnitten ...</em></div>';
                                }
                                
                                debug_html += `
                                        </div>
                                    </div>
                                `;
                                
                                frappe.msgprint({
                                    title: 'CPU-Kompatibilitäts Debug',
                                    message: debug_html,
                                    indicator: result.compatible ? 'green' : 'red'
                                });
                            }
                        }
                    });
                }, 'CPU Debug Test', 'Testen');
            }, 'Workflow');

            // Add Excel Export button
            frm.add_custom_button('📊 Excel Export', function(){
                frappe.dom.freeze('Excel-Export wird erstellt...');
                frappe.call({ 
                    method: 'msp.tactical-rmm.export_tables_to_excel',
                    args: { 
                        documentation_name: frm.doc.name 
                    },
                    callback: function(r) {
                        frappe.dom.unfreeze();
                        if (r.exc) {
                            frappe.msgprint({
                                title: __('Fehler'),
                                indicator: 'red',
                                message: __('Excel-Export konnte nicht erstellt werden: ') + r.exc
                            });
                            return;
                        }
                        if (r.message && r.message.success) {
                            let filename = r.message.filename;
                            let content = r.message.content;
                            
                            // Excel-Datei herunterladen
                            try {
                                // Base64 zu Blob konvertieren
                                const byteCharacters = atob(content);
                                const byteNumbers = new Array(byteCharacters.length);
                                for (let i = 0; i < byteCharacters.length; i++) {
                                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                                }
                                const byteArray = new Uint8Array(byteNumbers);
                                const blob = new Blob([byteArray], {
                                    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                                });
                                
                                // Download-Link erstellen
                                const url = window.URL.createObjectURL(blob);
                                const a = document.createElement('a');
                                const timestamp = new Date().toLocaleString('de-DE');
                                a.style.display = 'none';
                                a.href = url;
                                a.download = filename;
                                document.body.appendChild(a);
                                a.click();
                                window.URL.revokeObjectURL(url);
                                document.body.removeChild(a);
                                
                                frappe.show_alert({
                                    message: __('Excel-Export erfolgreich heruntergeladen: ') + filename,
                                    indicator: 'green'
                                });
                                
                            } catch (download_error) {
                                console.error('Download-Fehler:', download_error);
                                frappe.msgprint({
                                    title: __('Download-Fehler'),
                                    indicator: 'red',
                                    message: __('Die Excel-Datei konnte nicht heruntergeladen werden. Bitte versuchen Sie es erneut.')
                                });
                            }
                            
                        }
                    }
                });
            }, 'Export');
	}
});

