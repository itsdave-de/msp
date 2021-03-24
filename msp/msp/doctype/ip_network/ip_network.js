// Copyright (c) 2021, itsdave GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on('IP Network', {

	refresh(frm) {
		frm.add_custom_button('Calculate Network Data', function(){
			frappe.call({ 
				method: 'msp.msp.doctype.ip_network.ip_network.calculate_network_data', 
				args: { doc: frm.doc.name },
				callback:function(r){
					console.log(r.message)
					frm.reload_doc()
				}
			})
		})
	}
});
