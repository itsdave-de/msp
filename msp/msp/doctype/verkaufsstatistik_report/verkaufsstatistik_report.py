# Copyright (c) 2021, itsdave GmbH and contributors
# For license information, please see license.txt


from frappe.model.document import Document
from os import replace
import frappe
from datetime import datetime as dt
from pprint import pprint
import pandas as pd


class VerkaufsstatistikReport(Document):
	@frappe.whitelist()
	def do_report(self):
		artikel_auswahl = self.artikel
		artikel_name = [a.item for a in artikel_auswahl]
		if self.report_basierend_auf == "Rechnung":
			item_list = []
			si_list = frappe.get_all(
						"Sales Invoice", 
						filters = {
							"docstatus": 1,
							"posting_date": ["between", [self.from_date, self.to_date]]
							},
						fields = ["posting_date", "name"]
						)
			for si in si_list:			
				artikel_doc = frappe.get_doc("Sales Invoice", si["name"])
				for artikel in artikel_doc.items:
					if artikel.item_code in artikel_name:
						empl = str(artikel.item_name).replace("Arbeitszeit ","").replace("Herr ","").replace(" Anwendungsentwicklung","").replace("Remote-Service ","")
						artikel_details = [si["posting_date"],empl,artikel.item_name,artikel.item_code,artikel.qty]
						item_list.append(artikel_details)
	
		if self.report_basierend_auf == "Lieferschein":	
			item_list = []
			dn_list = frappe.get_all(
						"Delivery Note", 
						filters = {
							"docstatus": 1,
							"posting_date": ["between", [self.from_date, self.to_date]]
							},
						fields = ["posting_date", "name"]
						)		
			for dn in dn_list:			
				artikel_doc = frappe.get_doc("Delivery Note", dn["name"])
				
				for artikel in artikel_doc.items:
					if artikel.item_code in artikel_name:
						empl = str(artikel.item_name).replace("Arbeitszeit ","").replace("Herr ","").replace(" Anwendungsentwicklung","").replace("Remote-Service ","")
						artikel_details = [dn["posting_date"],empl,artikel.item_name,artikel.item_code,artikel.qty]
						item_list.append(artikel_details)
		
		
		df = pd.DataFrame(item_list, columns = ["Datum","Mitarbeiter","Item Name","Item","Anzahl"])
		df['Datum'] = pd.to_datetime(df['Datum'])
		df['Kalenderwoche']= df['Datum'].dt.isocalendar().week 
		df['Monat']= df['Datum'].dt.month
		df['Jahr'] = df['Datum'].dt.year
		
		
		if self.resolution == 'monthly':
			filters = ['Jahr','Monat']
				
		elif self.resolution == 'weekly':
			filters =['Jahr','Kalenderwoche']
			
		elif self.resolution == 'daily':
			filters = ['Datum']
			
		elif self.resolution == 'yearly':
			filters = ["Jahr"]
			
		elif self.resolution == 'period':
			filters = []

		else:
			frappe.msgprint("Bitte Zeiteinheit für Gruppierung auswählen")

		if self.gruppiert_nach == "Artikel":
			filters = filters +["Item","Item Name"]
		if self.gruppiert_nach == "Mitarbeiter":
			filters.append("Mitarbeiter")
		df_grouped = df.groupby(filters).agg({'Anzahl': ['sum']}).reset_index()

		html = df_grouped.to_html(header = False,index = False)
		#html_2 = html.replace('<tr>','<tr style="text-align: center;">')
		self.report_ausgabe = html
                            
		if item_list == []:
			self.report_ausgabe = '<p>' + ("Für die angegebene Periode sind keine Daten vorhanden") + '</p>'
