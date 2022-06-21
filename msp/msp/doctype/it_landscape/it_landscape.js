// Copyright (c) 2021, itsdave GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on('IT Landscape', {
	refresh: function(frm) {
			frm.add_custom_button('Copy SSH Keys', () => frm.trigger('copy_ssh_keys'), 'Actions');
			if (frm.doc.ticket_system_link) {
				frm.add_custom_button('Open Ticket System', () => frm.trigger('open_ticket_system'), 'Actions');
			};
			if (frm.doc.monitoring_link) {
				frm.add_custom_button('Open Monitoring', () => frm.trigger('open_monitoring'), 'Actions');
			}
		},
	open_ticket_system: function(frm) {
		window.open(frm.doc.ticket_system_link, '_blank').focus();
	},
	open_monitoring: function(frm) {
		window.open(frm.doc.monitoring_link, '_blank').focus();
	},

	copy_ssh_keys: function(frm) {
		frappe.call({
				"method": "msp.whitelisted_tools.get_ssh_keys_for_landscape",
				args: {
					"landscape": frm.doc.name,					
				},
				callback: (response) => {
					if (response.message.startsWith("#")) {
						console.log(response.message),
						frm.events.CopyToClipboard(response.message),
						frappe.msgprint(__('Keys copied to clipboard.'))
					}
					else {
						frappe.msgprint(__(response.message));
					}
					
				} 
	
		})
	},
	CopyToClipboard: function(value) {
			var tempInput = document.createElement("textarea");
			tempInput.value = value;
			document.body.appendChild(tempInput);
			tempInput.select();
			document.execCommand("copy");
			document.body.removeChild(tempInput);
	}
})
