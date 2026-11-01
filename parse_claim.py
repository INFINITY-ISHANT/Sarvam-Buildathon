from datetime import datetime
from zoneinfo import ZoneInfo

from sarvam_client import chat_json


def parse_claim(transcript):
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()
    system = (
        "The user is speaking about a payment or invoice, possibly in Hindi, Tamil, or a code-mixed language. "
        "Extract ONLY what they actually said. Return ONLY JSON with keys amount, date, vendor, invoice_number, "
        "gst_amount, gst_included. Convert spoken numbers to digits, for example 'saade chaar hazaar' is 4500. "
        f"Convert dates to ISO using {today} as the current date if none is stated. Use null for anything they did not mention. "
        "Never fill in a value they did not say."
    )
    return chat_json(system, transcript)
