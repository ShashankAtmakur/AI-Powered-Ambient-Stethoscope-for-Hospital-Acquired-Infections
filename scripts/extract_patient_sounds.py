#!/usr/bin/env python3
"""
scripts/extract_patient_sounds.py
Remove likely conversation/background and keep respiratory event sounds.
"""

from __future__ import annotations

import argparse
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from edge_ml.real_audio import isolate_patient_sounds


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input wav/webm/ogg path")
    parser.add_argument("--output", required=True, help="Output wav path")
    parser.add_argument(
        "--model",
        default="models/respiratory_event_model.joblib",
        help="Trained model path (optional)",
    )
    parser.add_argument(
        "--target-labels",
        default="cough,sneeze,crackle,wheeze",
        help="Comma-separated labels to keep",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.45,
        help="Minimum confidence for keeping a predicted window",
    )
    args = parser.parse_args()

    labels = [x.strip().lower() for x in args.target_labels.split(",") if x.strip()]
    model_path = args.model if os.path.exists(args.model) else None

    result = isolate_patient_sounds(
        input_audio_path=args.input,
        output_audio_path=args.output,
        model_path=model_path,
        target_labels=labels,
        confidence_threshold=args.confidence,
    )

    print("=" * 60)
    print("Patient respiratory audio extraction completed")
    print("=" * 60)
    print(f"Output file     : {result['output_audio_path']}")
    print(f"Kept windows    : {result['kept_windows']}")
    print(f"Total windows   : {result['total_windows']}")
    if model_path is None:
        print("Mode            : Heuristic fallback (no model found)")
    else:
        print(f"Model used      : {model_path}")


if __name__ == "__main__":
    main()
