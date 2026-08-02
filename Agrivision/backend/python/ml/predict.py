from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Tuple

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / "models"

ModelName = Literal["rf", "svm", "gb", "random_forest", "gradient_boosting"]

# Water-use intensity for arid Policy re-ranking (lower = more efficient)
WATER_INTENSITY = {
    "sorghum": 0.25,
    "barley": 0.45,
    "wheat": 0.55,
    "tomato": 0.80,
    "corn": 0.90,
}

FEATURE_LABELS = {
    "nitrogen_gkg": "nitrogen",
    "phosphorus_ppm": "phosphorus",
    "potassium_ppm": "potassium",
    "ph": "pH",
    "soil_moisture_m3m3": "soil moisture",
    "temp_c": "temperature",
    "rh_pct": "humidity",
    "rain_mm": "rainfall",
}


def _meta() -> Dict[str, Any]:
    p = MODEL_DIR / "model_meta.json"
    if not p.exists():
        return {"feature_order": [], "classes": [], "ideals": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def load_model(name: ModelName):
    if name in ("rf", "random_forest"):
        key = "random_forest"
    elif name in ("gb", "gradient_boosting"):
        key = "gradient_boosting"
    else:
        key = "svm"
    path = MODEL_DIR / f"{key}.joblib"
    if not path.exists():
        raise FileNotFoundError(f"Missing trained model: {path}. Run: python -m ml.train")
    return joblib.load(path)


def feature_vector(row: Dict[str, float]) -> Tuple[np.ndarray, List[str]]:
    meta = _meta()
    order = meta.get("feature_order") or [
        "nitrogen_gkg",
        "phosphorus_ppm",
        "potassium_ppm",
        "ph",
        "soil_moisture_m3m3",
        "temp_c",
        "rh_pct",
        "rain_mm",
    ]
    vals = np.array([[float(row[k]) for k in order]], dtype=float)
    return vals, order


def _explain_crop(crop: str, row: Dict[str, float], order: List[str]) -> List[str]:
    meta = _meta()
    ideals = meta.get("ideals") or {}
    ideal = ideals.get(crop)
    if not ideal or len(ideal) != len(order):
        return [f"{crop.title()} ranked highly by the ensemble for this site."]

    why: List[str] = []
    gaps = []
    for i, key in enumerate(order):
        actual = float(row.get(key, 0.0))
        target = float(ideal[i])
        denom = abs(target) if abs(target) > 1e-6 else 1.0
        rel = abs(actual - target) / denom
        gaps.append((rel, key, actual, target))
    gaps.sort(key=lambda x: x[0])

    for rel, key, actual, target in gaps[:2]:
        label = FEATURE_LABELS.get(key, key)
        if rel < 0.15:
            why.append(f"{label.title()} ({actual:.2f}) is close to the ideal for {crop} (~{target:.2f}).")
        else:
            direction = "a bit low" if actual < target else "a bit high"
            why.append(f"{label.title()} is {direction} vs {crop} ideal, but still competitive overall.")

    intensity = WATER_INTENSITY.get(crop.lower(), 0.6)
    if intensity <= 0.45:
        why.append("Lower water demand — better fit for arid / water-scarce conditions.")
    elif intensity >= 0.8:
        why.append("Higher water demand — consider drip irrigation if selected.")
    return why[:3]


def water_efficiency_score(crop: str, row: Dict[str, float]) -> float:
    """0–100; higher = more suitable under dry / scarce-water conditions."""
    intensity = WATER_INTENSITY.get(str(crop).lower(), 0.6)
    moisture = float(row.get("soil_moisture_m3m3", 0.1))
    rain = float(row.get("rain_mm", 0.0))
    temp = float(row.get("temp_c", 25.0))
    dryness = 0.0
    if moisture < 0.08:
        dryness += 0.35
    elif moisture < 0.12:
        dryness += 0.18
    if rain < 1.0:
        dryness += 0.25
    elif rain < 2.0:
        dryness += 0.10
    if temp > 32:
        dryness += 0.20
    elif temp > 28:
        dryness += 0.10
    dryness = min(1.0, dryness)
    # Prefer low-intensity crops when dry
    score = (1.0 - intensity) * (0.55 + 0.45 * dryness) + (1.0 - dryness) * 0.35 * (1.0 - abs(intensity - 0.5))
    return round(float(np.clip(score, 0, 1) * 100.0), 1)


# Rough ideal temperature bands (°C) for climate re-ranking
TEMP_BAND = {
    "sorghum": (24.0, 34.0),
    "barley": (10.0, 24.0),
    "wheat": (12.0, 26.0),
    "tomato": (18.0, 30.0),
    "corn": (20.0, 32.0),
}


def climate_fit_score(crop: str, row: Dict[str, float]) -> float:
    """0–100 how well local climate matches the crop (temp + humidity + rain)."""
    temp = float(row.get("temp_c", 25.0))
    rh = float(row.get("rh_pct", 40.0))
    rain = float(row.get("rain_mm", 0.0))
    lo, hi = TEMP_BAND.get(str(crop).lower(), (18.0, 30.0))
    if lo <= temp <= hi:
        temp_score = 1.0
    else:
        dist = lo - temp if temp < lo else temp - hi
        temp_score = max(0.0, 1.0 - dist / 12.0)

    # Prefer moderate humidity for most cereals; sorghum tolerates drier air
    c = str(crop).lower()
    if c == "sorghum":
        rh_score = 1.0 if rh < 55 else max(0.4, 1.0 - (rh - 55) / 50.0)
    elif c in ("wheat", "barley"):
        rh_score = 1.0 if 30 <= rh <= 70 else 0.55
    else:
        rh_score = 1.0 if 35 <= rh <= 75 else 0.6

    if c in ("sorghum", "barley"):
        rain_score = 1.0 if rain < 3.0 else 0.7
    elif c in ("corn", "tomato"):
        rain_score = 1.0 if rain >= 1.5 else 0.55
    else:
        rain_score = 0.85

    score = 0.60 * temp_score + 0.25 * rh_score + 0.15 * rain_score
    return round(float(np.clip(score, 0, 1) * 100.0), 1)


def _enrich(items: List[Dict[str, Any]], row: Dict[str, float], order: List[str]) -> List[Dict[str, Any]]:
    out = []
    for item in items:
        crop = str(item.get("crop", ""))
        out.append(
            {
                **item,
                "water_efficiency_score": water_efficiency_score(crop, row),
                "climate_fit_score": climate_fit_score(crop, row),
                "why": _explain_crop(crop, row, order),
            }
        )
    return out


def apply_arid_policy(
    items: List[Dict[str, Any]],
    row: Dict[str, float],
    *,
    enable: bool = True,
) -> List[Dict[str, Any]]:
    """Policy (P) node: blend ML match with water efficiency + climate fit."""
    if not enable or not items:
        return items
    moisture = float(row.get("soil_moisture_m3m3", 0.1))
    rain = float(row.get("rain_mm", 0.0))
    temp = float(row.get("temp_c", 25.0))
    arid = moisture < 0.10 or (rain < 1.5 and temp > 30)

    matches = [float(i.get("match_score", 0)) for i in items]
    peaked = max(matches) >= 65.0 if matches else False

    # When the ensemble is over-confident on one crop (common in arid fallback soil),
    # down-weight raw ML so climate & water can change the order by location.
    if peaked:
        w_match, w_water, w_climate = 0.30, 0.30, 0.40
    elif arid:
        w_match, w_water, w_climate = 0.45, 0.25, 0.30
    else:
        w_match, w_water, w_climate = 0.50, 0.15, 0.35

    rescored = []
    for item in items:
        match = float(item.get("match_score", 0))
        # Soften peaky probabilities: 81% → ~90 scale less extreme vs 5%
        match_soft = float(np.sqrt(max(match, 0.0) / 100.0) * 100.0)
        water = float(item.get("water_efficiency_score", 50))
        climate = float(item.get("climate_fit_score", 50))
        # Cooler highland / mild temps: lift wheat & barley
        crop = str(item.get("crop", "")).lower()
        if temp <= 26 and crop in ("wheat", "barley"):
            climate = min(100.0, climate + 12.0)
        if temp >= 36 and crop in ("wheat", "barley", "tomato"):
            climate = max(0.0, climate - 15.0)
        if temp >= 36 and crop == "sorghum":
            climate = min(100.0, climate + 8.0)
        final = w_match * match_soft + w_water * water + w_climate * climate
        rescored.append(
            {
                **item,
                "policy_adjusted_score": round(final, 2),
                "policy_applied": True,
                "arid_stress": arid,
            }
        )
    rescored.sort(key=lambda x: -float(x.get("policy_adjusted_score", 0)))
    return rescored


def predict_top_crops(
    row: Dict[str, float],
    model_name: ModelName = "rf",
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    model = load_model(model_name)
    X, order = feature_vector(row)
    classes = list(getattr(model, "classes_", []))
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(X)[0]
        ranked = sorted(zip(classes, proba), key=lambda x: -x[1])
    else:
        pred = model.predict(X)[0]
        ranked = [(pred, 1.0)]

    out = [{"crop": str(crop), "match_score": round(float(p) * 100.0, 2)} for crop, p in ranked[:top_k]]
    return _enrich(out, row, order)


def merge_unique_top(
    row: Dict[str, float],
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """Weighted RF + SVM + GB soft vote when models exist."""
    X, order = feature_vector(row)
    meta = _meta()
    weights = meta.get("blend_weights") or {"rf": 0.40, "svm": 0.25, "gb": 0.35}

    try:
        rf = load_model("rf")
        svm = load_model("svm")
        gb = load_model("gb")
    except FileNotFoundError:
        try:
            return predict_top_crops(row, "rf", top_k=top_k)
        except FileNotFoundError:
            return predict_top_crops(row, "svm", top_k=top_k)

    classes = list(rf.classes_)

    def align(model, proba):
        idx = [list(model.classes_).index(c) for c in classes]
        return proba[:, idx]

    blend = (
        float(weights.get("rf", 0.4)) * rf.predict_proba(X)
        + float(weights.get("svm", 0.25)) * align(svm, svm.predict_proba(X))
        + float(weights.get("gb", 0.35)) * align(gb, gb.predict_proba(X))
    )[0]
    ranked = sorted(zip(classes, blend), key=lambda x: -x[1])
    out = [{"crop": str(c), "match_score": round(float(p) * 100.0, 2)} for c, p in ranked[:top_k]]
    return _enrich(out, row, order)
