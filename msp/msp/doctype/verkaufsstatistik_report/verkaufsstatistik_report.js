// Copyright (c) 2021, itsdave GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on('Verkaufsstatistik Report', {
	refresh: function(frm) {
        moment.locale("de") // weeks start on monday
        frm.trigger('preset');
        
        frm.add_custom_button('Generate Excel Sheet', () => frm.trigger('generate_excel_sheet'));
        frm.add_custom_button('Generate Report', () => frm.trigger('generate_report'));
		},
		generate_report: function(frm) {
			frm.call('generate_report', {}, () => frm.reload_doc());
        
            
		},
		generate_excel_sheet: function(frm) {
			frm.call('generate_excel_sheet', {}, () => frm.reload_doc());
        
        
        },
    // setup: function(frm) {
    //     frm.set_query("artikel",function(){
    //         return {
    //             filters: [
    //                 ["Item","item_group", "in", ["Anwendungsentwicklung", "Arbeitszeiten Techniker"]]
    //             ]
    //         }
    //     });
    // },

    preset: function(frm) {
        if (!frm.doc.preset) {
            // No preset selected. Allow manual selection of dates.
            frm.toggle_enable(['from_date', 'to_date'], true);
        } else {
            // Preset selected. Make dates read only.
            frm.toggle_enable(['from_date', 'to_date'], false);

            if (frm.doc.preset === 'Last Week') {
                frm.events.set_dates(frm, frappe.datetime.previous("week"));
            } else if (frm.doc.preset === 'Last Month') {
                frm.events.set_dates(frm, frappe.datetime.previous("month"));
            } else if (frm.doc.preset === 'Last Year') {
                frm.events.set_dates(frm, frappe.datetime.previous("year"));
            } else if (frm.doc.preset === 'YTD') {
                frm.events.set_dates(frm, frappe.datetime.year_to_date());
            }
        }
    },
    set_dates: function(frm, date_range) {
        frm.set_value('from_date', date_range.start);
        frm.set_value('to_date', date_range.end);
    },
    });
