# Copyright (c) 2022, itsdave GmbH and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
from doctest import debug
import frappe
from frappe.model.document import Document
from erpnext.accounts.party import set_taxes as party_st
from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice
from datetime import datetime
from frappe import ValidationError, _

class AutoInvoiceGenerator(Document):

	@frappe.whitelist()
	def close_invoiced_delivery_notes(self):
		dns = frappe.get_all("Delivery Note", filters={"status": "To Bill"})
		print(len(dns))
		dns_to_close = []

		for el in dns:
			try:
				make_sales_invoice(el["name"])
			except ValidationError as e:
				if str(e) == _("All these items have already been Invoiced/Returned"):
					print(_("All these items have already been Invoiced/Returned") + " in: " +  el["name"])
					dns_to_close.append(el["name"])
		count = 0
		print(dns_to_close)
		for pos in dns_to_close:
			count +=1
			frappe.db.set_value("Delivery Note", pos, "status", "Closed")
		frappe.msgprint( str(count)+ " delivery notes were closed")

	@frappe.whitelist()
	def get_delivery_notes_for_invoicing(self): 

	#Funktion soll eine Liste aller Lieferscheine zurückgeben die abzurechnen sind 
		filters = {"status" : "to bill","is_return": 0, "project": "", "blocked_for_billing": 0 }
		#filters = {"status" : "to bill","is_return": 0, "project": ""}
		delivery_notes_list = frappe.get_all("Delivery Note", filters = filters, fields = ["name", "customer", "project"]) 
		print(len(delivery_notes_list))
		dl = [x.name for x in delivery_notes_list if x.project]
		print(dl)		
		print(len(dl))
	
		return delivery_notes_list 
	@frappe.whitelist()
	def get_customer_for_invoicing(self, delivery_note): 

	#Funktion erstellt eine Liste von Kunden für die Rechnungen erstellt werden sollen 

		delivery_notes = self.get_delivery_notes_for_invoicing() 

		customer_list = [x.customer for x in delivery_notes] 

		customer_list_exc_duplicate = list(set(customer_list)) 
		#print(customer_list_exc_duplicate)

		return customer_list_exc_duplicate 

	def get_delivery_notes_for_customer(self, cust, delivery_notes): 

#Funktion listet alle Lieferscheine für den jeweiligen Kunden auf 
		cust_del_note = [] 

		for el in delivery_notes: 

			if el["customer"] == cust: 
				cust_del_note.append(el) 

		return cust_del_note 
	@frappe.whitelist()
	def get_invoice_dict(self): 


		del_not = self.get_delivery_notes_for_invoicing()
		print(del_not) 
		cust_list = self.get_customer_for_invoicing(del_not)
		if self.customer: 
			customer_list = [self.customer]
		else:
			customer_list = cust_list
		
		print(len(customer_list))
		cust_count = 0
		invoice_count = 0
		for cust in customer_list:
			print(cust)
			cust_doc = frappe.get_doc("Customer",cust)
			invoice_in_draft = frappe.get_all("Sales Invoice", filters = {"status" : "Draft", "customer": cust})
			if len(invoice_in_draft) > 0:
				print("nicht bearbeitet")
				print(cust)
				continue
			else:
				cust_count += 1
				#if self.invoicing_grouped_by == "None":
				
				delivery_note_list = self.get_delivery_notes_for_customer(cust,del_not) 
				#print(delivery_note_list)
				if len(delivery_note_list) < 1:
					frappe.msgprint("Keine abrechnenbaren Lieferscheine vorhanden")
				sales_order_items = []
				service_items = []
				goods_items =[]
				for dn in delivery_note_list: 

					item_doc = frappe.get_doc("Delivery Note", dn["name"]) 

					for item in item_doc.items: 
						print(item.item_group)
						invoice_doc_item = frappe.get_doc({
							"doctype": "Sales Invoice Item",
							"item_code": item.item_code,
							"description": item.description,
							"qty": item.qty,
							"uom" : item.uom,
							"rate": item.rate,
							"sales_order": item.against_sales_order,
							"dn_detail": item.name,
							"parent": "delivery_note",
							"delivery_note": dn["name"]

							})
						print(item.dn_detail)
						print(dn["name"])
						print(item.qty)
						print(item.uom)
						if item.item_group == "Dienstleistungen" or item.item_group == "Anfahrten" or item.item_group == "Arbeitszeiten Techniker" or item.item_group == "Anwendungsentwicklung":
							service_items.append(invoice_doc_item)
						elif item.against_sales_order:
							sales_order_items.append(invoice_doc_item)
						else:
							goods_items.append(invoice_doc_item)
				
			if self.invoicing_grouped_by == "Service and Goods and Sales Order":
				self.create_invoice(cust, goods_items, "Ware " + cust_doc.customer_name)
				if len(goods_items) > 0:
					invoice_count += 1
				self.create_invoice(cust, service_items, "Dienstleistung " + cust_doc.customer_name)
				if len(service_items) > 0:	
					invoice_count += 1
				#self.create_invoice(cust, sales_order_items, "Sales Order " + cust_doc.customer_name)	
				if len(sales_order_items) > 0:
					print("Sales Order Check")
					x = [i.sales_order for i in sales_order_items]
					print(x)
					a = list(set(x))
					for el in a:
						sal_ord_it = []
						for i in sales_order_items:
							if i.sales_order == el:
								sal_ord_it.append(i)
						self.create_invoice(cust, sal_ord_it, "Sales Order "+ el+ " " + cust_doc.customer_name)
						invoice_count += 1
			elif self.invoicing_grouped_by == "Service and Goods":
				invoice_item = sales_order_items + goods_items
				self.create_invoice(cust, invoice_item, "Ware " + cust_doc.customer_name)
				if len(invoice_item) > 0:
					invoice_count += 1
				self.create_invoice(cust, service_items, "Dienstleistung " + cust_doc.customer_name)
				if len(service_items) >0:
					invoice_count += 1
			else: 
				invoice_item = sales_order_items + service_items + goods_items
				self.create_invoice(cust, invoice_item, "Dienstleistung und Ware  "+ cust_doc.customer_name)
				if len(invoice_item) > 0:
					invoice_count += 1
		frappe.msgprint("Für " + str(cust_count)+ " Kunden wurden " + str(invoice_count) + " Rechnungen erstellt.")
		self.date = datetime.today().strftime('%Y-%m-%d')
		self.invoice_count = invoice_count
		self.customer_count = cust_count
	def create_invoice(self,cust,invoice_doc_items,title):
		invoice_doc = frappe.get_doc({ 
				"doctype": "Sales Invoice", 
				"title": title,
				"customer": cust,
				"company": frappe.get_doc("Global Defaults").default_company,
				"items": invoice_doc_items
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

	
