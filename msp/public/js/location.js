frappe.ui.form.on('Location', {
    refresh(frm) {
        frm.add_custom_button('Show IT Objects in Location', () => {
            frm.call('get_all_child_locations_from_location',{})
                .then((response) => {
                    frappe.set_route('List', 'IT Object', { location: ['in', `${response.message.toString()}`] })
                })
        })
    }
});
