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
                let beforeOneWeek = new Date(new Date().getTime() - 60 * 60 * 24 * 7 * 1000),
                    beforeOneWeek2 = new Date(beforeOneWeek),
                    day = beforeOneWeek.getDay(),
                    diffToMonday = beforeOneWeek.getDate() - day + (day === 0 ? -6 : 1),
                    lastMonday = new Date(beforeOneWeek.setDate(diffToMonday)).toISOString().split('T')[0],
                    lastSunday = new Date(beforeOneWeek2.setDate(diffToMonday + 6)).toISOString().split('T')[0]
                console.log(lastMonday,lastSunday)
                frm.set_value('from_date',lastMonday)
                frm.set_value('to_date',lastSunday)
            } else if (frm.doc.preset === 'Last Month') {
                let date = new Date(),
                    previousMonthFirstDay = new Date(date.getFullYear(), date.getMonth()- 1, 2).toISOString().split('T')[0],
                    previousMonthLastDay = new Date(date.getFullYear(), date.getMonth() , 1).toISOString().split('T')[0]
                    console.log(previousMonthFirstDay,previousMonthLastDay)
                frm.set_value('from_date',previousMonthFirstDay)
                frm.set_value('to_date',previousMonthLastDay)
            } else if (frm.doc.preset === 'Last Year') {
                let currentYear = new Date().getFullYear(),
                    previousYear =  currentYear-1,
                    firstDay = new Date(previousYear, 0, 2).toISOString().split('T')[0],
                    lastDay = new Date(currentYear, 0, 1).toISOString().split('T')[0]
                console.log(lastDay);
                frm.set_value('from_date',firstDay)
                frm.set_value('to_date',lastDay)
            } else if (frm.doc.preset === 'YTD') {
                let currentYear = new Date().getFullYear(),
                    firstDaySY = new Date(currentYear, 0, 2).toISOString().split('T')[0],
                    today = new Date().toISOString().split('T')[0];
                frm.set_value('from_date',firstDaySY);
                frm.set_value('to_date',today);
                
            }
        }
    },
    });
            // } else if (frm.doc.preset === 'Last Month') {
            //     frm.events.set_dates(frm, frappe.datetime.previous("month"));
            // } else if (frm.doc.preset === 'Last Year') {
            //     frm.events.set_dates(frm, frappe.datetime.previous("year"));
            // } else if (frm.doc.preset === 'YTD') {
            //     frm.events.set_dates(frm, frappe.datetime.year_to_date());
//             // }
//         }
//     },
// //             if (frm.doc.preset === 'Last Week') {
//                 frm.events.set_dates(frm, frappe.datetime.previous("week"));
//             } else if (frm.doc.preset === 'Last Month') {
//                 frm.events.set_dates(frm, frappe.datetime.previous("month"));
//             } else if (frm.doc.preset === 'Last Year') {
//                 frm.events.set_dates(frm, frappe.datetime.previous("year"));
//             } else if (frm.doc.preset === 'YTD') {
//                 frm.events.set_dates(frm, frappe.datetime.year_to_date());
//             }
//         }
//     },
        
   


//     set_dates: function(frm, date_range) {
//     frm.set_value('from_date', date_range.start);
//     frm.set_value('to_date', date_range.end);
//     console.log(date_range);
//     console.log(date_range.start);
//     console.log(date_range.end)
//     }
// });
