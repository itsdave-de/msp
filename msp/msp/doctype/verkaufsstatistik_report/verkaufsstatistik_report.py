# Copyright (c) 2021, itsdave GmbH and contributors
# For license information, please see license.txt


from frappe.model.document import Document
from os import replace
import frappe
from datetime import datetime as dt
from pprint import pprint
import pandas as pd
import numpy as np
from retail.retail.doctype.flex_report.flex_report import pivot_table


class VerkaufsstatistikReport(Document):
	@frappe.whitelist()
	def do_report(self):
		artikel_auswahl = self.artikel
		if artikel_auswahl == []:
			frappe.throw('Keine Artikel ausgewählt.')
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
						price = artikel.qty*artikel.rate
						artikel_details = [si["posting_date"],empl,artikel.item_name,artikel.item_code,artikel.qty,artikel.rate, price]
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
						price = artikel.qty*artikel.rate
						artikel_details = [dn["posting_date"],empl,artikel.item_name,artikel.item_code,artikel.qty, artikel.rate, price]
						item_list.append(artikel_details)
				print(artikel_details)
		
		
		df = pd.DataFrame(item_list, columns = ["Datum","Mitarbeiter","Item Name","Item","Anzahl","Preis pro Einheit","Preis"])
		df['Datum'] = pd.to_datetime(df['Datum'])
		df['Kalenderwoche']= df['Datum'].dt.isocalendar().week
		#df['Monat']= df['Datum'].dt.month
		df['Jahr'] = df['Datum'].dt.year
		df['Monat'] = df['Datum'].dt.strftime("%m.%Y")
		
		df.round ({"Anzahl":2,"Preis":2})
		print(df.dtypes)
		if self.resolution == 'monthly':
			date = ['Monat']
				
		elif self.resolution == 'weekly':
			date =['Jahr','Kalenderwoche']
			
		elif self.resolution == 'daily':
			date = ['Datum']
			
		elif self.resolution == 'yearly':
			date = ["Jahr"]
			
		elif self.resolution == 'period':
			date = []

		else:
			frappe.msgprint("Bitte Zeiteinheit für Gruppierung auswählen")

		print(df)
		
		values =  []
		if self.anzahl == 1:
			values.append("Anzahl")
		if self.preis == 1:
			values.append("Preis")
		if self.gruppiert_nach == "Artikel":
			df_pivot =df.pivot_table(index=date, columns="Item", values = values, aggfunc = np.sum, fill_value=0)
		else:
			df_pivot =df.pivot_table(index=date, columns="Mitarbeiter", values = values, aggfunc = np.sum, fill_value=0)
		
		
		
		# #df_grouped = df.groupby(filters).agg({'Anzahl': ['sum']}).reset_index()
		# if self.anzahl == 1:
		# 	df['Item']=df['Item'].map('{} Anzahl'.format)
		# 	df_grouped = df.groupby(filters)['Anzahl'].sum().reset_index()
		# 	df_pivot1 = df_grouped.pivot_table(index= date,columns='Item',values='Anzahl')
		# 	df_pivot1 = df_pivot.fillna(0)
		# if self.preis == 1:
		# 	df['Item']=df['Item'].map('{} Preis'.format)
		# 	df_grouped = df.groupby(filters)['Preis'].sum().reset_index()
		# 	df_pivot2 = df_grouped.pivot_table(index= date,columns='Item',values='Preis')
		# 	df_pivot2= df_pivot.fillna(0)
		
	
		df_pivot = pd.DataFrame(df_pivot.to_records()) 
		
		a = df_pivot.drop(date,axis=1).astype(float)
		a[date] = df_pivot[date]
		a.set_index(date, inplace = True)
		c = a.columns.tolist()
		# = [lambda x : x.replace('(', '').replace(')','').replace("'",'') for x in c]
																					
		print(c)
		print(a)
		
	
		
		
		#df_pivot = df_pivot.astype(float)d
		#df_pivot = self.add_total_row(df_pivot)
		# print(df_pivot)
		self.report_ausgabe = self.get_styler(a).render()
                            
		if item_list == []:
			self.report_ausgabe = '<p>' + ("Für die angegebene Periode sind keine Daten vorhanden") + '</p>'
	def add_total_row(df,self):	
		sum_row = df.aggregate('sum')
		mean_row = df.aggregate('mean')
		df.loc['SUM']  = sum_row
		df.loc['MEAN'] = mean_row
	def get_styler(self,df):	
		styles = [
        dict(props=[("border-collapse", "collapse"), ("width", "100%")]),
        dict(selector="th, td", props=[("padding", ".75rem"), ("border-top", "1px solid #dee2e6")]),
        dict(selector=".col_heading", props=[('text-align', 'right')]),
        dict(selector=".col_heading.col0", props=[('text-align', 'left')]),
        dict(selector=".data", props=[("text-align", "right")]),
        #dict(selector=".col0", props=[("text-align", "left")]), # first column
        dict(selector="tbody tr:nth-of-type(odd)", props=[("background-color", "rgba(0,0,0,.05)")]), # stripes
		]
		return df.style.format('{:.2f}').set_table_styles(styles)