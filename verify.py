import re
from dateutil.parser import parse as parse_date
from rapidfuzz.fuzz import token_set_ratio


def verify(claim, doc):
    fields = []
    for field in ("amount", "date", "vendor", "invoice_number", "gst_amount", "gst_included"):
        claimed, found = claim.get(field), doc.get(field)
        if claimed is None:
            continue
        note = ""
        if found is None:
            verdict = "NOT_FOUND"
        elif field == "amount":
            difference = abs(float(claimed) - float(found))
            verdict = "MATCH" if difference <= 1 else "MISMATCH"
            if verdict == "MISMATCH":
                note = f"Difference: ₹{difference:.2f}"
        elif field == "gst_amount":
            difference = abs(float(claimed) - float(found))
            verdict = "MATCH" if difference <= 1 else "MISMATCH"
            if verdict == "MISMATCH":
                note = f"Difference: ₹{difference:.2f}"
        elif field == "date":
            days = abs((parse_date(str(claimed)).date() - parse_date(str(found)).date()).days)
            verdict = "MATCH" if days == 0 else "MISMATCH"
            if days:
                note = f"{days} days apart"
        elif field == "vendor":
            score = token_set_ratio(str(claimed), str(found))
            verdict = "MATCH" if score >= 80 else "MISMATCH"
            if verdict == "MISMATCH":
                note = f"Name similarity: {score}%"
        elif field == "invoice_number":
            clean = lambda value: re.sub(r"[\s-]", "", str(value).upper())
            verdict = "MATCH" if clean(claimed) == clean(found) else "MISMATCH"
        else:
            verdict = "MATCH" if bool(claimed) == bool(found) else "MISMATCH"
        fields.append({"field": field, "claimed": claimed, "found": found, "verdict": verdict, "note": note})

    verdicts = [item["verdict"] for item in fields]
    if "MISMATCH" in verdicts:
        overall = "DISPUTED"
    elif "MATCH" in verdicts:
        overall = "VERIFIED"
    else:
        overall = "INCONCLUSIVE"
    return {"overall": overall, "fields": fields}
