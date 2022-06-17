frappe.listview_settings['IT Object'] = {	
	get_indicator: function (doc) {
		if (doc.status === "in Production") {
			return [__("in Production"), "green", "status,=,in Production"];
		}
        else if (doc.status === "Implementation") {
			return [__("Implementation"), "blue", "status,=,Implementation"];
        } 
        else if (doc.status === "in Maintenance") {
			return [__("in Maintenance"), "orange", "status,=,in Maintenance"];
        }
        else if (doc.status === "failed") {
			return [__("failed"), "red", "status,=,failed"];
        }
        else if (doc.status === "Decommissioned") {
			return [__("Decommissioned"), "grey", "status,=,Decommissioned"];
        }
    }
}