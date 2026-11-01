# Sach Check

**Say it. We check it against the document.**

Sach Check is a small invoice and receipt verification app. Add a one-page document, then speak or type a payment claim. The app extracts details from the document, parses the claim, and compares the values field by field. It shows a verdict, a short spoken summary, and a receipt containing hashes of the document and extracted fields.

The comparison is performed by Python rules so matching values are auditable. Sarvam AI provides document reading, speech transcription, claim parsing, spoken-summary generation, and text-to-speech. Sach Check checks what the document says; it does not contact a bank or payment processor to independently confirm that a real-world payment occurred.

## Features

- Upload an invoice or receipt image, or use the image preloaded by the app.
- Enter a claim in text or record/upload speech.
- Extract amount, date, vendor, invoice number, GST amount, GST inclusion, and payment status when stated.
- Compare claimed and extracted fields with deterministic matching rules.
- See `VERIFIED`, `DISPUTED`, or `INCONCLUSIVE`, plus a field-by-field explanation.
- Hear a brief spoken summary when text-to-speech succeeds.
- Create a receipt ID from the image hash and extracted-field hash.

## Requirements

- Python 3.10 or newer
- A Sarvam AI API key with access to the APIs used by the app
- Internet access while using the Sarvam-powered features

The Python dependencies are listed in [`requirements.txt`](requirements.txt). The app uses Gradio for its interface and the Sarvam Python SDK for API calls.

## Run locally

Open PowerShell in the project directory:

```powershell
cd "C:\Users\ishan\Desktop\Sarvam Hackathon\Sarvam-Buildathon"
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Create a `.env` file in the project root with your key:

```dotenv
SARVAM_API_KEY=your_key_here
```

Keep `.env` private. It is ignored by Git; do not paste the key into source code or commit it.

Start the app:

```powershell
python app.py
```

Open [http://127.0.0.1:7860](http://127.0.0.1:7860) in your browser. To restart after changing code, stop the running process with **Ctrl+C**, then run `python app.py` again.

## Use the app

1. Use the preloaded invoice or choose a one-page invoice/receipt image.
2. Type a claim or record/upload a spoken claim. For example: “Is this invoice paid?” or “I paid ₹4,500 on 12 October.”
3. Select **Check**.
4. Review the overall verdict and each field’s claimed value, invoice value, and match result.

`assets/sample_invoice.jpg` is the included synthetic invoice. If `assets/invoice.png` exists locally, the app uses it as its initial image instead. That local file is ignored by Git and is not included in the repository.

## How it works

1. **Document reading:** Sarvam Document AI reads text from the invoice image. Sach Check extracts structured invoice fields from that text and caches the result locally in `.cache/`.
2. **Speech transcription (when used):** Sarvam Saaras converts the submitted audio to text and detects its language.
3. **Claim parsing:** Sarvam-105B turns the text claim into structured fields, including a payment-status value when the user asks about payment status.
4. **Verification:** Python compares amounts, dates, names, invoice numbers, GST values, and payment status. A missing value is not treated as a match.
5. **Summary and audio:** Sarvam-105B writes a short spoken summary, and Sarvam Bulbul generates audio. If audio generation fails, the text result is still shown.
6. **Receipt:** Sach Check hashes the invoice image and extracted fields and displays a receipt ID. The hash helps detect changes to those inputs; it is not a payment-provider receipt or proof of settlement.

The Sarvam client reads `SARVAM_API_KEY` from the process environment, with `.env` loaded for local runs. The configured models are Saaras v4 for speech transcription, Sarvam-105B for structured chat, and Bulbul v4 Flash for speech generation. Document reading uses Sarvam Document AI.

## Project files

- `app.py` — Gradio interface and end-to-end workflow
- `sarvam_client.py` — Sarvam SDK calls for document reading, chat, speech transcription, and speech generation
- `extract_doc.py` — invoice field extraction, normalization, payment-status detection, and local cache
- `parse_claim.py` — converts the user's text into structured claim fields
- `verify.py` — deterministic field comparisons and overall verdict
- `receipt.py` — creates the image, fields, and receipt hashes
- `assets/sample_invoice.jpg` — synthetic example invoice
- `assets/sample_vision.json` — structured fallback data for the included sample
- `index.py` — exports the Gradio ASGI app for Vercel

## Configuration and data

- `.env` stores the local API key and is excluded from Git.
- `assets/invoice.png` is an optional local invoice and is excluded from Git.
- `.cache/` stores local document extraction results and is excluded from Git.
- Uploaded images and audio are sent to Sarvam when their corresponding features are used. Use documents you are authorized to process.

## Deploy on Vercel

Live deployment: [Sach Check](https://sarvambuildathon-72nvxm5wy-ishants-projects-2a09f545.vercel.app/)

The repository includes `index.py` as the Python app entry point. When importing the repository into Vercel, configure `SARVAM_API_KEY` in the project's environment variables for the environments where the app will run. Do not commit `.env` or the API key. The deployed app needs network access to Sarvam APIs; deployment behavior should be checked in Vercel's build and function logs.

## Troubleshooting

- **Missing API key:** confirm `.env` is in the project root and contains `SARVAM_API_KEY=...`; restart the app after changing it.
- **Document extraction failed:** use a clear, upright, one-page image and confirm the Sarvam key has access to Document AI. Check the terminal running `python app.py` for the stage and error type.
- **Speech or audio is unavailable:** try typing the claim first. Text verification does not require a microphone; spoken output is optional.
- **No claim fields were checked:** state the value to verify, for example “Is this invoice paid?” or “The total is ₹4,500.”
- **Old extraction appears:** the local cache is under `.cache/`. It is safe to remove that folder to make the app extract documents again, though this requires another Sarvam document-reading call.

## License

No license file is currently included. Add a license before redistributing the project if you want to grant reuse rights.
