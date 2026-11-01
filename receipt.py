import hashlib
import json
from pathlib import Path


def make_receipt(image_path, doc_json):
    image_hash = hashlib.sha256(Path(image_path).read_bytes()).hexdigest()
    json_hash = hashlib.sha256(json.dumps(doc_json, sort_keys=True).encode("utf-8")).hexdigest()
    receipt_id = hashlib.sha256((image_hash + json_hash).encode("utf-8")).hexdigest()[:16]
    return {"image_hash": image_hash, "json_hash": json_hash, "receipt_id": receipt_id}
