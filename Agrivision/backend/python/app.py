"""Flask: Agrivision static site + ML recommend + IoT SRC + meta."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, request, send_from_directory
from flask_cors import CORS

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT.parent / ".env")

SITE_ROOT = (ROOT.parent.parent).resolve()

from ml.predict import apply_arid_policy, merge_unique_top, predict_top_crops
from services.iot_sensors import (
    fuse_features,
    ingest_reading,
    latest_ingest,
    list_ingest,
    simulate_sensors,
)
from services.irrigation import attach_irrigation
from services.open_meteo import fetch_weather
from services.soilgrids import build_feature_row, fetch_soil_properties

app = Flask(__name__)
CORS(app)


def _ml_training_meta() -> dict[str, Any]:
    p = ROOT / "ml" / "models" / "model_meta.json"
    try:
        m = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {
        "note": m.get("note"),
        "training_source": m.get("training_source"),
        "training_rows": m.get("training_rows"),
        "holdout_rows": m.get("holdout_rows"),
        "feature_order": m.get("feature_order"),
        "metrics": m.get("metrics"),
        "val_accuracy_rf": m.get("val_accuracy_rf"),
        "val_accuracy_svm": m.get("val_accuracy_svm"),
        "val_accuracy_gb": m.get("val_accuracy_gb"),
        "val_accuracy_blend": m.get("val_accuracy_blend"),
        "feature_importance_rf": m.get("feature_importance_rf"),
        "feature_importance_gb": m.get("feature_importance_gb"),
        "blend_weights": m.get("blend_weights"),
        "classes": m.get("classes"),
    }


def _safe_site_file(relative: str) -> Optional[Path]:
    if not relative:
        return None
    rel = relative.replace("\\", "/").strip("/")
    if rel != relative.strip():
        return None
    parts = [p for p in rel.split("/") if p and p != "."]
    if not parts or ".." in parts:
        return None
    target = (SITE_ROOT.joinpath(*parts)).resolve()
    try:
        target.relative_to(SITE_ROOT)
    except ValueError:
        return None
    return target if target.is_file() else None


@app.get("/ml/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "service": "agrivision-ml",
            "y3172": ["SRC", "C", "PP", "M", "P", "D", "SINK"],
        }
    )


@app.get("/ml/meta")
def meta():
    return jsonify(
        {
            "service": "agrivision-ml",
            "training": _ml_training_meta(),
            "pipeline": {
                "standard": "ITU-T Y.3172",
                "nodes": {
                    "SRC": ["SoilGrids", "Open-Meteo", "GPS", "IoT sensors (sim/ingest)"],
                    "C": "Flask collector",
                    "PP": "Feature vector + scaling inside model pipelines",
                    "M": ["random_forest", "svm", "gradient_boosting", "blend"],
                    "P": "Agronomic rules + sustainability guidelines (Vision 2030 / Saudi Green) + human validation",
                    "D": "JSON API + PWA web UI",
                    "SINK": "Farmer / agronomist decision",
                },
            },
        }
    )


@app.get("/ml/sensors/simulate")
def sensors_simulate():
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
    except (TypeError, ValueError):
        return jsonify({"error": "lat and lon query params are required numbers"}), 400
    return jsonify(simulate_sensors(lat, lon))


@app.post("/ml/sensors/ingest")
def sensors_ingest():
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict) or not body:
        return jsonify({"error": "JSON body required"}), 400
    record = ingest_reading(body)
    return jsonify(record), 201


@app.get("/ml/sensors/latest")
def sensors_latest():
    device_id = request.args.get("device_id")
    rec = latest_ingest(device_id)
    if not rec:
        return jsonify({"error": "no ingested readings"}), 404
    return jsonify(rec)


@app.get("/ml/sensors")
def sensors_list():
    return jsonify({"readings": list_ingest()})


@app.post("/ml/recommend")
def recommend():
    body = request.get_json(silent=True) or {}
    try:
        lat = float(body.get("latitude"))
        lon = float(body.get("longitude"))
    except (TypeError, ValueError):
        return jsonify({"error": "latitude and longitude are required numbers"}), 400

    model = (body.get("model") or "blend").lower()
    top_k = int(body.get("top_k") or 5)
    top_k = max(1, min(top_k, 5))
    use_iot = bool(body.get("use_iot") or body.get("iot"))
    iot_mode = (body.get("iot_mode") or "simulate").lower()  # simulate | ingest
    apply_policy = body.get("apply_policy", True)
    if isinstance(apply_policy, str):
        apply_policy = apply_policy.lower() not in ("0", "false", "no")

    weather = fetch_weather(lat, lon)
    soil = fetch_soil_properties(lat, lon)
    features = build_feature_row(soil, weather)

    data_sources = ["soilgrids", "open_meteo", "gps"]
    iot_payload = None
    if use_iot:
        if iot_mode == "ingest":
            iot_payload = latest_ingest(body.get("device_id"))
            if not iot_payload:
                iot_payload = simulate_sensors(lat, lon)
                iot_payload["note"] = (
                    "No ingested device reading found — fell back to IoT simulator for this request."
                )
        else:
            iot_payload = simulate_sensors(lat, lon)
        features = fuse_features(features, iot_payload)
        data_sources.append(str(iot_payload.get("source") or "iot"))

    if model == "svm":
        ranked = predict_top_crops(features, "svm", top_k=top_k)
    elif model in ("rf", "random_forest"):
        ranked = predict_top_crops(features, "rf", top_k=top_k)
    elif model in ("gb", "gradient_boosting"):
        ranked = predict_top_crops(features, "gb", top_k=top_k)
    else:
        ranked = merge_unique_top(features, top_k=top_k)
        model = "blend"

    ranked = apply_arid_policy(ranked, features, enable=bool(apply_policy))
    ranked = attach_irrigation(ranked, features)

    return jsonify(
        {
            "latitude": lat,
            "longitude": lon,
            "model": model,
            "data_sources": data_sources,
            "training": _ml_training_meta(),
            "pipeline_standard": "ITU-T Y.3172",
            "inputs": {
                "soil": soil,
                "weather": weather,
                "features": features,
                "iot": iot_payload,
            },
            "recommendations": ranked,
        }
    )


@app.get("/")
def site_index():
    return send_from_directory(SITE_ROOT, "index.html")


@app.get("/<path:path>")
def site_static(path: str):
    if path == "ml" or path.startswith("ml/"):
        abort(404)
    target = _safe_site_file(path)
    if target:
        return send_from_directory(target.parent, target.name)
    abort(404)


if __name__ == "__main__":
    port = int(os.environ.get("PORT") or os.environ.get("ML_PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
