from erpnext.stock.doctype import item
import frappe


def set_item_group_warehouse():
    pass

def get_item_goups_without_default_warehouse():
    igs = frappe.db.sql("""
    select 
        ig.name, 
        id.default_warehouse 
    from `tabItem Group` ig 
    left join `tabItem Default` id on id.parent = ig.name 
    where id.default_warehouse IS NULL;
    """)
    print(igs)

def get_item_group_for_item(item):
    pass


@frappe.whitelist()
def get_item_price_for_label(item_code):
    pl = frappe.db.get_single_value("Selling Settings", "selling_price_list")
    sp = frappe.get_all("Item Price", filters={"price_list": pl, "item_code": item_code, "selling": 1}, fields=["name", "price_list_rate"])
    if len(sp) == 1:

        amount =  sp[0]["price_list_rate"]
        if amount == 0:
            return
        thousands_separator = "."
        fractional_separator = ","
        currency = "{:,.2f} €".format(amount)

        if thousands_separator == ".":
            main_currency, fractional_currency = currency.split(".")[0], currency.split(".")[1]
            new_main_currency = main_currency.replace(",", ".")
            currency = new_main_currency + fractional_separator + fractional_currency

        return currency
    else:
        return
    
@frappe.whitelist()
def get_warehouse_for_label(item_code):
    return

@frappe.whitelist()
def get_qr_code(data, format=None):
    import segno
    

