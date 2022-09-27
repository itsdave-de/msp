
import frappe
from pprint import pprint

#ssigss = Sales Invoice Item Group Separation


def get_sales_invoice_item_group_separation(customer):
    #check, that we have exactly one Sales Invoice Item Group Separation Entry for this customer, and return it Parent Name
    ssigss = frappe.get_all(
        "Sales Invoice Item Group Separation Customer",
        filters={"customer": customer},
        fields=["name", "parent"])
    if not ssigss:
        frappe.throw("No Sales Invoice Item Group Separation Customer.")
    if len(ssigss) > 1:
        frappe.throw("More then one Sales Invoice Item Group Separation Customer.")
    return ssigss[0]["parent"]


def get_item_group_separation_dict(ssigs):
    """get item groups to concider from ssigss, should return something like:
            {1: {'filter': ['Anwendungsentwicklung'],
            'idx': 1,
            'item_group': 'Anwendungsentwicklung',
            'recursive': 0},
            2: {'filter': ['Dienstleistungen',
                        'Zuschläge',
                        'Anwendungsentwicklung',
                        'Arbeitszeiten Techniker'],
            'idx': 2,
            'item_group': 'Dienstleistungen',
            'recursive': 1}}
    """
    item_group_separation_dict = frappe.get_all(
        "Sales Invoice Item Group Separation Entry",
        filters={"parent": ssigs},
        fields=["idx", "item_group", "recursive"],
        order_by="idx")
    ordered_filters_dict = {}

    for item_group_separation in item_group_separation_dict:
        ordered_filters_dict[item_group_separation["idx"]] = item_group_separation
        if item_group_separation["recursive"]:
            ordered_filters_dict[item_group_separation["idx"]]["filter"] = search_child_item_groups(item_group_separation["item_group"])
        else:
            ordered_filters_dict[item_group_separation["idx"]]["filter"] = [item_group_separation["item_group"]]

    return ordered_filters_dict


def search_child_item_groups(item_group, item_groups_to_filter = None):
    #get all child item groups, return list with childs and parent
    if not item_groups_to_filter:
        item_groups_to_filter = []

    item_groups_to_filter.append(item_group)
    
    child_locations = frappe.get_all(
        "Item Group", 
        filters = {"parent_item_group": item_group})

    if child_locations:
        for child_location in child_locations:
            search_child_item_groups(child_location['name'], item_groups_to_filter)

    return item_groups_to_filter

def get_item_group_assignment_table(customer):
    ssigs = get_sales_invoice_item_group_separation(customer)
    item_group_separation_dict = get_item_group_separation_dict(ssigs)
    return item_group_separation_dict
# for idx in range(1, len(item_group_separation_dict) + 1):
#     print("prüfe artikel auf prio " + str(idx))
#     print(item_group_separation_dict[idx])
        


