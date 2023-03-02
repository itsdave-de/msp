import frappe
import json

@frappe.whitelist()
def checklist_fetch_from_template(values, name):

    values_dict = json.loads(values) 
    template = values_dict["template"]

    template_doc = frappe.get_doc("IT Checklist Template", template)
    it_checklist_doc = frappe.get_doc("IT Checklist", name)

    it_checklist_doc = get_recursive_items(template_doc, it_checklist_doc)
   
    it_checklist_doc.save()


def get_recursive_items(template_doc, it_checklist_doc):
    if template_doc.depends_on:
        rec_template_doc = frappe.get_doc("IT Checklist Template", template_doc.depends_on)
        it_checklist_doc = get_recursive_items(rec_template_doc, it_checklist_doc)

    for element in template_doc.elements:
        current_chekclist_element_doc = frappe.get_doc({
            "doctype": "IT Checklist Element",
            "title": element.title,
            "type": element.type,
            "description": element.description
        })
        it_checklist_doc.append("it_checklist_elements", current_chekclist_element_doc)
    return it_checklist_doc
    