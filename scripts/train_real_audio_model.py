#!/usr/bin/env python3
"""
scripts/train_real_audio_model.py
Train respiratory event classifier from a real dataset manifest.

Manifest format (CSV):
  audio_path,label
  data/cough/file1.wav,cough
  data/sneeze/file2.wav,sneeze
  data/crackle/file3.wav,crackle
  data/speech/file4.wav,speech
"""

from __future__ import annotations

import argparse
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from edge_ml.real_audio import train_from_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, help="CSV with audio_path,label columns")
    parser.add_argument(
        "--base-dir",
        default=None,
        help="Base directory used to resolve relative audio_path entries",
    )
    parser.add_argument(
        "--output",
        default="models/respiratory_event_model.joblib",
        help="Output model path",
    )
    args = parser.parse_args()

    result = train_from_manifest(
        manifest_csv=args.manifest,
        output_model=args.output,
        base_dir=args.base_dir,
    )

    print("=" * 60)
    print("Real-audio classifier trained")
    print("=" * 60)
    print(f"Samples     : {result['num_samples']}")
    print(f"Labels      : {', '.join(result['labels'])}")
    print(f"Macro F1    : {result['macro_f1']:.3f}")
    print(f"Model saved : {result['model_path']}")


if __name__ == "__main__":
    main()
