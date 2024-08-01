import frappe
import json
from datetime import datetime, date, timedelta
from frappe.database import get_db
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
def get_hours_from_ticket_service_reports(employee, from_date, to_date):

    if isinstance(from_date, str):
        from_date = datetime.strptime(from_date, "%Y-%m-%d")
    if isinstance(to_date, str):
        to_date = datetime.strptime(to_date, "%Y-%m-%d")

    to_date = to_date + timedelta(days=1) - timedelta(seconds=1)

    # Hours from the service reports
    service_report_hours = get_service_report_work(employee,from_date, to_date)

    # Hours from the tickets with status open
    ticket_hours = get_ticket_work_hours(employee, from_date, to_date)

    # Combine the results
    combined_hours = service_report_hours + ticket_hours

    hours_dict = {}

    if combined_hours:
        for entry in combined_hours:
            if entry['end'] and entry['begin'] and entry['end'] >= from_date and entry['begin'] <= to_date:
                date_key = entry['begin'].date()
                if date_key not in hours_dict:
                    hours_dict[date_key] = 0
                hours_dict[date_key] += entry['hours']
        hours_sum = sum([x['hours'] for x in combined_hours if x['end'] and x['begin'] and x['end'] >= from_date and x['begin'] <= to_date])
    else:
        hours_sum = 0

    sorted_hours_dict = dict(sorted(hours_dict.items()))
    print(hours_sum)
    print(hours_dict)
    return sorted_hours_dict, hours_sum


def get_service_report_work(employee, from_date, to_date):
    result = frappe.db.sql("""
        SELECT `begin`, `end`, `hours`
        FROM `tabService Report Work` 
        WHERE parenttype = 'Service Report'
        AND parent IN (SELECT name FROM `tabService Report` 
                       WHERE employee = %s 
                       AND (`begin` BETWEEN %s AND %s OR `end` BETWEEN %s AND %s))
    """, (employee, from_date, to_date, from_date, to_date), as_dict=True)

    return result

def get_ticket_work_hours(employee, from_date, to_date):

    # Get the OTRSConnect settings
    settings = frappe.get_doc("OTRSConnect Settings")
    otrsdb = get_db(host=settings.otrs_host, user=settings.db_user, password=settings.db_password)
    otrsdb.connect()
    otrsdb.use(settings.db_name)

    # Get the OTRSConnect user via the LinkField erpnext_employee
    user = frappe.get_all("OTRSConnect User", filters={"erpnext_employee": employee}, fields=["id"])
    if not user:
        return []
    user_id = user[0].id

    # Define SQL query
    sql = """
        SELECT 
            ticket.id, ticket.user_id, ticket.create_time, 
            time_accounting.time_unit
        FROM 
            ticket
        LEFT JOIN 
            time_accounting ON time_accounting.ticket_id = ticket.id
        WHERE 
            ticket.ticket_state_id = 4
            AND time_accounting.time_unit > 0
            AND ticket.create_time BETWEEN %(from_date)s AND %(to_date)s
            AND ticket.user_id = %(user_id)s;
    """

    # Execute the query with parameter transfer
    ticket_entries = otrsdb.sql(sql, {'from_date': from_date, 'to_date': to_date, 'user_id': user_id}, as_dict=True)

    # List for saving the processed ticket data
    ticket_hours = []

    for item in ticket_entries:

        # Calculate the hours and working times (15 minutes equals 0.25 hours)
        qty = float(item['time_unit']) / 4.0
        work_begin = item['create_time'] - timedelta(hours=qty)

        # Create the work item dictionary
        work_item = {
            "employee": employee,
            "begin": work_begin,
            "end": item['create_time'],
            "hours": qty
        }

       
        ticket_hours.append(work_item)

    return ticket_hours



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

    # List of public holidays
    holidays_list = get_holidays_list(from_date, to_date)

    # List of attendance data
    attendance_list = get_attendance_list(employee, from_date, to_date)

    target_hours_dict = {}

    if target_agreement:
        for agreement in target_agreement:
            agreement_from_date = max(from_date, agreement["from_date"])
            agreement_to_date = min(to_date, agreement["to_date"]) if agreement["to_date"] else to_date

            current_date = agreement_from_date
            while current_date <= agreement_to_date:

                # Check whether the date is included in the list of public holidays
                if current_date in holidays_list:
                    target_hours_dict[current_date] = 0
                else:
                    # Check the attendance status
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
    
    return holidays_list

def get_attendance_list(employee, from_date, to_date):

    # List of attendance data for the employee in the specified period
    attendance_data = frappe.get_all("Attendance",
                                     filters={
                                         "employee": employee,
                                         "attendance_date": (">=", from_date),
                                         "attendance_date": ("<=", to_date)
                                     },
                                     fields=["attendance_date", "status"])

    # Dictionary with date as key and attendance status as value
    attendance_dict = {entry["attendance_date"]: entry["status"] for entry in attendance_data}
    return attendance_dict


@frappe.whitelist()
def compare_hours(employee, from_date, to_date):

    if isinstance(from_date, str):
        from_date = datetime.strptime(from_date, "%Y-%m-%d")
    if isinstance(to_date, str):
        to_date = datetime.strptime(to_date, "%Y-%m-%d")

    
    # Working hours
    service_hours, service_hours_sum = get_hours_from_ticket_service_reports(employee, from_date, to_date)

    # Agreed hours
    target_hours = get_target_hours(employee, from_date, to_date)

    # Initialize the dictionaries
    daily_dict = {}
    period_dict = {"service_hours": service_hours_sum, "target_hours": sum(target_hours.values())}

    # Comparison of hours for each day in the period
    current_date = from_date
    to_date = to_date
    
    while current_date <= to_date:
        date_key = current_date.date()
        
        # Service hours for the date
        service_hour = service_hours.get(date_key, 0)
        
        # Agreed hours for the date
        target_hour = target_hours.get(date_key, 0)

        # Difference for the date
        difference = service_hour - target_hour 

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





