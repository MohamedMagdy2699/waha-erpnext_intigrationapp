
frappe.ui.form.on("Customer", {
    refresh(frm) {
        if (frm.is_new()) return;

        frm.add_custom_button(__("Send WhatsApp"), function () {

    // Fetch the number from Customer or its linked Contacts.
    frappe.call({
        method: "waha_integration.api.get_customer_whatsapp_number",
        args: {
            customer: frm.doc.name
        },
        freeze: true,
        freeze_message: __("Finding customer WhatsApp number..."),

        callback: function (r) {
            const customerNumber = r.message;

            if (!customerNumber) {
                frappe.msgprint({
                    title: __("Mobile Number Missing"),
                    message: __(
                        "No mobile number was found in the Customer or its linked Contacts."
                    ),
                    indicator: "orange"
                });
                return;
            }

            // Keep the existing dialog code below this line.
            const dialog = new frappe.ui.Dialog({
                title: __("Send WhatsApp Message"),
                size: "large",

                fields: [
                    {
                        fieldname: "phone",
                        label: __("WhatsApp Number"),
                        fieldtype: "Data",
                        default: customerNumber,
                        read_only: 1
                    },
                    {
                        fieldname: "message",
                        label: __("Message"),
                        fieldtype: "Small Text",
                        default: __("Hello {0}, this is a message from our accounting office.", [
                            frm.doc.customer_name || frm.doc.name
                        ])
                    },
                    {
                        fieldname: "attachments_html",
                        fieldtype: "HTML",
                        options: `
                            <div class="form-group">
                                <label class="control-label">
                                    ${__("Attachments")}
                                </label>

                                <input
                                    type="file"
                                    class="form-control"
                                    data-waha-attachments
                                    multiple
                                >

                                <p class="help-box">
                                    ${__("Select one or more files to send as actual WhatsApp attachments.")}
                                </p>

                                <div class="text-muted small" data-waha-file-list></div>
                            </div>
                        `
                    }
                ],

                primary_action_label: __("Send"),

                primary_action() {
                    const message = (dialog.get_value("message") || "").trim();

                    const fileInput = dialog.fields_dict.attachments_html
                        .$wrapper.find("[data-waha-attachments]")[0];

                    const selectedFiles = Array.from(fileInput.files || []);

                    if (!message && !selectedFiles.length) {
                        frappe.msgprint(
                            __("Enter a message or select at least one attachment.")
                        );
                        return;
                    }

                    const primaryButton = dialog.get_primary_btn();
                    primaryButton.prop("disabled", true);

                    frappe.dom.freeze(
                        __("Uploading attachments and sending WhatsApp...")
                    );

                    // Upload files to ERPNext, attached to this Customer.
                    const uploadFile = (file) => {
                        return new Promise((resolve, reject) => {
                            const formData = new FormData();

                            formData.append("file", file);
                            formData.append("is_private", "1");
                            formData.append("doctype", "Customer");
                            formData.append("docname", frm.doc.name);

                            const xhr = new XMLHttpRequest();

                            xhr.open("POST", "/api/method/upload_file");
                            xhr.withCredentials = true;

                            xhr.setRequestHeader("Accept", "application/json");

                            const csrfToken =
                                frappe.csrf_token || frappe.boot.csrf_token;

                            if (csrfToken) {
                                xhr.setRequestHeader(
                                    "X-Frappe-CSRF-Token",
                                    csrfToken
                                );
                            }

                            xhr.onload = () => {
                                let response;

                                try {
                                    response = JSON.parse(xhr.responseText);
                                } catch (error) {
                                    reject(
                                        new Error(
                                            __("Invalid response uploading {0}.", [
                                                file.name
                                            ])
                                        )
                                    );
                                    return;
                                }

                                if (
                                    xhr.status >= 200 &&
                                    xhr.status < 300 &&
                                    response.message?.file_url
                                ) {
                                    resolve(response.message.file_url);
                                } else {
                                    reject(
                                        new Error(
                                            __("Could not upload {0}.", [
                                                file.name
                                            ])
                                        )
                                    );
                                }
                            };

                            xhr.onerror = () => {
                                reject(
                                    new Error(
                                        __("Network error uploading {0}.", [
                                            file.name
                                        ])
                                    )
                                );
                            };

                            xhr.send(formData);
                        });
                    };

                    (async () => {
                        try {
                            const uploadedFileUrls = await Promise.all(
                                selectedFiles.map(uploadFile)
                            );

                            frappe.call({
                                method: "waha_integration.api.send_whatsapp_message",

                                args: {
                                    customer: frm.doc.name,
                                    message: message,
                                    attachments: JSON.stringify(
                                        uploadedFileUrls
                                    )
                                },

                                callback(response) {
                                    if (
                                        response.message &&
                                        response.message.success
                                    ) {
                                        frappe.show_alert({
                                            message: __(
                                                "WhatsApp sent successfully. {0} attachment(s) sent.",
                                                [
                                                    response.message.sent_files ||
                                                    0
                                                ]
                                            ),
                                            indicator: "green"
                                        });

                                        dialog.hide();
                                    }

                                    frappe.dom.unfreeze();
                                    primaryButton.prop("disabled", false);
                                },

                                error() {
                                    frappe.dom.unfreeze();
                                    primaryButton.prop("disabled", false);
                                }
                            });
                        } catch (error) {
                            frappe.dom.unfreeze();
                            primaryButton.prop("disabled", false);

                            frappe.msgprint({
                                title: __("Attachment Upload Failed"),
                                message: error.message,
                                indicator: "red"
                            });
                        }
                    })();
                }
            });

            dialog.show();

            // Display selected filenames.
            const fileInput = dialog.fields_dict.attachments_html
                .$wrapper.find("[data-waha-attachments]");

                        fileInput.on("change", function () {
                const names = Array.from(this.files || []).map(
                    file => file.name
                );

                dialog.fields_dict.attachments_html
                    .$wrapper.find("[data-waha-file-list]")
                    .text(
                        names.length
                            ? names.join(", ")
                            : __("No files selected")
                    );
               }); // End fileInput.on

        } // End callback
    }); // End frappe.call
}); // End add_custom_button
    } // End refresh
}); // End frappe.ui.form.on
