"""Heuristic irrigation hints from weather and crop water-use tier."""

from __future__ import annotations

from typing import Any, Dict, List

CROP_WATER_CLASS: Dict[str, str] = {
    "wheat": "moderate",
    "barley": "moderate",
    "corn": "high",
    "tomato": "high",
    "sorghum": "low",
}


def irrigation_advice(
    crop: str,
    rain_mm: float,
    soil_moisture_m3m3: float,
    temp_c: float,
    rh_pct: float,
) -> Dict[str, Any]:
    wclass = CROP_WATER_CLASS.get(crop.lower(), "moderate")

    if soil_moisture_m3m3 < 0.06:
        soil_note = "Topsoil is dry — irrigate sooner or shorten intervals slightly."
    elif soil_moisture_m3m3 < 0.12:
        soil_note = "Soil moisture is moderate — keep the usual schedule."
    else:
        soil_note = "Good topsoil moisture — ease irrigation briefly to limit nutrient leaching."

    if rain_mm > 3:
        rain_note = "Recent rain — delay irrigation until the surface dries."
    elif rain_mm > 0:
        rain_note = "Light rain — check moisture before the next irrigation."
    else:
        rain_note = "No recent rain — rely on irrigation or dew as appropriate."

    if temp_c > 32 and rh_pct < 35:
        evap = "Hot, dry air — high evaporation; shorter, more frequent irrigations if needed."
    elif temp_c > 28:
        evap = "Warm conditions — watch for water stress."
    else:
        evap = "Temperature relatively mild for normal irrigation timing."

    if wclass == "high":
        crop_hint = "High water-use crop — prefer drip; avoid dry-down at peak demand."
    elif wclass == "low":
        crop_hint = "Lower water-use crop — avoid over-irrigation."
    else:
        crop_hint = "Moderate water need — spread water across growth stages."

    return {
        "crop": crop,
        "water_class": wclass,
        "summary": " ".join([crop_hint, soil_note, rain_note, evap]),
    }


def attach_irrigation(recommendations: List[Dict[str, Any]], ctx: Dict[str, float]) -> List[Dict[str, Any]]:
    rain = ctx.get("rain_mm", 0.0)
    sm = ctx.get("soil_moisture_m3m3", 0.1)
    t = ctx.get("temp_c", 25.0)
    rh = ctx.get("rh_pct", 50.0)
    out = []
    for item in recommendations:
        c = item.get("crop", "")
        adv = irrigation_advice(c, rain, sm, t, rh)
        out.append({**item, "irrigation": adv})
    return out
