"""
edge_ml/real_audio.py
Utilities for training and running a real-audio respiratory sound classifier.

This module is optional and used only when real respiratory audio datasets are
available locally. It supports:
- Training from a CSV manifest of labeled clips
- Window-level inference on new audio
- Isolation of respiratory event windows (e.g., cough/sneeze/crackle/wheeze)
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


@dataclass
class WindowPrediction:
    start_s: float
    end_s: float
    label: str
    confidence: float


def _normalize_distribution(weights: dict[str, float]) -> dict[str, float]:
    total = sum(v for v in weights.values() if v > 0)
    if total <= 0:
        n = max(len(weights), 1)
        return {k: 1.0 / n for k in weights}
    return {k: float(v / total) for k, v in weights.items()}


def _event_to_disease_probabilities(event_probs: dict[str, float]) -> dict[str, float]:
    cough = event_probs.get("cough", 0.0)
    sneeze = event_probs.get("sneeze", 0.0)
    crackle = event_probs.get("crackle", 0.0)
    wheeze = event_probs.get("wheeze", 0.0)
    ambient = event_probs.get("ambient", 0.0)

    disease_scores = {
        "pneumonia": 0.55 * crackle + 0.25 * cough + 0.15 * wheeze + 0.05 * ambient,
        "upper_respiratory_infection": 0.55 * sneeze + 0.30 * cough + 0.10 * wheeze + 0.05 * ambient,
        "bronchitis_or_asthma": 0.55 * wheeze + 0.30 * cough + 0.10 * crackle + 0.05 * ambient,
        "normal": 0.80 * ambient + 0.20 * (1.0 - min(cough + sneeze + crackle + wheeze, 1.0)),
    }
    return _normalize_distribution(disease_scores)


def _lazy_import_audio_libs() -> tuple[Any, Any]:
    try:
        import librosa  # type: ignore
        import soundfile as sf  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Audio dependencies are missing. Install librosa and soundfile first."
        ) from exc
    return librosa, sf


def _extract_features(y: np.ndarray, sr: int) -> np.ndarray:
    librosa, _ = _lazy_import_audio_libs()
    y = y.astype(np.float32)
    if np.max(np.abs(y)) > 0:
        y = y / np.max(np.abs(y))

    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)
    zcr = librosa.feature.zero_crossing_rate(y)
    rms = librosa.feature.rms(y=y)
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
    bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)

    feats = np.concatenate(
        [
            np.mean(mfcc, axis=1),
            np.std(mfcc, axis=1),
            [float(np.mean(zcr)), float(np.std(zcr))],
            [float(np.mean(rms)), float(np.std(rms))],
            [float(np.mean(centroid)), float(np.std(centroid))],
            [float(np.mean(rolloff)), float(np.std(rolloff))],
            [float(np.mean(bandwidth)), float(np.std(bandwidth))],
        ]
    )
    return feats


def _window_audio(y: np.ndarray, sr: int, window_s: float, hop_s: float) -> Iterable[tuple[int, int, np.ndarray]]:
    window = max(int(window_s * sr), 1)
    hop = max(int(hop_s * sr), 1)
    for start in range(0, max(len(y) - window + 1, 1), hop):
        end = min(start + window, len(y))
        chunk = y[start:end]
        if len(chunk) < window:
            chunk = np.pad(chunk, (0, window - len(chunk)))
        yield start, end, chunk


def _resolve_path(path_str: str, base_dir: str | None) -> str:
    p = Path(path_str)
    if p.is_absolute() or base_dir is None:
        return str(p)
    return str((Path(base_dir) / p).resolve())


def _parse_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def train_from_manifest(
    manifest_csv: str,
    output_model: str,
    base_dir: str | None = None,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict[str, Any]:
    """
    Train a classifier from CSV rows: audio_path,label.
    """
    librosa, _ = _lazy_import_audio_libs()

    x_rows: list[np.ndarray] = []
    y_rows: list[str] = []

    with open(manifest_csv, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])
        if "audio_path" not in fieldnames or "label" not in fieldnames:
            raise ValueError("Manifest must contain 'audio_path' and 'label' columns")

        for row in reader:
            path = _resolve_path(row["audio_path"], base_dir)
            label = str(row["label"]).strip().lower()
            if not os.path.exists(path):
                continue
            y, sr = librosa.load(path, sr=16000, mono=True)
            if y.size == 0:
                continue
            start_s = _parse_optional_float(row.get("start_s"))
            end_s = _parse_optional_float(row.get("end_s"))
            if start_s is not None or end_s is not None:
                start_idx = max(int((start_s or 0.0) * sr), 0)
                end_idx = int((end_s if end_s is not None else (len(y) / sr)) * sr)
                end_idx = min(max(end_idx, start_idx + 1), len(y))
                y = y[start_idx:end_idx]
                if y.size == 0:
                    continue
            x_rows.append(_extract_features(y, sr))
            y_rows.append(label)

    if not x_rows:
        raise ValueError("No training rows could be loaded from the manifest")

    x = np.vstack(x_rows)
    y = np.array(y_rows)

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=test_size,
        stratify=y if len(set(y)) > 1 else None,
        random_state=random_state,
    )

    model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "rf",
                RandomForestClassifier(
                    n_estimators=300,
                    random_state=random_state,
                    class_weight="balanced_subsample",
                ),
            ),
        ]
    )
    model.fit(x_train, y_train)

    y_pred = model.predict(x_test)
    report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)

    payload = {
        "model": model,
        "labels": sorted(set(y_rows)),
        "sample_rate": 16000,
    }
    os.makedirs(os.path.dirname(output_model) or ".", exist_ok=True)
    joblib.dump(payload, output_model)

    return {
        "num_samples": int(len(x_rows)),
        "labels": sorted(set(y_rows)),
        "model_path": output_model,
        "macro_f1": float(report.get("macro avg", {}).get("f1-score", 0.0)),
    }


def predict_windows(
    audio_path: str,
    model_path: str,
    window_s: float = 1.0,
    hop_s: float = 0.5,
) -> list[WindowPrediction]:
    librosa, _ = _lazy_import_audio_libs()
    bundle = joblib.load(model_path)
    model: Pipeline = bundle["model"]
    y, sr = librosa.load(audio_path, sr=16000, mono=True)

    preds: list[WindowPrediction] = []
    for start, end, chunk in _window_audio(y, sr, window_s, hop_s):
        features = _extract_features(chunk, sr).reshape(1, -1)
        probs = model.predict_proba(features)[0]
        cls = model.classes_[int(np.argmax(probs))]
        conf = float(np.max(probs))
        preds.append(
            WindowPrediction(
                start_s=round(start / sr, 3),
                end_s=round(end / sr, 3),
                label=str(cls),
                confidence=conf,
            )
        )
    return preds


def isolate_patient_sounds(
    input_audio_path: str,
    output_audio_path: str,
    model_path: str | None = None,
    target_labels: Iterable[str] = ("cough", "sneeze", "crackle", "wheeze"),
    confidence_threshold: float = 0.45,
    window_s: float = 1.0,
    hop_s: float = 0.5,
) -> dict[str, Any]:
    """
    Keep respiratory event windows and remove likely normal speech/background.
    """
    librosa, sf = _lazy_import_audio_libs()

    target = {lbl.strip().lower() for lbl in target_labels}
    y, sr = librosa.load(input_audio_path, sr=16000, mono=True)

    if model_path and os.path.exists(model_path):
        predictions = predict_windows(
            input_audio_path,
            model_path=model_path,
            window_s=window_s,
            hop_s=hop_s,
        )
        keep_ranges = [
            p for p in predictions if p.label.lower() in target and p.confidence >= confidence_threshold
        ]
    else:
        # Heuristic fallback: high-energy, non-speech-like windows.
        keep_ranges = []
        for start, end, chunk in _window_audio(y, sr, window_s, hop_s):
            feats = _extract_features(chunk, sr)
            rms_mean = float(feats[42])
            centroid_mean = float(feats[44])
            likely_event = rms_mean > 0.02 and 300.0 < centroid_mean < 3500.0
            if likely_event:
                keep_ranges.append(
                    WindowPrediction(
                        start_s=round(start / sr, 3),
                        end_s=round(end / sr, 3),
                        label="resp_event",
                        confidence=0.5,
                    )
                )

    if not keep_ranges:
        sf.write(output_audio_path, np.zeros((1,), dtype=np.float32), sr)
        return {
            "output_audio_path": output_audio_path,
            "kept_windows": 0,
            "total_windows": 0,
        }

    chunks = []
    for p in keep_ranges:
        s = int(p.start_s * sr)
        e = int(p.end_s * sr)
        chunks.append(y[s:e])

    y_out = np.concatenate(chunks) if chunks else np.zeros((1,), dtype=np.float32)
    os.makedirs(os.path.dirname(output_audio_path) or ".", exist_ok=True)
    sf.write(output_audio_path, y_out, sr)

    return {
        "output_audio_path": output_audio_path,
        "kept_windows": len(keep_ranges),
        "total_windows": max(int((len(y) / sr - window_s) / hop_s) + 1, 1),
    }


def infer_disease_from_audio(
    audio_path: str,
    model_path: str | None = None,
    window_s: float = 1.0,
    hop_s: float = 0.5,
    confidence_threshold: float = 0.35,
) -> dict[str, Any]:
    """
    Predict respiratory event distribution and infer likely disease from audio.
    """
    labels = ["ambient", "cough", "sneeze", "crackle", "wheeze"]
    counts = {k: 0.0 for k in labels}

    if model_path and os.path.exists(model_path):
        predictions = predict_windows(
            audio_path=audio_path,
            model_path=model_path,
            window_s=window_s,
            hop_s=hop_s,
        )
        total = max(len(predictions), 1)
        for p in predictions:
            if p.confidence < confidence_threshold:
                counts["ambient"] += 0.5
                continue
            key = p.label.lower().strip()
            if key not in counts:
                counts["ambient"] += 0.5
                continue
            counts[key] += float(max(p.confidence, 0.1))
        event_probs = _normalize_distribution(counts)
    else:
        librosa, _ = _lazy_import_audio_libs()
        y, sr = librosa.load(audio_path, sr=16000, mono=True)
        total = 0
        for _, _, chunk in _window_audio(y, sr, window_s, hop_s):
            total += 1
            feats = _extract_features(chunk, sr)
            rms_mean = float(feats[42])
            centroid_mean = float(feats[44])
            zcr_mean = float(feats[40])

            if rms_mean < 0.01:
                counts["ambient"] += 1.0
            elif centroid_mean > 2200 and zcr_mean > 0.08:
                counts["sneeze"] += 1.0
            elif 1300 < centroid_mean <= 2200 and zcr_mean > 0.06:
                counts["cough"] += 1.0
            elif 700 < centroid_mean <= 1600 and zcr_mean < 0.06:
                counts["wheeze"] += 1.0
            else:
                counts["crackle"] += 1.0
        event_probs = _normalize_distribution(counts)

    disease_probs = _event_to_disease_probabilities(event_probs)
    likely_disease = max(disease_probs.items(), key=lambda item: item[1])[0]
    return {
        "event_probabilities": event_probs,
        "disease_probabilities": disease_probs,
        "likely_disease": likely_disease,
        "total_windows": int(total),
    }
