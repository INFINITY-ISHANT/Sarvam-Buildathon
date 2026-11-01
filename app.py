import json
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
    try:
        data = chat_json(
            "Write 1 to 3 short sentences in the language of the user's transcript. Name each mismatch plainly with both values. Keep numbers as digits. Return JSON with one key: spoken_summary.",
            json.dumps({"transcript": transcript, "verification": result}, ensure_ascii=False),
        )
        return str(data["spoken_summary"])
    except Exception:
        mismatches = [f"{row['field']}: claimed {row['claimed']}, found {row['found']}" for row in result["fields"] if row["verdict"] != "MATCH"]
        return "Claim checked. " + ("; ".join(mismatches) if mismatches else result["overall"].title() + ".")


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
