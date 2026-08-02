"""Train RF + SVM + GradientBoosting. Uses crops_training.csv or synthetic IDEALS samples."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / "models"
DATA_DIR = ROOT.parent / "data"

FEATURE_ORDER = [
    "nitrogen_gkg",
    "phosphorus_ppm",
    "potassium_ppm",
    "ph",
    "soil_moisture_m3m3",
    "temp_c",
    "rh_pct",
    "rain_mm",
]

IDEALS = {
    "wheat": (1.2, 22.0, 220.0, 6.6, 0.12, 21.0, 55.0, 2.0),
    "barley": (1.0, 20.0, 200.0, 6.5, 0.10, 19.0, 50.0, 1.5),
    "corn": (1.6, 28.0, 260.0, 6.4, 0.16, 27.0, 65.0, 4.0),
    "tomato": (1.4, 35.0, 240.0, 6.3, 0.18, 24.0, 60.0, 3.0),
    "sorghum": (1.0, 18.0, 190.0, 6.7, 0.09, 28.0, 45.0, 1.2),
}

SIGMA_SCALE = np.array([0.35, 6.0, 45.0, 0.6, 0.035, 5.0, 12.0, 2.0], dtype=float)


def generate_training_rows(n_per_crop: int = 400, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    X_list = []
    y_list = []
    for crop, ideal in IDEALS.items():
        center = np.array(ideal, dtype=float)
        for _ in range(n_per_crop):
            noise = rng.normal(0, 1, size=8) * SIGMA_SCALE
            vec = center + noise
            vec[4] = float(np.clip(vec[4], 0.02, 0.45))
            vec[7] = max(0.0, vec[7])
            X_list.append(vec.astype(float))
            y_list.append(crop)
    return np.stack(X_list, axis=0), np.array(y_list)


def _load_csv_training(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("Empty CSV")
        for c in FEATURE_ORDER + ["crop"]:
            if c not in reader.fieldnames:
                raise ValueError(f"Training CSV missing column: {c}")
        xs, ys = [], []
        for row in reader:
            xs.append([float(row[k]) for k in FEATURE_ORDER])
            ys.append(row["crop"])
    return np.array(xs, dtype=float), np.array(ys)


def _importance_map(names: list[str], values: np.ndarray) -> dict[str, float]:
    total = float(np.sum(values)) or 1.0
    return {n: round(float(v) / total, 4) for n, v in zip(names, values)}


def _eval(y_true, y_pred) -> dict[str, float]:
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "macro_f1": round(float(f1_score(y_true, y_pred, average="macro")), 4),
    }


def train_and_save() -> None:
    csv_path = DATA_DIR / "crops_training.csv"
    if csv_path.exists():
        X, y = _load_csv_training(csv_path)
    else:
        X, y = generate_training_rows()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    rf = RandomForestClassifier(
        n_estimators=280,
        max_depth=18,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    rf.fit(X_train, y_train)
    rf_metrics = _eval(y_test, rf.predict(X_test))

    svm = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "svc",
                SVC(
                    kernel="rbf",
                    C=2.5,
                    gamma="scale",
                    probability=True,
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]
    )
    svm.fit(X_train, y_train)
    svm_metrics = _eval(y_test, svm.predict(X_test))

    gb = GradientBoostingClassifier(
        n_estimators=180,
        learning_rate=0.08,
        max_depth=4,
        subsample=0.9,
        random_state=42,
    )
    gb.fit(X_train, y_train)
    gb_metrics = _eval(y_test, gb.predict(X_test))

    # Soft-vote blend on holdout
    pr = rf.predict_proba(X_test)
    ps = svm.predict_proba(X_test)
    pg = gb.predict_proba(X_test)
    classes = list(rf.classes_)
    # Align SVM/GB class order to RF
    def _align(model, proba):
        idx = [list(model.classes_).index(c) for c in classes]
        return proba[:, idx]

    blend = 0.40 * pr + 0.25 * _align(svm, ps) + 0.35 * _align(gb, pg)
    blend_pred = np.array([classes[i] for i in np.argmax(blend, axis=1)])
    blend_metrics = _eval(y_test, blend_pred)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(rf, MODEL_DIR / "random_forest.joblib")
    joblib.dump(svm, MODEL_DIR / "svm.joblib")
    joblib.dump(gb, MODEL_DIR / "gradient_boosting.joblib")

    used_file = csv_path.exists()
    meta = {
        "feature_order": FEATURE_ORDER,
        "classes": classes,
        "ideals": {k: list(v) for k, v in IDEALS.items()},
        "metrics": {
            "rf": rf_metrics,
            "svm": svm_metrics,
            "gb": gb_metrics,
            "blend": blend_metrics,
        },
        "val_accuracy_rf": rf_metrics["accuracy"],
        "val_accuracy_svm": svm_metrics["accuracy"],
        "val_accuracy_gb": gb_metrics["accuracy"],
        "val_accuracy_blend": blend_metrics["accuracy"],
        "feature_importance_rf": _importance_map(FEATURE_ORDER, rf.feature_importances_),
        "feature_importance_gb": _importance_map(FEATURE_ORDER, gb.feature_importances_),
        "blend_weights": {"rf": 0.40, "svm": 0.25, "gb": 0.35},
        "note": (
            "Trained on data/crops_training.csv — replace with real agronomic labels when available."
            if used_file
            else "Synthetic samples from crop ideals (add data/crops_training.csv for locked training table)."
        ),
        "training_rows": len(X),
        "training_source": "crops_training.csv" if used_file else "generated",
        "holdout_rows": len(X_test),
    }
    (MODEL_DIR / "model_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    train_and_save()
