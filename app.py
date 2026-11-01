import json
import re
import time
from pathlib import Path

import gradio as gr

from extract_doc import extract_document
from parse_claim import parse_claim
from receipt import make_receipt
from sarvam_client import chat_json, speak, transcribe
from verify import verify

ROOT = Path(__file__).parent
USER_INVOICE = ROOT / "assets" / "invoice.png"
SAMPLE_IMAGE = str(USER_INVOICE if USER_INVOICE.exists() else ROOT / "assets" / "sample_invoice.jpg")


def _stage(name, work):
    started = time.monotonic()
    try:
        return work()
    finally:
        print(f"{name}: {time.monotonic() - started:.1f}s")


def _summary(result, transcript):
    labels = {
        "amount": "amount",
        "date": "date",
        "vendor": "vendor",
        "invoice_number": "invoice number",
        "gst_amount": "GST amount",
        "gst_included": "whether GST is included",
        "payment_status": "payment status",
    }

    def has_value(value):
        return value is not None and str(value).strip().lower() not in {"", "null", "none", "unknown"}

    comparisons = [
        {
            "field": labels.get(row["field"], "invoice detail"),
            "claimed": row["claimed"],
            "invoice": row["found"],
            "matches": row["verdict"] == "MATCH",
        }
        for row in result["fields"]
        if has_value(row.get("claimed")) and has_value(row.get("found"))
    ]

    def fallback():
        status = next((row for row in result["fields"] if row["field"] == "payment_status"), None)
        if status and has_value(status.get("found")):
            invoice_status = str(status["found"]).replace("_", " ").lower()
            if status["verdict"] == "MATCH":
                return f"The invoice confirms the payment status is {invoice_status}."
            claim_status = str(status["claimed"]).replace("_", " ").lower()
            return f"The invoice says {invoice_status}, but the claim says {claim_status}."
        if result["overall"] == "VERIFIED":
            return "The claim matches the invoice."
        if result["overall"] == "DISPUTED":
            mismatches = [row for row in result["fields"] if row["verdict"] == "MISMATCH" and has_value(row.get("found"))]
            if mismatches:
                row = mismatches[0]
                label = labels.get(row["field"], "invoice detail")
                return f"The claimed {label} is {row['claimed']}; the invoice shows {row['found']}."
        return "I couldn't confirm this claim from the invoice."

    try:
        data = chat_json(
            "Write one brief, natural sentence for speech in the language of the user's transcript. Use only the supplied comparisons. "
            "Never mention JSON, field names, underscores, null, none, unknown, or missing values. "
            "Do not list technical details. If payment status matches, say plainly that the invoice confirms it. "
            "If the comparisons list is empty, say you could not confirm the claim from the invoice. "
            "Return JSON with one key: spoken_summary.",
            json.dumps({"transcript": transcript, "overall": result["overall"], "comparisons": comparisons}, ensure_ascii=False),
        )
        summary = str(data["spoken_summary"]).strip()
        if not summary or re.search(r"payment[_\s-]*null|\bnull\b|\bnone\b|\bunknown\b|[_{}\[\]]", summary, re.IGNORECASE):
            return fallback()
        return summary
    except Exception:
        return fallback()


def run(image, audio, typed_claim):
    if not image:
        return "### Add an invoice image", [], "", {}, None, "", "Choose a one-page invoice image to begin."
    if not typed_claim and not audio:
        return "### Add a claim", [], "", {}, None, "", "Speak a claim or type it in the box."

    stage = "transcribe"
    try:
        if typed_claim and typed_claim.strip():
            transcript, language_code = typed_claim.strip(), "hi-IN"
        else:
            speech = _stage(stage, lambda: transcribe(audio))
            transcript, language_code = speech["text"], speech["language_code"]

        stage = "document extraction"
        document = _stage(stage, lambda: extract_document(image))
        stage = "claim parsing"
        claim = _stage(stage, lambda: parse_claim(transcript))
        stage = "verification"
        result = _stage(stage, lambda: verify(claim, document))
        stage = "spoken summary"
        summary = _stage(stage, lambda: _summary(result, transcript))
        stage = "speech generation"
        try:
            audio_out = _stage(stage, lambda: speak(summary, language_code))
        except Exception:
            audio_out = None
        stage = "receipt"
        receipt = _stage(stage, lambda: make_receipt(image, document))

        rows = [[row["field"], row["claimed"], row["found"], row["verdict"], row["note"]] for row in result["fields"]]
        icon = {"VERIFIED": "✅", "DISPUTED": "❌", "INCONCLUSIVE": "⚠️"}[result["overall"]]
        verdict = f"## {icon} {result['overall']}"
        receipt_text = (
            f"**Receipt ID:** `{receipt['receipt_id']}`\n\n"
            f"**Image SHA-256:** `{receipt['image_hash']}`\n\n"
            f"**Fields SHA-256:** `{receipt['json_hash']}`\n\n"
            "Change a single pixel or field and this ID changes."
        )
        return verdict, rows, transcript, document, audio_out, receipt_text, summary
    except Exception as exc:
        print(f"{stage} failed: {type(exc).__name__}")
        return f"### {stage.title()} failed", [], "", {}, None, "", f"{stage.title()} failed ({type(exc).__name__}). Try again or use a clearer one-page image."


def build_demo():
    with gr.Blocks(title="Sach Check") as demo:
        gr.Markdown("# Sach Check\nSay it. We check it against the document.")
        with gr.Row():
            with gr.Column():
                image = gr.Image(value=SAMPLE_IMAGE, type="filepath", label="One-page invoice or receipt")
                audio = gr.Audio(sources=["microphone", "upload"], type="filepath", label="Speak your claim")
                typed_claim = gr.Textbox(label="Or type your claim", placeholder="Maine 4,500 ka payment kiya tha 12 October ko")
                with gr.Row():
                    check = gr.Button("Check", variant="primary")
                    load_demo = gr.Button("Load demo invoice")
            with gr.Column():
                verdict = gr.Markdown("### Ready")
                fields = gr.Dataframe(
                    headers=["Field", "Claimed", "Found", "Verdict", "Note"],
                    datatype=["str", "str", "str", "str", "str"],
                    label="Field-by-field check",
                    interactive=False,
                )
                transcript = gr.Textbox(label="Claim transcript", interactive=False)
                document = gr.JSON(label="Extracted invoice fields")
                spoken = gr.Audio(label="Spoken verdict", autoplay=True, type="filepath")
                receipt = gr.Markdown(label="Tamper-evident receipt")
                status = gr.Markdown("Ready.")
        check.click(run, [image, audio, typed_claim], [verdict, fields, transcript, document, spoken, receipt, status])
        load_demo.click(lambda: SAMPLE_IMAGE, outputs=image)
    return demo


demo = build_demo()

if __name__ == "__main__":
    demo.launch()
