from this import d
from erpnext.stock.doctype import item
import frappe
import re


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
def get_epc_inline(name, iban, amount, text, color_dark=None, scale=None):
    from segno import helpers
    settings = frappe.get_single("MSP Settings")
    #determinate color
    if color_dark:
        m = re.match("(#\d{3}|#\d{6})", color_dark)
        if m:
            color_dark = m[1]
    else:
        if settings.qr_code_dark_color:
            color_dark = settings.qr_code_dark_color
        else:
            color_dark = "#333A3F"
    #determinate Scale
    if not scale:
        scale = settings.qr_code_scale if settings.qr_code_scale else 1

    qrcode = helpers.make_epc_qr(
        name=name,
        iban=iban,
        amount=amount,
        text=text)
    return qrcode.svg_inline(dark=color_dark, scale=scale)

@frappe.whitelist()
def get_qr_code_inline(data, color_dark=None, scale=None):
    import segno
    settings = frappe.get_single("MSP Settings")
    #determinate color
    if color_dark:
        m = re.match("(#\d{3}|#\d{6})", color_dark)
        if m:
            color_dark = m[1]
    else:
        if settings.qr_code_dark_color:
            color_dark = settings.qr_code_dark_color
        else:
            color_dark = "#333A3F"
    #determinate Scale
    if not scale:
        scale = settings.qr_code_scale if settings.qr_code_scale else 1
    scale = float(scale)
    qrcode = segno.make(data)
    return qrcode.svg_inline(dark=color_dark, scale=scale)

