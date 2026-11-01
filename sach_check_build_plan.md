# Sach Check: build plan

I have 45 minutes total at a hackathon hosted by Sarvam. Build this exactly as specced, in order, and keep it small. A working demo beats a complete one. Do not add features that are not in this file.

## 1. What it does

User uploads a photo of an invoice or receipt, then speaks a claim about it in their own language (Hindi, Tamil, Hinglish, etc). Example claim: "Maine 4,500 ka payment kiya tha 12 October ko, GST ke saath."

The app:
1. Extracts the fields from the document photo (Sarvam Vision).
2. Transcribes the spoken claim (Saaras).
3. Turns the claim into structured fields (Sarvam-105B).
4. Compares claim vs document field by field and gives a verdict per field: MATCH, MISMATCH, NOT_FOUND.
5. Speaks the verdict back in the user's language (Bulbul).
6. Shows a tamper-evident receipt ID (SHA-256 of the image plus the extracted JSON).

Demo moment: say one true claim, then one false claim (wrong amount or date), and show the app catching it with the exact field highlighted.

## 2. Hard constraints

- Python 3.10+, single repo, runs with `python app.py`.
- UI: Gradio only. No separate frontend.
- Deploy target: Hugging Face Spaces (Gradio SDK). Fallback: `demo.launch(share=True)` for an instant public link.
- API key is read from env var `SARVAM_API_KEY`. Never hardcode it. Never commit `.env`.
- Total build budget is 45 minutes, so prefer the simplest thing that works.

## 3. Important: do not guess the Sarvam API

I am not certain of the exact model IDs, request shapes, or whether Sarvam Vision is sync or async. Before writing any real code:

1. Read the docs at https://docs.sarvam.ai (speech to text, text to speech, chat completions, and the Sarvam Vision / document intelligence page).
2. Check whether the official Python SDK `sarvamai` covers all four calls. Use it if so. Use plain `requests` for anything it does not cover.
3. Put EVERY Sarvam call behind one file, `sarvam_client.py`, with four functions (see section 6). The rest of the app must only call those four functions. That way if an API detail is wrong, only one file changes.
4. Model names go in a `MODELS` dict at the top of `sarvam_client.py` so I can swap them in one place. Use the latest versions the docs list for Saaras (speech to text), Bulbul (text to speech), and Sarvam-105B (chat). If you cannot confirm a model ID from the docs, stop and ask me instead of inventing one.

## 4. Repo layout

```
sach-check/
  app.py               # gradio UI + pipeline wiring
  sarvam_client.py     # the only file that talks to Sarvam
  extract_doc.py       # image -> structured doc fields
  parse_claim.py       # transcript -> structured claim fields
  verify.py            # deterministic comparison logic
  receipt.py           # hashing and receipt id
  assets/
    sample_invoice.jpg # a clean sample invoice for demo + fallback
    sample_vision.json # cached Vision output for the sample (fallback)
  smoke_test.py        # calls each Sarvam function once
  requirements.txt
  README.md            # includes HF Spaces frontmatter (section 10)
  .gitignore           # .env, .cache/, __pycache__/
```

requirements.txt: `gradio`, `sarvamai`, `rapidfuzz`, `python-dateutil`, `pillow`, `python-dotenv`, `requests`.

## 5. Data shapes

Both the document and the claim are normalised into the same dict so comparison is trivial:

```json
{
  "amount": 4500.0,
  "date": "2026-10-12",
  "vendor": "Sharma Traders",
  "invoice_number": "INV-2041",
  "gst_amount": 686.44,
  "gst_included": true
}
```

Any field can be `null` if absent. Amount is a float in rupees. Date is ISO `YYYY-MM-DD`.

Verification output:

```json
{
  "overall": "VERIFIED | DISPUTED | INCONCLUSIVE",
  "fields": [
    {"field": "amount", "claimed": 4500.0, "found": 4500.0, "verdict": "MATCH", "note": ""},
    {"field": "date", "claimed": "2026-10-12", "found": "2026-10-14", "verdict": "MISMATCH", "note": "2 days apart"}
  ],
  "spoken_summary": "text in the user's language",
  "language_code": "hi-IN"
}
```

## 6. Module specs

### sarvam_client.py

Four functions, each with a short docstring and sensible timeouts (30s, Vision may need longer):

- `transcribe(audio_path) -> {"text": str, "language_code": str}`
  Saaras speech to text. Return the detected language code if the API gives one, otherwise default `"hi-IN"`.
