"""IoT-ready sensor SRC node: simulator + in-memory ingest for real devices."""

from __future__ import annotations

import hashlib
import math
import time
from typing import Any, Dict, List, Optional

# Latest ingested reading per device_id (demo store; replace with DB in production)
_INGEST_STORE: Dict[str, Dict[str, Any]] = {}


def _seed_from_latlon(lat: float, lon: float) -> int:
    h = hashlib.sha256(f"{lat:.5f}:{lon:.5f}".encode()).hexdigest()
    return int(h[:8], 16)


def simulate_sensors(lat: float, lon: float, *, now: Optional[float] = None) -> Dict[str, Any]:
    """Deterministic-ish field sensors for a point (Y.3172 SRC)."""
    now = now if now is not None else time.time()
    seed = _seed_from_latlon(lat, lon)
    # Pseudo-random but stable per location; slight diurnal drift from time
    t_phase = math.sin(now / 3600.0)
    r1 = ((seed % 1000) / 1000.0) - 0.5
    r2 = (((seed // 1000) % 1000) / 1000.0) - 0.5
    r3 = (((seed // 1_000_000) % 1000) / 1000.0) - 0.5

    # Saudi-ish arid defaults with local variation
    soil_moisture = float(np_clip(0.06 + 0.05 * r1 + 0.01 * t_phase, 0.03, 0.28))
    temp_c = float(np_clip(28.0 + 8.0 * r2 + 2.5 * t_phase, 12.0, 48.0))
    rh_pct = float(np_clip(35.0 + 20.0 * r3 - 0.3 * max(0, temp_c - 30), 10.0, 85.0))
    nitrogen_gkg = float(np_clip(0.85 + 0.4 * abs(r1), 0.4, 2.0))
    phosphorus_ppm = float(np_clip(14.0 + 12.0 * abs(r2), 5.0, 45.0))
    potassium_ppm = float(np_clip(170.0 + 60.0 * abs(r3), 80.0, 320.0))
    ph = float(np_clip(7.4 + 0.8 * r1, 6.0, 8.6))

    return {
        "source": "iot_sim",
        "device_id": f"sim-{seed % 100000:05d}",
        "latitude": lat,
        "longitude": lon,
        "timestamp": int(now),
        "readings": {
            "soil_moisture_m3m3": round(soil_moisture, 4),
            "temp_c": round(temp_c, 2),
            "rh_pct": round(rh_pct, 1),
            "nitrogen_gkg": round(nitrogen_gkg, 3),
            "phosphorus_ppm": round(phosphorus_ppm, 1),
            "potassium_ppm": round(potassium_ppm, 1),
            "ph": round(ph, 2),
        },
        "y3172_node": "SRC",
        "note": "Simulated IoT field sensors (architecture-ready for real device ingest).",
    }


def np_clip(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def ingest_reading(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Accept a real/device payload. Expected keys under readings or top-level features."""
    device_id = str(payload.get("device_id") or payload.get("id") or "unknown-device")
    lat = payload.get("latitude")
    lon = payload.get("longitude")
    readings = payload.get("readings") or {}
    # Allow flat feature keys
    for key in (
        "soil_moisture_m3m3",
        "temp_c",
        "rh_pct",
        "nitrogen_gkg",
        "phosphorus_ppm",
        "potassium_ppm",
        "ph",
        "rain_mm",
    ):
        if key in payload and key not in readings:
            readings[key] = payload[key]

    record = {
        "source": "iot_ingest",
        "device_id": device_id,
        "latitude": lat,
        "longitude": lon,
        "timestamp": int(payload.get("timestamp") or time.time()),
        "readings": readings,
        "y3172_node": "SRC",
        "note": "Ingested device reading stored in demo memory.",
    }
    _INGEST_STORE[device_id] = record
    return record


def latest_ingest(device_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if device_id:
        return _INGEST_STORE.get(device_id)
    if not _INGEST_STORE:
        return None
    # Most recent by timestamp
    return max(_INGEST_STORE.values(), key=lambda r: int(r.get("timestamp") or 0))


def list_ingest() -> List[Dict[str, Any]]:
    return sorted(_INGEST_STORE.values(), key=lambda r: int(r.get("timestamp") or 0), reverse=True)


def fuse_features(
    base_features: Dict[str, float],
    sensor_payload: Optional[Dict[str, Any]],
) -> Dict[str, float]:
    """IoT overrides overlapping keys when present (Collector fusion)."""
    if not sensor_payload:
        return dict(base_features)
    readings = sensor_payload.get("readings") or {}
    out = dict(base_features)
    for key, val in readings.items():
        if key in out and val is not None:
            try:
                out[key] = float(val)
            except (TypeError, ValueError):
                continue
    return out
