import frappe
import json
from datetime import datetime, date, timedelta
from erpnext.stock.utils import get_stock_balance

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
    


@frappe.whitelist()
def get_hours_from_service_reports(employee, from_date, to_date):
   
   
    to_date = to_date + timedelta(days=1) - timedelta(seconds=1)

    result = get_service_report_work(employee)
    #print(result)

    hours_dict = {}

    if result:
        for entry in result:
            if entry['end'] and entry['begin'] and entry['end'] >= from_date and entry['begin'] <= to_date:
                date_key = entry['begin'].date()
                if date_key not in hours_dict:
                    hours_dict[date_key] = 0
                hours_dict[date_key] += entry['hours']
        hours_sum = sum([x.hours for x in result if x.end and x.begin and x.end >= from_date and x.begin <= to_date])

    else:
        hours_sum = 0
    sorted_hours_dict = dict(sorted(hours_dict.items()))
    #print(hours_sum)
    #print(hours_dict)
    return sorted_hours_dict,hours_sum

def get_service_report_work(employee):


    result = frappe.db.sql("""
        SELECT `begin`, `end`, `hours`
        FROM `tabService Report Work` 
        WHERE parenttype = 'Service Report'
        AND parent IN (SELECT name FROM `tabService Report` 
                       WHERE employee = %s 
                       )
    """, (employee,), as_dict=True)

    return result


@frappe.whitelist()
def get_target_hours(employee, from_date, to_date):
    from_date = from_date.date()
    to_date = to_date.date()

    target_agreement = frappe.get_all("Employee Target Agreement",
                                       filters={
                                           "employee": employee,
                                           "to_date": (">=", from_date),
                                           "from_date": ("<=", to_date)
                                       },
                                       fields=["from_date", "to_date", "daily_hours"])

    # Liste der Feiertage
    holidays_list = get_holidays_list(from_date, to_date)

    # Liste der Anwesenheitsdaten
    attendance_list = get_attendance_list(employee, from_date, to_date)

    target_hours_dict = {}

    if target_agreement:
        for agreement in target_agreement:
            agreement_from_date = max(from_date, agreement["from_date"])
            agreement_to_date = min(to_date, agreement["to_date"])

            current_date = agreement_from_date
            while current_date <= agreement_to_date:
                # Überprüfen, ob das Datum in der Liste der Feiertage enthalten ist
                if current_date in holidays_list:
                    target_hours_dict[current_date] = 0
                else:
                    # Überprüfung vom Anwesenheitsstatus
                    attendance_status = attendance_list.get(current_date, "")
                    if attendance_status == "On Leave":
                        target_hours_dict[current_date] = 0
                    elif attendance_status == "Half Day":
                        target_hours_dict[current_date] = agreement["daily_hours"] / 2
                    else:
                        target_hours_dict[current_date] = agreement["daily_hours"]

                current_date += timedelta(days=1)

    return target_hours_dict

def get_holidays_list(from_date, to_date):
    
    holidays = frappe.get_all("Holiday List", filters={"to_date": (">=", from_date),
                                           "from_date": ("<=", to_date)}, 
                                          )
    holidays_list =[] 
    for x in holidays:
        hol_doc = frappe.get_doc("Holiday List", x.name)
        holidays_li = [h.holiday_date for h in hol_doc.holidays]
        holidays_list.extend(holidays_li)
    
    #print(holidays_list)
    
    # holidays_list = [datetime.strptime(holiday, '%Y-%m-%d').date() for holiday in holidays[0]["holidays"]]
    return holidays_list

def get_attendance_list(employee, from_date, to_date):
    # Liste der Anwesenheitsdaten für den Mitarbeiter im angegebenen Zeitraum
    attendance_data = frappe.get_all("Attendance",
                                     filters={
                                         "employee": employee,
                                         "attendance_date": (">=", from_date),
                                         "attendance_date": ("<=", to_date)
                                     },
                                     fields=["attendance_date", "status"])

    # Dictionary mit Datum als Schlüssel und Anwesenheitsstatus als Wert
    attendance_dict = {entry["attendance_date"]: entry["status"] for entry in attendance_data}
    return attendance_dict


@frappe.whitelist()
def compare_hours(employee, from_date, to_date):
    from_date = datetime.strptime(from_date, '%Y-%m-%d')
    to_date = datetime.strptime(to_date, '%Y-%m-%d')
    # Stunden aus get_hours_from_service_reports erhalten
    service_hours, service_hours_sum = get_hours_from_service_reports(employee, from_date, to_date)

    # Stunden aus get_target_hours erhalten
    target_hours = get_target_hours(employee, from_date, to_date)

    # Initialisiere die Dictionarys
    daily_dict = {}
    period_dict = {"service_hours": service_hours_sum, "target_hours": sum(target_hours.values())}

    # Vergleich der Stunden für jeden Tag im Zeitraum
    current_date = from_date
    to_date = to_date
    
    while current_date <= to_date:
        date_key = current_date.date()
        
        # Service-Stunden für das Datum
        service_hour = service_hours.get(date_key, 0)
        
        # Target-Stunden für das Datum
        target_hour = target_hours.get(date_key, 0)

        # Differenz zwischen Target-Stunden und Service-Stunden für das Datum
        difference = service_hour - target_hour 

        # Füge Werte zum daily_dict hinzu
        daily_dict[date_key] = {"service_hours": service_hour, "target_hours": target_hour, "difference": difference}

        current_date += timedelta(days=1)

    return {"daily_dict": daily_dict, "period_dict": period_dict}


@frappe.whitelist()
def get_act_stock(name):
    warehouses = frappe.get_all("Warehouse", filters={"disabled": 0}, pluck="name")  # Alle aktiven Warenlager erhalten
    total_qty = 0

    for warehouse in warehouses:
        item_qty = get_stock_balance(name, warehouse)
        total_qty += item_qty
    
    # warehouse = "Lagerräume - IG"
    # item_qty = get_stock_balance(name,warehouse)
   
    if item_qty < 0:
        result = '<i class="fa fa-cube" style="color: var(--text-on-red);"></i>'+ ' ' + str(item_qty)
    elif item_qty == 0:
        result = '<i class="fa fa-cube" style="color: #D3D3D3;"></i>' + ' ' + str(item_qty)
    elif item_qty > 0:
        result = '<i class="fa fa-cube" style="color: #90EE90;"></i>' + ' ' + str(item_qty)
    # <i class="fa fa-cube" style="color: var(--text-on-green);"></i>
    return result





