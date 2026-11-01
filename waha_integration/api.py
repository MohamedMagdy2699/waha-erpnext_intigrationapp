import re

import frappe
import requests
from frappe import _


def get_waha_config():
    """Load WAHA configuration from the current Frappe site."""

    config = frappe.get_conf()

    base_url = config.get("waha_base_url")
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

    # Convert Egyptian local mobile format, e.g. 01012345678
    # to international format, e.g. 201012345678.
    if len(digits) == 11 and digits.startswith("01"):
        digits = "2" + digits

    if not 8 <= len(digits) <= 15:
        frappe.throw(_("Please check the phone number."))

    return f"{digits}@c.us"


def send_text(phone, message):
    """Send a WhatsApp text message through WAHA."""

    if not isinstance(message, str) or not message.strip():
        frappe.throw(_("Message cannot be empty."))

    base_url, api_key, session = get_waha_config()

    payload = {
        "session": session,
        "chatId": normalize_phone(phone),
        "text": message.strip(),
    }

    try:
        response = requests.post(
            f"{base_url}/api/sendText",
            headers={
                "X-Api-Key": api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
            timeout=20,
        )

        response.raise_for_status()

        frappe.logger("waha_integration").info(
            "WAHA accepted an outgoing message."
        )

        return {
            "success": True,
            "message": "Message accepted by WAHA.",
            "response": response.json()
            if response.content
            else {},
        }

    except requests.RequestException:
        frappe.log_error(
            title="WAHA Message Delivery Error",
            message=frappe.get_traceback(),
        )

        frappe.throw(
            _("Could not send the WhatsApp message. Check the integration logs.")
        )


@frappe.whitelist()
def send_whatsapp_message(phone, message):
    """Authenticated Frappe API endpoint for sending WhatsApp messages."""

    if frappe.session.user == "Guest":
        frappe.throw(_("Authentication is required."))

    if not frappe.has_permission("Customer", "read"):
        frappe.throw(_("You do not have permission to use this integration."))

    return send_text(phone, message)
