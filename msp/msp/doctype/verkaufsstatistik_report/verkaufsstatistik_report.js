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
                
                frm.call({
                    method: 'msp.msp.doctype.verkaufsstatistik_report.verkaufsstatistik_report.generate_report',
                    args: { doc_name: frm.doc.name },
                    freeze: true,
                    freeze_message: __("Report wird erstellt ..."),
                    callback: function() {
                        
                        frm.reload_doc();
                    },
                   
                });
            },
            generate_excel_sheet: function(frm) {
                frm.call('generate_excel_sheet', {}, () => frm.reload_doc());
            
            
            },
        
        
    
        // generate_report: function(frm) {
        //     frappe.show_progress('Report wird generiert...', 50, 100, 'Dieser Vorgang kann ein paar Minuten dauern.')
        //     frm.call('generate_report', {}, () => frm.reload_doc());
        //     frappe.hide_progress();
        
   
        // },
            
		// generate_excel_sheet: function(frm) {
		// 	frm.call('generate_excel_sheet', {}, () => frm.reload_doc());
        
        
        // },
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
                    lastMonday = convertDate(new Date(beforeOneWeek.setDate(diffToMonday))),
                    lastSunday = convertDate(new Date(beforeOneWeek2.setDate(diffToMonday + 6)))
                console.log(lastMonday,lastSunday)
                frm.set_value('from_date',lastMonday)
                frm.set_value('to_date',lastSunday)
            } else if (frm.doc.preset === 'Last Month') {
                let date = new Date(),
                    previousMonthFirstDay = convertDate(new Date(date.getFullYear(), date.getMonth()- 1, 1)),
                    previousMonthLastDay = convertDate(new Date(date.getFullYear(), date.getMonth() , 0))
                    console.log(previousMonthFirstDay,previousMonthLastDay)
                frm.set_value('from_date',previousMonthFirstDay)
                frm.set_value('to_date',previousMonthLastDay)
            } else if (frm.doc.preset === 'Last Year') {
                let currentYear = new Date().getFullYear(),
                    previousYear =  currentYear-1,
                    firstDay = convertDate(new Date(previousYear, 0,1 )),
                    lastDay = convertDate(new Date(previousYear, 11, 31))
                console.log(lastDay);
                frm.set_value('from_date',firstDay)
                frm.set_value('to_date',lastDay)
            } else if (frm.doc.preset === 'YTD') {
                let currentYear = new Date().getFullYear(),
                    firstDaySY = convertDate(new Date(currentYear, 0, 1)),
                    today = convertDate(new Date())
                frm.set_value('from_date',firstDaySY);
                frm.set_value('to_date',today);
                
            }
        }
    },
    
    });

    
    function convertDate(date) {
        let yyyy = date.getFullYear().toString(),
            mm = (date.getMonth()+1).toString(),
            dd  = date.getDate().toString(),
            mmChars = mm.split(''),
            ddChars = dd.split('')
    
        return yyyy + '-' + (mmChars[1]?mm:"0"+mmChars[0]) + '-' + (ddChars[1]?dd:"0"+ddChars[0]);
        }
  