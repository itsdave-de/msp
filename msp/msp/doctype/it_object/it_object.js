// Copyright (c) 2021, itsdave GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on('IT Object', {
	refresh: function(frm) {
		if (frm.doc.admin_interface_link) {
			frm.add_custom_button('Open Admin Interface', () => frm.trigger('open_admin_interface'), 'Actions');
		};
		if (frm.doc.monitoring_link) {
			frm.add_custom_button('Open Monitoring', () => frm.trigger('open_monitoring'), 'Actions');
		};
	},
	open_admin_interface: function(frm) {
		window.open(frm.doc.admin_interface_link, '_blank').focus();
	},
	open_monitoring: function(frm) {
		window.open(frm.doc.monitoring_link, '_blank').focus();
	},
	
});
