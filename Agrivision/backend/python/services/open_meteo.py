"""Open-Meteo: temperature, humidity, rainfall, soil moisture; stable 7-day local averages for ML."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests

OPEN_METEO_URL = os.environ.get(
    "OPEN_METEO_URL",
    "https://api.open-meteo.com/v1/forecast",
)

_CURRENT_VARS = ",".join(
    [
        "temperature_2m",
        "relative_humidity_2m",
        "precipitation",
        "soil_moisture_0_to_7cm",
        "wind_speed_10m",
    ]
)


def _mean_non_null(values: List[Any]) -> Optional[float]:
    nums = []
    for v in values:
        if v is None:
            continue
        try:
            nums.append(float(v))
        except (TypeError, ValueError):
            continue
    if not nums:
        return None
    return sum(nums) / len(nums)


def fetch_weather(lat: float, lon: float, timeout: int = 15) -> Dict[str, Any]:
    params_full = {
        "latitude": lat,
        "longitude": lon,
        "past_days": 7,
        "current": _CURRENT_VARS,
        "daily": "temperature_2m_mean,relative_humidity_2m_mean,precipitation_sum",
    }
    params_current_only = {
        "latitude": lat,
        "longitude": lon,
        "current": _CURRENT_VARS,
    }
    data: Dict[str, Any] = {}
    try:
        r = requests.get(OPEN_METEO_URL, params=params_full, timeout=timeout)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError):
        data = {}
    if not (data.get("current") or {}):
        try:
            r = requests.get(OPEN_METEO_URL, params=params_current_only, timeout=timeout)
            r.raise_for_status()
            data = r.json()
        except (requests.RequestException, ValueError):
            data = {}

    cur = data.get("current") or {}
    temp_c = float(cur.get("temperature_2m", 25.0))
    rh_pct = float(cur.get("relative_humidity_2m", 40.0))
    rain_mm = float(cur.get("precipitation", 0.0))
    soil_m = float(cur.get("soil_moisture_0_to_7cm", 0.08))
    wind = cur.get("wind_speed_10m")
    wind_speed = float(wind) if wind is not None else None

    summary_mode = "current"
    daily = data.get("daily") or {}
    t_mean = _mean_non_null(daily.get("temperature_2m_mean") or [])
    rh_mean = _mean_non_null(daily.get("relative_humidity_2m_mean") or [])
    rains = daily.get("precipitation_sum") or []
    rain_nums: List[float] = []
    for v in (rains if isinstance(rains, list) else []):
        if v is None:
            continue
        try:
            rain_nums.append(float(v))
        except (TypeError, ValueError):
            continue
    avg_daily_rain = (sum(rain_nums) / len(rain_nums)) if rain_nums else None

    has_daily = (
        t_mean is not None or rh_mean is not None or avg_daily_rain is not None
    )
    if has_daily:
        summary_mode = "daily_7d_mean"
        if t_mean is not None:
            temp_c = t_mean
        if rh_mean is not None:
            rh_pct = rh_mean
        if avg_daily_rain is not None:
            rain_mm = avg_daily_rain

    return {
        "temp_c": float(temp_c),
        "rh_pct": float(rh_pct),
        "rain_mm": float(rain_mm),
        "soil_moisture_m3m3": float(soil_m),
        "wind_speed_10m": wind_speed,
        "source": "open-meteo",
        "summary_mode": summary_mode,
        "summary_note_en": (
            "Air temperature, humidity, and rainfall use a 7-day local average for this "
            "location (recent typical conditions). Soil moisture is the latest grid estimate. "
            "These values, together with soil nutrients from your coordinates, feed the recommendation model."
            if summary_mode == "daily_7d_mean"
            else "Air and soil moisture use the latest Open-Meteo snapshot for this location, "
            "together with soil data — all fed into the recommendation model."
        ),
    }
