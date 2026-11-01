from pathlib import Path

from sarvam_client import chat_json, read_document, speak, transcribe

sample = Path(__file__).parent / "assets" / "sample_invoice.jpg"

audio_path = speak("The invoice total is four thousand five hundred rupees.", "en-IN")
transcript = transcribe(audio_path)
document_text = read_document(sample)
json_result = chat_json("Return a JSON object with the key ok set to true.", "Return the requested result.")

print(f"transcribe: {transcript['text']}")
print(f"read_document: {document_text[:180].replace(chr(10), ' ')}")
print(f"chat_json: {json_result}")
print(f"speak: WAV created at {audio_path}")
