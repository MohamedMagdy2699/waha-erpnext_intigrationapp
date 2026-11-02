
import base64
import json
import mimetypes
import re

import frappe
import requests
from frappe import _


def get_waha_config():
    """Load WAHA configuration from the current Frappe site."""

    config = frappe.get_conf()

    # Keep compatibility with the configuration key already in your setup.
    base_url = config.get("waha_base_url") or config.get("waha_url")
    api_key = config.get("waha_api_key")
    session = config.get("waha_session")

    if not all([base_url, api_key, session]):
        frappe.throw(
            _("WAHA configuration is incomplete. Check site configuration.")
        )

    return base_url.rstrip("/"), api_key, session


def normalize_phone(phone):
    """Normalize an Egyptian or international phone number."""

    digits = re.sub(r"\D", "", phone or "")

    if not digits:
        frappe.throw(_("Please provide a valid phone number."))

    # 01012345678 -> 201012345678
    if len(digits) == 11 and digits.startswith("01"):
        digits = "2" + digits

    if not 8 <= len(digits) <= 15:
        frappe.throw(_("Please check the phone number."))

    return f"{digits}@c.us"


def _waha_post(endpoint, payload, base_url, api_key):
    """Send a JSON request to WAHA."""

    response = requests.post(
        f"{base_url}/api/{endpoint}",
        headers={
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json=payload,
        timeout=60,
    )

    response.raise_for_status()

    return response.json() if response.content else {}


def send_text(phone, message):
    """Send a WhatsApp text message through WAHA."""

    if not message or not message.strip():
        frappe.throw(_("Message cannot be empty."))

    base_url, api_key, session = get_waha_config()

    payload = {
        "session": session,
        "chatId": normalize_phone(phone),
        "text": message.strip(),
    }

    try:
        result = _waha_post("sendText", payload, base_url, api_key)

        return {
            "success": True,
            "message": "Message accepted by WAHA.",
            "response": result,
        }

    except requests.RequestException:
        frappe.log_error(
            title="WAHA Message Delivery Error",
            message=frappe.get_traceback(),
        )

        frappe.throw(
            _("Could not send the WhatsApp message. Check the integration logs.")
        )


def _send_file(file_doc, chat_id, caption, base_url, api_key, session):
    """Send actual file bytes as a WhatsApp image or document."""

    file_path = file_doc.get_full_path()

    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()
    except OSError:
        frappe.throw(
            _("Could not read attachment {0}.").format(file_doc.file_name)
        )

    if not file_bytes:
        frappe.throw(
            _("Attachment {0} is empty.").format(file_doc.file_name)
        )

    mime_type = (
        file_doc.get("content_type")
        or mimetypes.guess_type(file_doc.file_name)[0]
        or "application/octet-stream"
    )

    # WAHA accepts Base64 data URIs for actual media/document content.
    encoded_file = base64.b64encode(file_bytes).decode("ascii")
    data_uri = f"data:{mime_type};base64,{encoded_file}"

    payload = {
        "session": session,
        "chatId": chat_id,
        "file": {
            "mimetype": mime_type,
            "filename": file_doc.file_name,
            "data": data_uri,
        },
        "caption": caption or "",
    }

    endpoint = "sendImage" if mime_type.startswith("image/") else "sendFile"

    return _waha_post(endpoint, payload, base_url, api_key)


@frappe.whitelist()
def send_whatsapp_message(customer, message=None, attachments=None):
    """Send a WhatsApp message to a Customer with optional attachments."""

    if frappe.session.user == "Guest":
        frappe.throw(_("Authentication is required."))

    if not customer:
        frappe.throw(_("Customer is required."))

    if not frappe.has_permission("Customer", "read", customer):
        frappe.throw(_("You do not have permission to read this Customer."))

    customer_doc = frappe.get_doc("Customer", customer)

    # Use the requested mobile_number field first.
    phone = (
        customer_doc.get("mobile_number")
        or customer_doc.get("mobile_no")
        or customer_doc.get("phone")
    )

    if not phone:
        frappe.throw(
            _("Please add a mobile number to this Customer before sending.")
        )

    message = (message or "").strip()

    if isinstance(attachments, str):
        try:
            attachments = json.loads(attachments)
        except (TypeError, ValueError):
            frappe.throw(_("Invalid attachments list."))

    attachments = attachments or []

    if not isinstance(attachments, list):
        frappe.throw(_("Attachments must be a list."))

    if not message and not attachments:
        frappe.throw(_("Enter a message or attach at least one file."))

    chat_id = normalize_phone(phone)
    base_url, api_key, session = get_waha_config()

    try:
        # Text-only message
        if not attachments:
            result = _waha_post(
                "sendText",
                {
                    "session": session,
                    "chatId": chat_id,
                    "text": message,
                },
                base_url,
                api_key,
            )

            return {
                "success": True,
                "sent_files": 0,
                "response": result,
            }

        sent_files = 0

        for index, file_url in enumerate(attachments):
            if not isinstance(file_url, str) or not file_url.strip():
                frappe.throw(_("Invalid attachment reference."))

            file_name = frappe.db.get_value(
                "File",
                {"file_url": file_url},
                "name",
            )

            if not file_name:
                frappe.throw(_("Uploaded attachment was not found."))

            file_doc = frappe.get_doc("File", file_name)

            # Security: only send files attached to this Customer.
            if (
                file_doc.attached_to_doctype != "Customer"
                or file_doc.attached_to_name != customer_doc.name
            ):
                frappe.throw(
                    _("File {0} is not attached to this Customer.").format(
                        file_doc.file_name
                    )
                )

            # Include message as the first attachment's caption.
            caption = message if index == 0 else ""

            _send_file(
                file_doc=file_doc,
                chat_id=chat_id,
                caption=caption,
                base_url=base_url,
                api_key=api_key,
                session=session,
            )

            sent_files += 1

        return {
            "success": True,
            "sent_files": sent_files,
            "message": _("Attachments accepted by WAHA."),
        }

    except requests.RequestException:
        frappe.log_error(
            title="WAHA Attachment Delivery Error",
            message=frappe.get_traceback(),
        )

        frappe.throw(
            _("WAHA could not send the message or attachment. Check Error Log.")
        )

