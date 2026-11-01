# Sach Check

Say it. We check it against the document.

Upload a one-page invoice or receipt, speak or type a claim, and get a field-by-field verdict. Matching is deterministic Python; Sarvam extracts and explains.

The included demo invoice is synthetic. A local `assets/invoice.png` takes precedence when present, but that personal file is ignored by Git.

## Run locally

1. Install Python 3.10 or newer and the packages in `requirements.txt`.
2. Add your key to `.env` as `SARVAM_API_KEY=...`.
3. Run `python app.py`.

## Deploy on Vercel

Import this repository into Vercel, set the `SARVAM_API_KEY` environment variable in Project Settings, then deploy. The app exports its Gradio ASGI app through `index.py` for Vercel's Python runtime.

Vercel Functions have a 4.5 MB request body limit. Keep the one-page photo and audio clip small. Local invoice extraction is cached in `.cache`; Vercel's cache is temporary.

## Demo

1. Click **Load demo invoice**.
2. Type or speak a true claim: “Maine 4,500 ka payment kiya tha 12 October 2026 ko, GST ke saath.”
3. Change the amount or date and run it again. The matching field should show **MISMATCH**.
4. The LLM extracts and explains; the comparison itself is deterministic and auditable.
