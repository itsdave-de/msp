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
	}
});

