import json
import os
import re
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

import httpx
from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv()

MODELS = {
    "stt": "saaras:v4",
    "chat": "sarvam-105b",
    "tts": "bulbul:v4-flash",
}

client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"], timeout=30)


def _retry(call):
    for attempt in range(2):
        try:
            return call()
        except (httpx.TransportError, TimeoutError):
            if attempt:
                raise
            time.sleep(1)
        except Exception as exc:
            if getattr(exc, "status_code", None) not in (500, 502, 503, 504) or attempt:
                raise
            time.sleep(1)


def transcribe(audio_path):
    """Transcribe a short audio clip and return its detected language."""
    def call():
        with open(audio_path, "rb") as audio:
            return client.speech_to_text.transcribe(
                file=audio,
                model=MODELS["stt"],
                language_code="unknown",
            )

    response = _retry(call)
    return {"text": response.transcript, "language_code": response.language_code or "hi-IN"}


def read_document(image_path):
    """Read a document image through Sarvam Document AI and return its text."""
    path = Path(image_path)
    content_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"

    def submit():
        with path.open("rb") as image:
            return client.doc_ai.parse(
                file=[(path.name, image, content_type)],
                language="en-IN",
                content_type="printed",
            )

    job = _retry(submit)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        status = _retry(lambda: client.doc_ai.get_status(job_id=job.job_id))
        state = status.status.lower()
        if state in {"completed", "partially_completed"}:
            break
        if state in {"failed", "rejected"}:
            raise RuntimeError(f"Sarvam Vision job {state}")
        time.sleep(2)
    else:
        raise TimeoutError("Sarvam Vision did not finish within 60 seconds")

    download = _retry(lambda: client.doc_ai.get_download_url(job_id=job.job_id))
    with tempfile.TemporaryDirectory() as temp_dir:
        archive_path = Path(temp_dir) / "result.zip"
        _retry(lambda: urllib.request.urlretrieve(download.url, archive_path))
        with zipfile.ZipFile(archive_path) as archive:
            names = [name for name in archive.namelist() if not name.endswith("/")]
            candidates = [name for name in names if Path(name).suffix.lower() in {".md", ".html", ".txt", ".json"}]
            if not candidates:
                raise RuntimeError("Sarvam Vision returned no readable document output")
            return archive.read(candidates[0]).decode("utf-8", errors="replace")


def chat_json(system_prompt, user_prompt):
    """Return a JSON object from Sarvam-105B, retrying once if needed."""
    current_prompt = user_prompt
    for attempt in range(2):
        response = _retry(lambda: client.chat.completions(
            model=MODELS["chat"],
            temperature=0,
            max_tokens=2048,
            reasoning_effort="low",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": current_prompt},
            ],
        ))
        content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            if attempt:
                raise ValueError("Sarvam returned no visible JSON content")
            current_prompt += "\nReturn valid JSON only, with no reasoning or explanation."
            continue
        text = content.strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
        try:
            result = json.loads(text)
            if not isinstance(result, dict):
                raise ValueError("Expected a JSON object")
            return result
        except (json.JSONDecodeError, ValueError) as exc:
            if attempt:
                raise ValueError("Sarvam returned invalid JSON twice") from exc
            current_prompt += "\nReturn valid JSON only."


def speak(text, language_code):
    """Create a WAV file with Bulbul and return its path."""
    if language_code not in {"hi-IN", "bn-IN", "en-IN", "gu-IN", "kn-IN", "ml-IN", "mr-IN", "od-IN", "pa-IN", "ta-IN", "te-IN"}:
        language_code = "hi-IN"
    speakers = {
        "hi-IN": "shubh_hi_customer",
        "bn-IN": "arnab_bn_conversation",
        "en-IN": "simran_en_customer",
        "gu-IN": "pooja_gu_conversational",
        "kn-IN": "chaitra_kn_conversation",
        "mr-IN": "ishita_mr_conversational",
        "pa-IN": "anand_pa_conversation",
        "ta-IN": "gokul_ta_narration",
        "te-IN": "kavitha_te_conversation",
    }
    model = "bulbul:v3" if language_code in {"ml-IN", "od-IN"} else MODELS["tts"]
    speaker = "shubh" if model == "bulbul:v3" else speakers.get(language_code, "shubh_hi_customer")
    response = _retry(lambda: client.text_to_speech.convert(
        text=text[:2500],
        language_code=language_code,
        model=model,
        speaker=speaker,
        output_audio_codec="wav",
    ))
    output = Path(tempfile.gettempdir()) / f"sach-check-{time.time_ns()}.wav"
    output.write_bytes(__import__("base64").b64decode(response.audios[0]))
    return str(output)
