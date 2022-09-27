import frappe
from frappe.utils import cstr

def build_full_location_path(doctype, method=None):
    parent_location_name = doctype.parent_location
    full_path = ''
    html_full_path = ''
    has_parent_location = True if parent_location_name else False

    while has_parent_location:
        result = frappe.db.get_value('Location', {'name': parent_location_name}, ['name', 'location_name', 'parent_location'], as_dict=True)
        if not result:
            has_parent_location = False
            continue

        full_path = f"{result['location_name']} --> {full_path}"
        html_full_path = f"<a href='http://{cstr(frappe.local.site)}/app/location/{result['name']}' target='_blank'>{result['location_name']}</a> --> {html_full_path}"
        parent_location_name = result['parent_location']

        if not parent_location_name:
            has_parent_location = False

    full_path = f"{full_path} {doctype.location_name}" if full_path != '' else doctype.location_name
    html_full_path = f"{html_full_path} <a href='http://{cstr(frappe.local.site)}/app/location/{doctype.name}' target='_blank'>{doctype.location_name}</a>" if html_full_path != '' else f"<a href='{doctype.name}'>{doctype.location_name}</a>"

    doctype.full_path = full_path
    doctype.html_full_path = html_full_path
