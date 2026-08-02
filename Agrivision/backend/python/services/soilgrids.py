"""SoilGrids (ISRIC) point query; regional KSA priors when layers are null."""

from __future__ import annotations

import math
import os
from typing import Any, Dict, List, Optional, Tuple

import requests

SOILGRIDS_URL = os.environ.get(
    "SOILGRIDS_URL",
    "https://rest.isric.org/soilgrids/v2.0/properties/query",
)

# Location-aware priors when SoilGrids has no data (common in sparse KSA cells)
_REGION_PROFILES = {
    "western_highlands": {  # Taif / cooler uplands — better for wheat/barley
        "nitrogen_gkg": 1.15,
        "phosphorus_ppm": 22.0,
        "potassium_ppm": 210.0,
        "ph": 6.8,
        "label": "western_highlands",
    },
    "red_sea_coast": {  # Jeddah / coastal — warmer, alkaline tendency
        "nitrogen_gkg": 0.85,
        "phosphorus_ppm": 16.0,
        "potassium_ppm": 170.0,
        "ph": 7.6,
        "label": "red_sea_coast",
    },
    "central_arid": {  # Riyadh / Najd — hot, low organic matter
        "nitrogen_gkg": 0.75,
        "phosphorus_ppm": 12.0,
        "potassium_ppm": 160.0,
        "ph": 8.0,
        "label": "central_arid",
    },
    "eastern": {
        "nitrogen_gkg": 0.8,
        "phosphorus_ppm": 13.0,
        "potassium_ppm": 175.0,
        "ph": 7.8,
        "label": "eastern",
    },
    "default_ksa": {
        "nitrogen_gkg": 0.9,
        "phosphorus_ppm": 14.0,
        "potassium_ppm": 180.0,
        "ph": 7.9,
        "label": "default_ksa",
    },
}


def regional_soil_prior(lat: float, lon: float) -> Dict[str, Any]:
    """Pick a KSA soil prior from coordinates (small jitter so nearby points differ)."""
    if 20.5 <= lat <= 22.2 and 39.5 <= lon <= 41.5:
        base = dict(_REGION_PROFILES["western_highlands"])
    elif 20.8 <= lat <= 22.5 and 38.5 <= lon <= 39.8:
        base = dict(_REGION_PROFILES["red_sea_coast"])
    elif 23.5 <= lat <= 26.5 and 45.5 <= lon <= 48.0:
        base = dict(_REGION_PROFILES["central_arid"])
    elif 24.0 <= lat <= 27.5 and 48.0 <= lon <= 51.0:
        base = dict(_REGION_PROFILES["eastern"])
    else:
        base = dict(_REGION_PROFILES["default_ksa"])

    # Tiny deterministic variation from lat/lon so pins a few km apart are not identical
    jitter = math.sin(lat * 12.9898 + lon * 78.233) * 43758.5453
    frac = jitter - math.floor(jitter)
    base["nitrogen_gkg"] = round(base["nitrogen_gkg"] + (frac - 0.5) * 0.08, 3)
    base["phosphorus_ppm"] = round(base["phosphorus_ppm"] + (frac - 0.5) * 3.0, 2)
    base["potassium_ppm"] = round(base["potassium_ppm"] + (frac - 0.5) * 12.0, 2)
    base["ph"] = round(base["ph"] + (frac - 0.5) * 0.15, 2)
    return base


def _layer_means(geojson: Dict[str, Any]) -> Dict[str, Optional[float]]:
    out: Dict[str, Optional[float]] = {}
    for layer in (geojson.get("properties") or {}).get("layers") or []:
        name = layer.get("name")
        depths = layer.get("depths") or []
        if not name or not depths:
            continue
        mean = (depths[0].get("values") or {}).get("mean")
        d_factor = (layer.get("unit_measure") or {}).get("d_factor") or 1
        if mean is None:
            out[name] = None
        else:
            try:
                raw = float(mean)
                out[name] = raw / float(d_factor) if d_factor else raw
            except (TypeError, ValueError):
                out[name] = None
    return out


def fetch_soil_properties(lat: float, lon: float, timeout: int = 25) -> Dict[str, Any]:
    props: List[str] = [
        "nitrogen",
        "phh2o",
        "clay",
        "sand",
        "soc",
    ]
    params: List[Tuple[str, str]] = [
        ("lat", str(lat)),
        ("lon", str(lon)),
        ("depth", "0-5cm"),
        ("value", "mean"),
    ]
    for p in props:
        params.append(("property", p))

    try:
        r = requests.get(SOILGRIDS_URL, params=params, timeout=timeout)
        r.raise_for_status()
        raw = r.json()
    except (requests.RequestException, ValueError):
        raw = {"properties": {"layers": []}}

    means = _layer_means(raw)
    prior = regional_soil_prior(lat, lon)

    nitrogen_gkg = means.get("nitrogen")
    ph_raw = means.get("phh2o")
    ph = ph_raw
    if ph is not None and ph > 14:
        ph = ph / 10.0
    clay_pct = means.get("clay")
    sand_pct = means.get("sand")
    soc_gkg = means.get("soc")

    used_fallback = False
    if nitrogen_gkg is None:
        nitrogen_gkg = prior["nitrogen_gkg"]
        used_fallback = True
    if ph is None:
        ph = prior["ph"]
        used_fallback = True

    phosphorus_ppm = prior["phosphorus_ppm"]
    potassium_ppm = prior["potassium_ppm"]
    if soc_gkg is not None:
        phosphorus_ppm = max(5.0, min(60.0, 8.0 + soc_gkg * 2.2))
    elif used_fallback:
        phosphorus_ppm = prior["phosphorus_ppm"]
    if clay_pct is not None:
        potassium_ppm = max(80.0, min(320.0, 120.0 + clay_pct * 3.5))
    elif used_fallback:
        potassium_ppm = prior["potassium_ppm"]

    return {
        "nitrogen_gkg": float(nitrogen_gkg),
        "phosphorus_ppm": float(phosphorus_ppm),
        "potassium_ppm": float(potassium_ppm),
        "ph": float(ph),
        "clay_pct": float(clay_pct) if clay_pct is not None else None,
        "sand_pct": float(sand_pct) if sand_pct is not None else None,
        "soc_gkg": float(soc_gkg) if soc_gkg is not None else None,
        "soilgrids_used_fallback": used_fallback,
        "soil_region": prior.get("label"),
        "source": "soilgrids+regional_prior" if used_fallback else "soilgrids",
    }


def build_feature_row(soil: Dict[str, Any], weather: Dict[str, Any]) -> Dict[str, float]:
    return {
        "nitrogen_gkg": soil["nitrogen_gkg"],
        "phosphorus_ppm": soil["phosphorus_ppm"],
        "potassium_ppm": soil["potassium_ppm"],
        "ph": soil["ph"],
        "soil_moisture_m3m3": weather["soil_moisture_m3m3"],
        "temp_c": weather["temp_c"],
        "rh_pct": weather["rh_pct"],
        "rain_mm": weather["rain_mm"],
    }
