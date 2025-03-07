import frappe
import json
from datetime import datetime, date, timedelta
import math
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

    # Stunden aus Service Reports und Tickets abrufen
    service_report_hours = get_service_report_work(employee, from_date, to_date)
    ticket_hours = get_ticket_work_hours(employee, from_date, to_date)

    combined_hours = service_report_hours + ticket_hours

    hours_dict = {}
    detailed_entries = []  # Liste für Kalendereinträge

    if combined_hours:
        for entry in combined_hours:
            if entry['end'] and entry['begin'] and entry['end'] >= from_date and entry['begin'] <= to_date:
                current_time = entry['begin']
                
                while current_time < entry['end']:
                    date_key = current_time.date()
                    next_day = (current_time + timedelta(days=1)).replace(hour=0, minute=0, second=0)

                    if date_key not in hours_dict:
                        hours_dict[date_key] = 0
                    
                    # Bestimme die tatsächliche Endzeit für diesen Tag
                    actual_end = min(entry['end'], next_day)
                    
                    # Berechne die Stunden für diesen Zeitraum
                    work_hours = (actual_end - current_time).total_seconds() / 3600
                    
                    # Runde auf Viertelstunden
                    work_hours = math.ceil(work_hours * 4) / 4  

                    hours_dict[date_key] += work_hours
                    
                    # Kalendereintrag hinzufügen
                    detailed_entries.append({
                        "employee": employee,
                        "begin": current_time,
                        "end": actual_end,
                        "hours": work_hours,
                        "customer": entry.get("customer", "Unbekannt"),
                        "description": entry.get("description", "Keine Beschreibung")
                    })
                    
                    current_time = next_day  # Zum nächsten Tag übergehen

        # Gesamtstunden berechnen (nach Rundung)
        hours_sum = sum(hours_dict.values())
    else:
        hours_sum = 0

    sorted_hours_dict = dict(sorted(hours_dict.items()))
    print(sorted_hours_dict)
    
    return sorted_hours_dict, hours_sum, detailed_entries


def get_service_report_work(employee, from_date, to_date):
    result = frappe.db.sql("""
        SELECT srw.`begin`, srw.`end`, srw.`hours`, sr.customer, srw.description
        FROM `tabService Report Work` srw
        JOIN `tabService Report` sr ON sr.name = srw.parent
        WHERE sr.employee = %s
        AND (srw.`begin` BETWEEN %s AND %s OR srw.`end` BETWEEN %s AND %s)
       
       
    """, (employee, from_date, to_date, from_date, to_date), as_dict=True)

    return result