- `read_document(image_path) -> str`
  Sarvam Vision on the uploaded image. Return the raw extracted text/markdown. If the API is async (job then poll), handle the polling inside this function and expose a simple blocking call. Add a 60s overall timeout.
- `chat_json(system_prompt, user_prompt) -> dict`
  Sarvam-105B chat completion, temperature 0 or lowest allowed. Instruct it to return JSON only, then strip code fences and `json.loads`. If parsing fails, retry once with "Return valid JSON only." appended. Raise a clear error if it fails twice.
- `speak(text, language_code) -> bytes_or_path`
  Bulbul text to speech. Return a wav file path that Gradio's `gr.Audio` can play. Pick a default speaker from the docs. If the language is unsupported, fall back to `hi-IN`.

All four load the key with `os.environ["SARVAM_API_KEY"]` after `load_dotenv()`.

### extract_doc.py

`extract_document(image_path) -> dict`
1. Hash the image bytes (sha256). If `.cache/<hash>.json` exists, return it (this makes repeat demos instant).
2. Call `read_document`.
3. Call `chat_json` with a system prompt like: "You extract fields from Indian invoices and receipts. Return ONLY JSON with keys: amount (total payable as a number in INR), date (ISO YYYY-MM-DD), vendor, invoice_number, gst_amount, gst_included (true if the total already includes GST). Use null for anything not present. Do not guess." and the Vision text as the user prompt.
4. Normalise types (amount to float, strip commas and the rupee sign) and write the cache file.
5. If the whole thing throws and the image is the bundled sample, load `assets/sample_vision.json` instead and log that the fallback was used.

### parse_claim.py

`parse_claim(transcript) -> dict`
Same JSON shape as above. System prompt: "The user is speaking about a payment or invoice, possibly in Hindi, Tamil, or a code-mixed language. Extract ONLY what they actually said. Return ONLY JSON with the same keys as the schema. Convert spoken numbers to digits ('saade chaar hazaar' is 4500). Convert dates to ISO using the current year if none is stated. Use null for anything they did not mention. Never fill in a value they did not say."

Pass today's date into the prompt so "kal" and "parso" resolve.

### verify.py

All comparison is deterministic Python. Do NOT ask the LLM to decide match or mismatch; only use it for extraction and for writing the spoken summary.

`verify(claim, doc) -> dict` with these rules, per field, skipping any field where the claim value is null:
- If the doc value is null: `NOT_FOUND`.
- amount: MATCH if `abs(a - b) <= 1.0`, else MISMATCH with note showing the difference.
- date: parse both with `dateutil`, MATCH if equal, else MISMATCH with note "N days apart".
- vendor: `rapidfuzz.fuzz.token_set_ratio >= 80` is MATCH, else MISMATCH.
- invoice_number: normalise (uppercase, strip spaces, dashes) then exact compare.
- gst_included: compare booleans. If the claim says GST included and the doc does not, MISMATCH.

Overall: any MISMATCH means `DISPUTED`. Else if at least one MATCH and no MISMATCH means `VERIFIED`. Else `INCONCLUSIVE`.

Then one `chat_json` call (or plain chat) to write `spoken_summary`: 1 to 3 short sentences, in the language of the transcript, naming each mismatch plainly with both values. Keep numbers as digits. If this call fails, fall back to a simple English template so the demo never breaks.

### receipt.py

`make_receipt(image_path, doc_json) -> dict`
- `image_hash = sha256(image bytes)`
- `json_hash = sha256(json.dumps(doc_json, sort_keys=True))`
- `receipt_id = sha256(image_hash + json_hash)[:16]`
Return all three. Display them in the UI with a one-line explanation: "Change a single pixel or field and this ID changes."

### app.py

Gradio Blocks layout:
- Left column: `gr.Image(type="filepath")` for the document, `gr.Audio(sources=["microphone","upload"], type="filepath")` for the claim, a `gr.Textbox` labelled "Or type your claim" (fallback if the mic or STT fails), and a "Check" button. Add a "Load demo invoice" button that fills in the sample image.
- Right column, in order: overall verdict as big markdown (green VERIFIED, red DISPUTED, amber INCONCLUSIVE), a `gr.Dataframe` of the per-field results, transcript textbox, extracted document JSON (`gr.JSON`), spoken verdict `gr.Audio` (autoplay), receipt ID and hashes.
- Use a clean title and one subtitle line: "Say it. We check it against the document."

