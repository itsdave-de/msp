// Copyright (c) 2021, itsdave GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on('IT Checklist', {
	refresh: function(frm) {
		add_my_buttons(frm)
	}
});


var add_my_buttons = function(frm) {

    if (!frm.is_new()) {
   
        frm.add_custom_button('fetch from Template', function(){
            frm.save()
            frappe.prompt([
                {'fieldname': 'template', 'fieldtype': 'Link', 'label': 'Vorlage', 'reqd': 1, 'options': 'IT Checklist Template'},
                ],
            function(values){
                frappe.call({ 
                    method: 'msp.tools.checklist_fetch_from_template', 
                    args: { values: values, name: frm.doc.name },
                    callback:function(r){
                        console.log(r.message)
                        frm.reload_doc()
                    }
                })},
            'Artikel aus Vorlage hinzufügen',
            'Artikel hinzufügen',
            )

        });
	}
}