#!/usr/bin/env python3
"""
Train a DeepDerm acne detector with Ultralytics YOLO11.

Example:
    python training/train_yolo11.py \
      --data datasets/deepderm_acne/data.yaml \
      --model yolo11s.pt \
      --epochs 100
"""
from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train DeepDerm YOLO11 acne detector")
    parser.add_argument("--data", required=True, help="Path to YOLO data.yaml")
    parser.add_argument("--model", default="yolo11s.pt", help="YOLO11 base model or checkpoint")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--project", default="runs/deepderm")
    parser.add_argument("--name", default="acne-yolo11s-v1")
    parser.add_argument("--device", default=None, help="Optional device, e.g. 0, cpu, mps")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_path = Path(args.data)
    if not data_path.exists():
        raise FileNotFoundError(f"Dataset config not found: {data_path}")

    model = YOLO(args.model)
    model.train(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        patience=args.patience,
        project=args.project,
        name=args.name,
        device=args.device,
    )

    print()
    print("Training complete.")
    print(f"Set DERMAI_MODEL_PATH to: {args.project}/{args.name}/weights/best.pt")
    print(f"Set DERMAI_MODEL_VERSION to: {args.name}")


if __name__ == "__main__":
    main()

