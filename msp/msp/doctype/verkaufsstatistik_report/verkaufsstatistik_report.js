// Copyright (c) 2021, itsdave GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on('Verkaufsstatistik Report', {
	refresh: function(frm) {
        
        moment.locale("de") // weeks start on monday
        frm.trigger('preset');
        
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
    
    from_date: (frm) => frm.trigger('set_to_date'),
    set_to_date: function (frm) {
        
        const len_in_days = moment(frm.doc.to_date).diff(moment(frm.doc.from_date), 'days');
        let to_date = moment(frm.doc.from_date).add(len_in_days, 'days');

        if (frm.doc.preset && frm.doc.preset !== 'YTD') {
            // to_date is equal to the end of the week / month / year of from_date
            const time_map = {
                'Last Week': 'week',
                'Last Month': 'month',
                'Last Year': 'year',
            }
            to_date = moment(frm.doc.from_date).endOf(time_map[frm.doc.preset]);
        }

        
    },
    set_from_date: function(frm) {
        

        if (frm.doc.to_previous_year) {
            frm.toggle_enable(['from_date'], false);
            let from_date = moment(frm.doc.from_date).subtract(1, 'year');

            if (frm.doc.preset == 'Last Week') {
                const week = moment(frm.doc.from_date).format('WW');
                const previous_year = (moment(frm.doc.from_date).year() - 1).toString();
                from_date = moment(`${previous_year}W${week}`);
            }

            frm.set_value('from_date', from_date.format());
        } else {
            frm.toggle_enable(['from_date'], true);
		}
	},
	
	set_dates: function(frm, date_range) {
	frm.set_value('from_date', date_range.start);
	frm.set_value('to_date', date_range.end);	
    },
    
    
});

