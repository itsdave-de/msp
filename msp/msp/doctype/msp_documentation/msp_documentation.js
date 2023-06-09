// Copyright (c) 2023, itsdave GmbH and contributors
// For license information, please see license.txt


frappe.ui.form.on('MSP Documentation', {
	refresh(frm) {
            frm.add_custom_button('1. Get Tactical Agents', function(){
                frappe.call({ 
                    method: 'msp.tactical-rmm.get_agents_pretty', 
                    args: { documentation: frm.doc.name },
                    callback:function(r){
                        console.log(r.message)
                        frm.reload_doc()
                    }
                });
            }, 'Workflow');
            frm.add_custom_button('2. office suche', function(){
                frappe.call({ 
                    method: 'msp.tactical-rmm.search_office', 
                    args: { documentation: frm.doc.name },
                    callback:function(r){
                        console.log(r.message)
                        frm.reload_doc()
                    }
                });
            }, 'Workflow');
	}
});