Pipeline function `run(image, audio, typed_claim)`:
1. Validate inputs, return friendly messages if the image or claim is missing.
2. Transcript = typed claim if given, else `transcribe(audio)`.
3. `doc = extract_document(image)`, `claim = parse_claim(transcript)`.
4. `result = verify(claim, doc)`.
5. `audio_out = speak(result["spoken_summary"], language_code)`; if TTS fails, return None for audio but still show text.
6. `receipt = make_receipt(image, doc)`.
Wrap each stage in try/except and show which stage failed in the UI instead of crashing.

## 7. Build order (with time boxes and acceptance checks)

Do these in order. Do not start a phase until the previous one passes its check.

| Phase | Time | Task | Done when |
|---|---|---|---|
| 0 | 0 to 8 min | Project setup, `.env`, install deps, write `sarvam_client.py`, write `smoke_test.py` that calls transcribe, read_document, chat_json, speak once each with tiny inputs | `python smoke_test.py` prints a result for all four, or a clear error naming which one failed |
| 1 | 8 to 20 min | `extract_doc.py`, `parse_claim.py`, `verify.py` as a plain script run on the sample invoice and a typed claim | Script prints the verification JSON correctly for one true claim and one false claim |
| 2 | 20 to 30 min | `receipt.py` and `app.py` with the full UI wired up | Full flow works locally in the browser with mic input |
| 3 | 30 to 38 min | Deploy to Hugging Face Spaces (section 10), set the secret | Public URL works end to end |
| 4 | 38 to 45 min | Test with 2 real invoices, fix the worst bug only, write demo script into README | Demo script runs clean twice in a row |

If a phase runs over by more than 3 minutes, cut scope from the cut list below instead of extending the time.

## 8. Cut list (drop in this order if time runs short)

1. Receipt hashing UI (keep the code, hide the section).
2. Spoken output (show text verdict only).
3. Fuzzy vendor and invoice number checks (compare amount and date only).
4. Live Vision call (always use the cached sample output).

Never cut: transcribe, document extraction, deterministic verify, the UI.

## 9. Error handling rules

- Every Sarvam call has a timeout and one retry on network errors.
- No bare `except:`. Catch specific errors where possible and surface a short message in the UI.
- Log which stage is running with plain `print` (stage name plus seconds taken) so I can see slow steps during the demo.
- Show a spinner or status text while running. Vision can be slow.

## 10. Deployment (Hugging Face Spaces)

README.md must start with this frontmatter:

```
---
title: Sach Check
emoji: ✅
colorFrom: green
colorTo: blue
sdk: gradio
app_file: app.py
pinned: false
---
```

Steps:
1. Create a new Space on huggingface.co (SDK: Gradio, public).
2. In Space Settings, add a secret named `SARVAM_API_KEY`.
3. Push the repo (git push to the Space remote, or upload files in the web UI).
4. Wait for the build, open the URL, run the demo flow once.

`app.py` should end with `demo.launch()` and read the port and host defaults from Gradio, nothing custom. Include `assets/sample_invoice.jpg` in the repo so the Space has it.

Fast fallback if the Space build fails: run locally with `demo.launch(share=True)` and use that temporary public link.

## 11. Demo script (put in README)

1. Open the app, click "Load demo invoice".
2. Speak a true claim in Hindi that matches the invoice. Show VERIFIED, point at the field table and the receipt ID.
3. Speak a false claim (change the amount or date). Show DISPUTED with the exact field called out, and play the spoken verdict in Hindi.
4. One line on the design choice: the LLM only extracts and explains, the comparison itself is deterministic code, so the verdicts are auditable and don't hallucinate.

## 12. Code style rules for the agent

- Write plain, readable code like a student who knows Python well would. Short functions, clear names, comments only where something is non obvious.
- Do not add comments, docstrings, README text, commit messages, or UI copy that mention AI tools, assistants, or code generation. Nothing should say the code was generated.
- No em dashes anywhere, in code, comments, strings, or docs. Use commas, colons, or hyphens.
- Keep the whole project under roughly 400 lines of Python.
- Use `git init` and make small normal commits ("add sarvam client", "wire up gradio ui").

## 13. Report back

When each phase is done, tell me in 2 to 3 lines what works, what you assumed, and anything in the Sarvam API that did not match what I described, before moving on.
