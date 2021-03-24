// Copyright (c) 2021, itsdave GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on('IT User Account', {
	refresh: function(frm) {
        frm.add_custom_button('Copy PW', () => frm.trigger('get_pw'));

    },
    get_pw: function(frm) {
        frm.call('copy_pw', {
            'user_agent': navigator.userAgent,
            'platform': navigator.platform,
        },
        (r) => {
			frm.events.CopyToClipboard(r.message)
        }
        );
    },
	CopyToClipboard: function(value) {
		var tempInput = document.createElement("input");
		tempInput.value = value;
		document.body.appendChild(tempInput);
		tempInput.select();
		document.execCommand("copy");
		document.body.removeChild(tempInput);
	},
	  



   
});
 
