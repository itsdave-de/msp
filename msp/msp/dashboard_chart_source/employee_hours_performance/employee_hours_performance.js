

frappe.dashboards.chart_sources["Employee Hours Performance"] = {
    method: "msp.msp.dashboard_chart_source.employee_hours_performance.employee_hours_performance.get_data",
    filters: [
        {
            fieldname: "employee",
            label: __("Employee"),
            fieldtype: "Link",
            options: "Employee",
            default: "",
        },
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
        },
    ],
};
