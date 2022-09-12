import frappe
from erpnext.assets.doctype.location.location import Location

class CustomLocation(Location):
    @frappe.whitelist()
    def get_all_child_locations_from_location(self):
        parent_location_name = self.name
        locations_to_filter = []
        return self.search_child_locations(locations_to_filter, parent_location_name)

    def search_child_locations(self, locations_to_filter, parent_location_name):
        locations_to_filter.append(parent_location_name)
        child_locations = frappe.db.get_list('Location', {'parent_location': parent_location_name}, ['name'])
        if child_locations:
            for child_location in child_locations:
                self.search_child_locations(locations_to_filter, child_location['name'])

        return locations_to_filter
