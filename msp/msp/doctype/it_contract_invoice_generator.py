import frappe
from frappe.model.document import Document
from erpnext.accounts.party import set_taxes as party_st
from datetime import datetime

@frappe.whitelist()
def get_invoices(doc):
    contract_list = frappe.get_all("IT Contract", filter ={"status":"active"})
    for contr in contract_list:
        contract= frappe.get_doc("IT Contract",contr.name)
        billing_month = doc.billing_month
        customer = contract.customer
        items = contract.items
        introduction = "Lestungszeitraum " + billing_month
        title = contract.it_contract_type + billing_month + contract.customer_name
        inv_title_list = frappe.get_all("Invoice", filters = {"title":title})
        if len(inv_title_list) > 0:
            invoice_items = [create_invoice_doc_item(el) for el in items]
            invoice_doc = create_invoice(doc,customer,invoice_items,title, introduction)

def create_invoice_doc_item(self, item):
    #Funktion kreiert Invoice Item aus den gegebenen IT Contract Items
    invoice_doc_item = frappe.get_doc({
                    "doctype": "Sales Invoice Item",
                    "item_code": item.item_code,
                    "description": item.item_name,
                    "qty": item.qty,
                    "uom" : "Stk",
                    "rate": item.rate,
                    
                    })
    return invoice_doc_item

def create_invoice(self,cust,invoice_doc_items,title, introduction):
    invoice_doc = frappe.get_doc({ 
            "doctype": "Sales Invoice", 
            "title": title,
            "customer": cust,
            "company": frappe.get_doc("Global Defaults").default_company,
            "items": invoice_doc_items,
            "introduction_text":introduction
            }) 
    if len(invoice_doc_items)>0:
        
        settings_doc = frappe.get_single("Auto Invoice Generator Settings")
        customer_doc = frappe.get_doc("Customer", cust )
    
        if customer_doc.payment_terms:
            invoice_doc.payment_terms_template = customer_doc.payment_terms
        else:
            invoice_doc.payment_terms_template = settings_doc.payment_terms_template
        invoice_doc.tc_name = settings_doc.tc_name
        tac_doc = frappe.get_doc("Terms and Conditions", settings_doc.tc_name)
        invoice_doc.terms = tac_doc.terms

        invoice_doc.taxes_and_charges = party_st(invoice_doc.customer, "Customer", invoice_doc.posting_date, invoice_doc.company)
        taxes = frappe.get_doc("Sales Taxes and Charges Template", settings_doc.taxes_and_charges).taxes

        for tax in taxes:
            new_tax = frappe.get_doc({
                    "doctype": "Sales Taxes and Charges",
                    "charge_type": tax.charge_type,
                    "account_head": tax.account_head,
                    "rate": tax.rate,
                    "description": tax.description
                })
        invoice_doc.append("taxes", new_tax)
        invoice_doc.save()
