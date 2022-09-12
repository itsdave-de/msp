frappe.ui.form.on('Location', {
    refresh(frm) {
        frm.add_custom_button('Show IT Objects in Location', () => {
            frappe.set_route('List', 'IT Object', { location_full_path: ['like', `%${frm.doc.location_name}%`] })
        })
    }
});