def get_ticket_work_hours(employee, from_date, to_date):
    print(f"DEBUG: Start get_ticket_work_hours for employee {employee}, from {from_date} to {to_date}")

    if isinstance(from_date, str):
        from_date = datetime.strptime(from_date, "%Y-%m-%d")
    if isinstance(to_date, str):
        to_date = datetime.strptime(to_date, "%Y-%m-%d")

    to_date = to_date + timedelta(days=1) - timedelta(seconds=1)

    user = frappe.get_all("OTRSConnect User", filters={"erpnext_employee": employee}, fields=["id"])
    if not user:
        print("DEBUG: No OTRSConnect User found for this employee.")
        return []

    user_id = user[0].id

    considered_articles = frappe.db.sql("""
    SELECT otrs_article
    FROM `tabService Report Work`
    WHERE otrs_article IS NOT NULL AND `begin` BETWEEN %s AND %s
    """, (from_date, to_date), as_list=True)

    considered_article_ids = [article[0] for article in considered_articles]

    sql_query = """
    SELECT 
        a.`id`, 
        a.`create_time`, 
        a.`time_unit`, 
        a.`a_body` AS description,  
        t.`erpnext_customer` AS customer
    FROM `tabOTRSConnect Article` a
    LEFT JOIN `tabOTRSConnect Ticket` t ON a.`ticket_id` = t.`name`
    WHERE 
        a.create_time BETWEEN %s AND %s
        AND a.create_by = %s
        AND a.docstatus IN (0, 1)
    """

    params = (from_date, to_date, user_id)
    if considered_article_ids:
        sql_query += " AND a.id NOT IN %s"
        params += (tuple(considered_article_ids),)

    result = frappe.db.sql(sql_query, params, as_dict=True)

    if not result:
        print("DEBUG: No articles found in `tabOTRSConnect Article` for the given conditions.")
        return []

    ticket_hours = []

    for item in result:
        qty = float(item['time_unit']) / 4.0
        work_begin = item['create_time'] - timedelta(hours=qty)

        work_item = {
            "employee": employee,
            "begin": work_begin,
            "end": item['create_time'],
            "hours": qty,
            "customer": item.get("customer", "Unbekannt"),
            "description": item.get("description", "Keine Beschreibung")
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
    service_hours, service_hours_sum, detailed_entries = get_hours_from_ticket_service_reports(employee, from_date, to_date)
    print(service_hours, service_hours_sum, detailed_entries)

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

    return {
        "daily_dict": daily_dict,
        "period_dict": period_dict,
        "detailed_entries": detailed_entries  
        }


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

def get_otrsdb_connection():
    settings = frappe.get_doc("OTRSConnect Settings")
    password = settings.get_password("db_password")
    otrsdb = get_db(host=settings.otrs_host, user=settings.db_user, password=password)
    otrsdb.connect()
    otrsdb.use(settings.db_name)
    return otrsdb, settings

def get_tickets_from_otrsdb(otrsdb, condition):
    sql = f"""
        SELECT DISTINCT ticket.id, ticket.tn, ticket.title, 
            ticket.queue_id, ticket.user_id, ticket.responsible_user_id, 
            ticket.ticket_priority_id, ticket.customer_id, ticket.customer_user_id, 
            ticket.ticket_state_id, ticket.create_time, ticket.create_by, 
            ticket.change_time, ticket.change_by 
        FROM ticket 
        LEFT JOIN users ON ticket.user_id=users.id 
        LEFT JOIN customer_company ON customer_company.customer_id=ticket.customer_id 
        LEFT JOIN time_accounting ON time_accounting.ticket_id=ticket.id 
        WHERE time_accounting.time_unit > 0 
        AND {condition}
    """
    return otrsdb.sql(sql, as_dict=1)

def get_articles_from_otrsdb(otrsdb, last_article_id):
    sql = f"""
        SELECT article.id, article.ticket_id, article.create_time, 
            article.create_by, article_data_mime.a_from, article_data_mime.a_to, 
            article_data_mime.a_subject, article_data_mime.a_body, 
            time_accounting.time_unit 
        FROM article 
        LEFT JOIN article_data_mime ON article.id=article_data_mime.id 
        LEFT JOIN time_accounting time_accounting ON article.id=time_accounting.article_id 
        WHERE time_accounting.time_unit > 0 
        AND article.id > {last_article_id}
    """
    return otrsdb.sql(sql, as_dict=1)

@frappe.whitelist()
def update_tickets_and_articles():
    otrsdb, settings = get_otrsdb_connection()
    sync_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Ensure settings.last_ticket_sync has a default value
    last_ticket_sync = settings.last_ticket_sync or '2024-07-01T00:00:00'

    # Add a buffer of 15 minutes to the last_ticket_sync time
    last_ticket_sync_time = datetime.strptime(last_ticket_sync, "%Y-%m-%d %H:%M:%S")
    last_ticket_sync_with_buffer = (last_ticket_sync_time - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
    
    
    new_tickets = get_tickets_from_otrsdb(otrsdb, f"ticket.id > {int(settings.last_ticket_id)}")
    print(len(new_tickets))
    updated_tickets = get_tickets_from_otrsdb(otrsdb, f"ticket.change_time > '{last_ticket_sync_with_buffer}'")
    print(len(updated_tickets))
    articles = get_articles_from_otrsdb(otrsdb, int(settings.last_article_id))
    print(len(articles))

    messages = []
    if new_tickets:
        messages.append(f"Found {len(new_tickets)} new tickets.")
    else:
        messages.append("No new tickets found.")
        
    if updated_tickets:
        messages.append(f"Found {len(updated_tickets)} updated tickets.")
    else:
        messages.append("No updated tickets found.")
        
    if articles:
        messages.append(f"Found {len(articles)} new articles.")
    else:
        messages.append("No new articles found.")
    
    # Display messages to the user
    for message in messages:
        frappe.msgprint(message)

    # Process and store new and updated tickets
    for ticket in new_tickets + updated_tickets:
        process_ticket(ticket)
    frappe.db.commit()
    # Update last_ticket_id and last_ticket_sync based on the processed tickets
    if new_tickets:
        settings.last_ticket_id = max([int(t['id']) for t in new_tickets] + [int(settings.last_ticket_id)])
    settings.last_ticket_sync = sync_time
    
    # Process and store articles
    for article in articles:
        process_article(article)
    frappe.db.commit()
    # Update last_article_id based on the processed articles
    if articles:
        settings.last_article_id = max([int(a['id']) for a in articles] + [int(settings.last_article_id)])
        
    settings.last_article_sync = sync_time

    settings.save()
    frappe.db.commit()

def process_ticket(ticket):
    ERPNext_tickets = frappe.get_all("OTRSConnect Ticket", filters={"id": ticket["id"]})
    
    if not ERPNext_tickets:
        frappe_doctype_dict = {"doctype": "OTRSConnect Ticket", "status": "fetched"}
        ticket["id"] = str(ticket["id"])
        frappe_doctype_dict.update(ticket)
        ticket_doc = frappe.get_doc(frappe_doctype_dict)
        ticket_doc.insert()
        link_ERPNext_OTRS_Ticket(ticket_doc)
    else:
        existing_ticket = frappe.get_doc("OTRSConnect Ticket", ERPNext_tickets[0].name)
        if existing_ticket.docstatus == 0 and existing_ticket.status != "delivered":
            read_only_fields = {"create_time", "create_by"}
            for key, value in ticket.items():
                if key not in read_only_fields:
                    setattr(existing_ticket, key, value)
            existing_ticket.save(ignore_permissions=True, ignore_version=True)

def process_article(article):
    # Ensure the referenced ticket exists
    ticket_exists = frappe.db.exists("OTRSConnect Ticket", {"id": article["ticket_id"]})
    
    if not ticket_exists:
        # Fetch the ticket from OTRS and insert it into ERPNext
        otrsdb, _ = get_otrsdb_connection()
        ticket = get_tickets_from_otrsdb(otrsdb, f"ticket.id = {article['ticket_id']}")
        if ticket:
            process_ticket(ticket[0])
    
    # Check again if the ticket now exists
    ticket_exists = frappe.db.exists("OTRSConnect Ticket", {"id": article["ticket_id"]})
    if ticket_exists:
        ERPNext_articles = frappe.get_all("OTRSConnect Article", filters={"id": article["id"]})
        
        if not ERPNext_articles:
            # Article doesn't exist, create a new one
            frappe_doctype_dict = {"doctype": "OTRSConnect Article"}
            article["id"] = str(article["id"])
            article["ticket_id"] = str(article["ticket_id"])
            frappe_doctype_dict.update(article)
            article_doc = frappe.get_doc(frappe_doctype_dict)
            article_doc.insert()
    else:
        print(f"Warning: Referenced ticket ID {article['ticket_id']} does not exist in ERPNext.")

def link_ERPNext_OTRS_Ticket(OTRSConnect_Ticket):

    if OTRSConnect_Ticket.customer_id == None:
        frappe.msgprint("Keine Kundenummer vorhanden für: " + str(OTRSConnect_Ticket.title) + "<br>" + str(OTRSConnect_Ticket.tn))
        return False

    if OTRSConnect_Ticket.customer_id == "":
        frappe.msgprint("Kundennummerzuweisung nicht eindeutig möglich für: " + str(OTRSConnect_Ticket.title) + "<br>" + str(OTRSConnect_Ticket.id))
        return False
    naming_series = "CUST-" + str(OTRSConnect_Ticket.customer_id)
    customers_for_customer_id = frappe.get_all("Customer", filters={"naming_series": naming_series})
    if len(customers_for_customer_id) == 1:
        OTRSConnect_Ticket.erpnext_customer = naming_series
        OTRSConnect_Ticket.save()
    else:
        frappe.msgprint("Kundennummerzuweisung nicht eindeutig möglich für: " + str(OTRSConnect_Ticket.customer_id) + "<br>" + str(OTRSConnect_Ticket.title) + "<br>" + str(OTRSConnect_Ticket.id))

@frappe.whitelist()
def save_backlinks(doc, method):
    service_report = doc 
    
    if hasattr(service_report, 'work'):
        for item in service_report.work:
            if hasattr(item, 'otrs_article'):
                service_report_article = item.name
                article_name = item.otrs_article
                articles = frappe.get_all('OTRSConnect Article', filters={'name': article_name}, fields=['name'])
                
                for article in articles:
                    article_doc = frappe.get_doc('OTRSConnect Article', article.name)
                    updated = False
                    
                    if not article_doc.service_report:
                        article_doc.service_report = service_report.name
                        updated = True
                    
                    if not article_doc.service_report_work_item:
                        article_doc.service_report_work_item = service_report_article
                        updated = True
                    
                    if updated:
                        article_doc.save()
                        frappe.db.commit()

def handle_backlinks(doc, method):
    if method == "on_trash":
        clear_backlinks(doc)
    elif method == "on_cancel":
        clear_backlinks(doc)

def clear_backlinks(doc):
    if hasattr(doc, 'work'):
        for item in doc.work:
            if hasattr(item, 'otrs_article'):
                article_name = item.otrs_article
                articles = frappe.get_all('OTRSConnect Article', filters={'name': article_name, 'service_report': doc.name}, fields=['name'])
                
                for article in articles:
                    article_doc = frappe.get_doc('OTRSConnect Article', article.name)
                    updated = False
                    
                    if article_doc.service_report == doc.name:
                        article_doc.service_report = None
                        updated = True
                        
                    if article_doc.service_report_work_item == item.name:
                        article_doc.service_report_work_item = None
                        updated = True
                    
                    if updated:
                        article_doc.save()
                        frappe.db.commit()

def get_status_from_ticket():
    # Abrufen von maximal 100 Datensätzen aus der "OTRSConnect Article"-Dokumentation
    ERPNext_articles = frappe.get_all("OTRSConnect Ticket", fields=["*"], limit=100)
    
    # Ausgabe der Statusinformationen
    for article in ERPNext_articles:
        for field, value in article.items():
            print(f"{field}: {value}")
        print("---")

 





