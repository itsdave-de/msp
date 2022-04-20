# Copyright (c) 2021, itsdave GmbH and contributors
# For license information, please see license.txt


from frappe.model.document import Document
from os import replace
import frappe
from datetime import datetime as dt
from pprint import pprint
import pandas as pd
import numpy as np
from six import BytesIO
from frappe.utils.file_manager import save_file

class VerkaufsstatistikReport(Document):
	@frappe.whitelist()
	def do_report(self):
		
		employee_tup = ""
		if self.gruppiert == "Employee":
			employee_auswahl = self.employee
			if employee_auswahl != []:
				employee_list = [x.employee for x in employee_auswahl]
				filters = {"employee": ["in", employee_list]}
			else:
				filters = {}
			employee_art = frappe.get_all(
				"Employee Item Assignment", 
				filters= filters, 
				fields= ["item","employee_name"])
			#employee_artikel = [x.item for x in employee_art]
			artikel_name = [x.item for x in employee_art]
			employee_tup = [(x.item,x.employee_name) for x in employee_art]
			print(employee_tup)
			# if employee_auswahl == []:
			# 	frappe.throw('Keine Mitarbeiter ausgewählt.')
		elif self.gruppiert == "Item":
			artikel_auswahl = self.artikel
			print(artikel_auswahl)
			artikel_name = [a.item for a in artikel_auswahl]
			if artikel_auswahl == []:
				frappe.throw('Keine Artikel ausgewählt.')
		else:
			frappe.throw('Keine Auswahl bei Gruppierung getroffen.')			
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
						b = [y[0] for y in employee_tup]
						if artikel.item_code in b:
							employee =employee_tup[b.index(artikel.item_code )][1] 
						else:
							employee = 0
							
						#print(employee)
						#empl = str(artikel.item_name).replace("Arbeitszeit ","").replace("Herr ","").replace(" Anwendungsentwicklung","").replace("Remote-Service ","")
						price = artikel.qty*artikel.rate
						artikel_details = [si["posting_date"],employee,artikel.item_name,artikel.item_code,artikel.qty,artikel.rate, price]
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
						b = [y[0] for y in employee_tup]
						if artikel.item_code in b:
							employee =employee_tup[b.index(artikel.item_code )][1] 
						else:
							employee = 0
						#empl = str(artikel.item_name).replace("Arbeitszeit ","").replace("Herr ","").replace(" Anwendungsentwicklung","").replace("Remote-Service ","")
						price = artikel.qty*artikel.rate

						artikel_details = [dn["posting_date"],employee,artikel.item_name,artikel.item_code,artikel.qty, artikel.rate, price]
						item_list.append(artikel_details)
				
		
		
		df = pd.DataFrame(item_list, columns = ["Datum","Mitarbeiter","Item Name","Item","Anzahl","Preis pro Einheit","Preis"])
		df['Date'] = pd.to_datetime(df['Datum'])
		df['Datum'] = df['Date'].dt.strftime('%d.%m.%Y')
		df['Kalenderwoche']= df['Date'].dt.isocalendar().week
		#df['Monat']= df['Date'].dt.month
		df['Jahr'] = df['Date'].dt.year
		df['Monat'] = df['Date'].dt.strftime("%m.%Y")
		from_date_dt = dt. strptime(self.from_date, '%Y-%m-%d')
		from_date_st = from_date_dt.strftime('%d.%m.%Y')
		to_date_dt = dt. strptime(self.to_date, '%Y-%m-%d')
		to_date_st = to_date_dt.strftime('%d.%m.%Y')
		df['Periode'] = from_date_st+ " bis " + to_date_st
		
		df.round ({"Anzahl":2,"Preis":2})
		if df.empty:
			frappe.throw('Für die angegebene Periode sind keine Daten vorhanden')
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
			date = ["Periode"]

		else:
			frappe.msgprint("Bitte Zeiteinheit für Gruppierung auswählen")

		print(df)
		
		values =  []
		if self.anzahl == 1:
			values.append("Anzahl")
		if self.preis == 1:
			values.append("Preis")
		if len(values) == 0:
			frappe.msgprint("Bitte Vergleichswert auswählen")

		if self.gruppiert_nach == "Artikel":
			df_pivot =df.pivot_table(index=date, columns="Item", values = values, aggfunc = np.sum, fill_value=0)
		elif self.gruppiert_nach == "Mitarbeiter": 
			df_pivot =df.pivot_table(index=date, columns="Mitarbeiter", values = values, aggfunc = np.sum, fill_value=0)
		elif self.gruppiert_nach == "Alle":
			df_pivot =df.pivot_table(index=date, values = values, aggfunc = np.sum, fill_value=0)
		# df_pivot.columns = df_pivot.columns.droplevel(0) #remove amount
		# df_pivot.columns.name = None               #remove categories
		# df_pivot = df_pivot.reset_index()                #index to columns
		# print(df_pivot)
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
																		
		#print(a)
		#df_pivot = df_pivot.astype(float)d
		#df_pivot = self.add_total_row(df_pivot)
		# print(df_pivot)

		#self.report_ausgabe = self.get_styler(a).render()
                            
		if item_list == []:
			self.report_ausgabe = '<p>' + ("Für die angegebene Periode sind keine Daten vorhanden") + '</p>'
		return a
	@frappe.whitelist()
	def generate_report(self):
		df = self.do_report()
		if self.summenzeile == 1:
			df= self.add_total_row(df)
		if df.empty:
			frappe.throw('Für die angegebene Periode sind keine Daten vorhanden')
		self.report_ausgabe = self.get_styler(df).render()
		self.save()

	def add_total_row(self,df):
		
		sum_row = df.aggregate('sum')
		df.loc['SUM']  = sum_row
		
		return df
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
		if self.summenzeile == 1:
			a = dict(selector="tr:nth-last-child(1)", props=[("font-weight", "bold")])
			styles.append(a)
		return df.style.format('{:.2f}').set_table_styles(styles)
	
	@frappe.whitelist()
	def generate_excel_sheet(self):
        
		df = self.do_report()
		if self.summenzeile == 1:
			df= self.add_total_row(df)

		if df.empty:
			frappe.throw('Für die angegebene Periode sind keine Daten vorhanden')
		
		self.attach_as_excel(self.get_styler(df), self.doctype, self.name)

	def styler_to_excel(self,styler):
    
		buffer = BytesIO()
		with pd.ExcelWriter(buffer, engine='xlsxwriter', date_format='DD.MM.YYYY', datetime_format='DD.MM.YYYY hh:mm') as writer:
			
			styler.to_excel(writer, index=True)
		return buffer.getvalue()

		

	def attach_as_excel(self,styler, doctype, name):
    
		content = self.styler_to_excel(styler)
		
		filename = name + '.xlsx'
		save_file(filename, content, doctype, name, None, False, 1)