# compare_hours_chart_source.py

import frappe
from frappe import _
from msp.tools import compare_hours

@frappe.whitelist()
def get_employee_for_current_user():
    user = frappe.session.user
    employee = frappe.get_value("Employee", {"user_id": user}, "name")
    return employee

@frappe.whitelist()
def get_data(chart_name=None, chart=None, no_cache=None, filters=None, from_date=None, to_date=None, timespan=None, time_interval=None, heatmap_year=None):
    if filters:
        filters = frappe.parse_json(filters)

    employee = filters.get("employee")
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")

    if not employee:
        employee = get_employee_for_current_user()

    if not (employee and from_date and to_date):
        return {}

    # Get data from compare_hours function
    
    o = compare_hours(employee, from_date, to_date)

    # Extract data for the chart
    labels = [str(date) for date in o['daily_dict'].keys()]
    service_hours = [o['daily_dict'][date]['service_hours'] for date in o['daily_dict']]
    target_hours = [o['daily_dict'][date]['target_hours'] for date in o['daily_dict']]
    
    # Prepare data for Frappe chart
    data = {
        'labels': labels,
        'datasets': [
            {
                'name': 'Service Hours',
                'values': service_hours
            },
            {
                'name': 'Target Hours',
                'values': target_hours
            }
        ]
    }
    
    return data
