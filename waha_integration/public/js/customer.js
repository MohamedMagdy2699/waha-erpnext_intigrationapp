frappe.ui.form.on("Customer", {
    refresh(frm) {
        if (frm.is_new()) return;

        frm.add_custom_button(__("Send WhatsApp"), function () {
            const dialog = new frappe.ui.Dialog({
                title: __("Send WhatsApp Message"),
                fields: [
                    {
                        fieldname: "phone",
                        label: __("WhatsApp Number"),
                        fieldtype: "Data",
                        default: frm.doc.mobile_no || frm.doc.phone || "",
                        reqd: 1
                    },
                    {
                        fieldname: "message",
                        label: __("Message"),
                        fieldtype: "Small Text",
                        default: __("Hello {0}, this is a message from our accounting office.",
                            [frm.doc.customer_name || frm.doc.name]),
                        reqd: 1
                    }
                ],
                primary_action_label: __("Send"),
                primary_action(values) {
                    frappe.call({
                        method: "waha_integration.api.send_whatsapp_message",
                        args: {
                            phone: values.phone,
                            message: values.message
                        },
                        freeze: true,
                        freeze_message: __("Sending WhatsApp message..."),
                        callback(response) {
                            if (response.message && response.message.success) {
                                frappe.show_alert({
                                    message: __("WhatsApp message sent successfully"),
                                    indicator: "green"
                                });
                                dialog.hide();
                            }
                        }
                    });
                }
            });

            dialog.show();
        });
    }
});
