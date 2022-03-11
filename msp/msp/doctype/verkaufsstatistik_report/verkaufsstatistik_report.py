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
						artikel_details = [si["posting_date"],empl,artikel.item_name,artikel.item_code,artikel.qty,artikel.rate]
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
						artikel_details = [dn["posting_date"],empl,artikel.item_name,artikel.item_code,artikel.qty, artikel.rate]
						item_list.append(artikel_details)
		
		
		df = pd.DataFrame(item_list, columns = ["Datum","Mitarbeiter","Item Name","Item","Anzahl","Preis"])
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
			filters = filters +["Item","Item Name","Preis"]
		if self.gruppiert_nach == "Mitarbeiter":
			filters.append("Mitarbeiter")
		#df_grouped = df.groupby(filters).agg({'Anzahl': ['sum']}).reset_index()
		df_grouped = df.groupby(filters)['Anzahl'].sum().to_frame('Anzahl').reset_index()
		self.report_ausgabe = self.get_styler(df_grouped).render()
                            
		if item_list == []:
			self.report_ausgabe = '<p>' + ("Für die angegebene Periode sind keine Daten vorhanden") + '</p>'
	
	def get_styler(self,df):	
		styles = [
        dict(props=[("border-collapse", "collapse"), ("width", "100%")]),
        dict(selector="th, td", props=[("padding", ".75rem"), ("border-top", "1px solid #dee2e6")]),
        dict(selector=".col_heading", props=[('text-align', 'right')]),
        #dict(selector=".col_heading.col0", props=[('text-align', 'left')]),
        dict(selector=".data", props=[("text-align", "right")]),
        dict(selector=".col0", props=[("text-align", "left")]), # first column
        dict(selector="tbody tr:nth-of-type(odd)", props=[("background-color", "rgba(0,0,0,.05)")]), # stripes
		]
		return df.style.hide_index().format({"Anzahl":'{:.2f}', "Preis":'{:.2f}'}).set_table_styles(styles)