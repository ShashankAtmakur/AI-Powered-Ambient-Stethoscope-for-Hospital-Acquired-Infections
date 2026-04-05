#!/usr/bin/env python3
"""
scripts/build_real_audio_manifest.py
Build a combined training manifest from ICBHI, COUGHVID, and optional ESC-50 datasets.

Output CSV columns:
  audio_path,label,start_s,end_s,source

Notes:
- ICBHI contributes cycle-level labels: crackle/wheeze/ambient
- COUGHVID contributes file-level cough labels using cough_detected threshold
- ESC-50 optionally contributes file-level sneeze labels from the "sneezing" class
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


def _iter_icbhi_rows(icbhi_dir: Path) -> Iterable[dict[str, str]]:
    for ann in sorted(icbhi_dir.glob("*.txt")):
        wav = ann.with_suffix(".wav")
        if not wav.exists():
            continue
        try:
            lines = ann.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue

        for line in lines:
            parts = line.strip().split()
            if len(parts) < 4:
                continue
            try:
                start_s = float(parts[0])
                end_s = float(parts[1])
                crackle = int(parts[2])
                wheeze = int(parts[3])
            except ValueError:
                continue

            if end_s <= start_s:
                continue

            if crackle == 1:
                label = "crackle"
            elif wheeze == 1:
                label = "wheeze"
            else:
                label = "ambient"

            yield {
                "audio_path": str(wav),
                "label": label,
                "start_s": f"{start_s:.3f}",
                "end_s": f"{end_s:.3f}",
                "source": "icbhi",
            }


def _best_quality(row: dict[str, str]) -> str:
    values = []
    for i in range(1, 5):
        v = (row.get(f"quality_{i}") or "").strip().lower()
        if v:
            values.append(v)
    if "good" in values:
        return "good"
    if "ok" in values:
        return "ok"
    return values[0] if values else ""


def _iter_coughvid_rows(coughvid_dir: Path, cough_threshold: float) -> Iterable[dict[str, str]]:
    metadata = coughvid_dir / "metadata_compiled.csv"
    if not metadata.exists():
        return

    with metadata.open("r", newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            uid = (row.get("uuid") or "").strip()
            if not uid:
                continue

            audio_path = None
            for ext in (".wav", ".ogg", ".webm"):
                p = coughvid_dir / f"{uid}{ext}"
                if p.exists():
                    audio_path = p
                    break
            if audio_path is None:
                continue

            try:
                cough_detected = float((row.get("cough_detected") or "0").strip())
            except ValueError:
                cough_detected = 0.0

            quality = _best_quality(row)
            if cough_detected < cough_threshold:
                continue
            if quality and quality not in {"good", "ok"}:
                continue

            yield {
                "audio_path": str(audio_path),
                "label": "cough",
                "start_s": "",
                "end_s": "",
                "source": "coughvid",
            }


def _iter_esc50_rows(esc50_dir: Path) -> Iterable[dict[str, str]]:
    meta_csv = esc50_dir / "meta" / "esc50.csv"
    audio_dir = esc50_dir / "audio"
    if not meta_csv.exists() or not audio_dir.exists():
        return

    with meta_csv.open("r", newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            category = (row.get("category") or "").strip().lower()
            if category != "sneezing":
                continue

            filename = (row.get("filename") or "").strip()
            if not filename:
                continue

            audio_path = audio_dir / filename
            if not audio_path.exists():
                continue

            yield {
                "audio_path": str(audio_path),
                "label": "sneeze",
                "start_s": "",
                "end_s": "",
                "source": "esc50",
            }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--icbhi-dir", required=True)
    parser.add_argument("--coughvid-dir", required=True)
    parser.add_argument(
        "--esc50-dir",
        default="",
        help="Optional ESC-50 root directory containing meta/esc50.csv and audio/",
    )
    parser.add_argument("--output", default="datasets/real_audio_manifest.csv")
    parser.add_argument("--cough-threshold", type=float, default=0.8)
    args = parser.parse_args()

    icbhi_dir = Path(args.icbhi_dir)
    coughvid_dir = Path(args.coughvid_dir)
    esc50_dir = Path(args.esc50_dir) if args.esc50_dir else None
    output = Path(args.output)

    rows = []
    rows.extend(_iter_icbhi_rows(icbhi_dir))
    rows.extend(_iter_coughvid_rows(coughvid_dir, args.cough_threshold))
    if esc50_dir is not None:
        rows.extend(_iter_esc50_rows(esc50_dir))

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["audio_path", "label", "start_s", "end_s", "source"],
        )
        writer.writeheader()
        writer.writerows(rows)

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["label"]] = counts.get(row["label"], 0) + 1

    print("=" * 60)
    print("Manifest generated")
    print("=" * 60)
    print(f"Output: {output}")
    print(f"Rows  : {len(rows)}")
    print("Labels:")
    for k in sorted(counts):
        print(f"  - {k}: {counts[k]}")


if __name__ == "__main__":
    main()
