#!/usr/bin/env python3
"""
test_analyze.py
===============
CLI test script — sends a local image to POST /analyze and pretty-prints
the JSON response.

Usage:
    python test_analyze.py --image /path/to/face.jpg [--url http://localhost:8000]

Dependencies: httpx (already in requirements.txt)
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send a face photo to the DermAI /analyze endpoint"
    )
    parser.add_argument(
        "--image",
        required=True,
        help="Path to the face image (JPEG/PNG/WEBP)",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the DermAI service (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--photo-id",
        default=str(uuid.uuid4()),
        help="UUID to use as photo_id (auto-generated if omitted)",
    )
    parser.add_argument(
        "--patient-id",
        default=str(uuid.uuid4()),
        help="UUID to use as patient_id (auto-generated if omitted)",
    )
    args = parser.parse_args()

    image_path = args.image
    endpoint   = f"{args.url.rstrip('/')}/analyze"

    print(f"\n{'='*60}")
    print(f"  DermAI Test Client")
    print(f"{'='*60}")
    print(f"  Endpoint  : {endpoint}")
    print(f"  Image     : {image_path}")
    print(f"  photo_id  : {args.photo_id}")
    print(f"  patient_id: {args.patient_id}")
    print(f"{'='*60}\n")

    # ── Health check first ────────────────────────────────────────────────────
    try:
        health_resp = httpx.get(f"{args.url}/health", timeout=5)
        health_resp.raise_for_status()
        health = health_resp.json()
        print(f"✅  Health: {health['status']} | model={health.get('model_version')} | loaded={health.get('model_loaded')}")
    except Exception as exc:
        print(f"⚠️  Health check failed: {exc}")
        print("    Proceeding with /analyze anyway …\n")

    # ── POST /analyze ─────────────────────────────────────────────────────────
    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
    except FileNotFoundError:
        print(f"❌  File not found: {image_path}", file=sys.stderr)
        sys.exit(1)

    print(f"\nSending {len(image_bytes) / 1024:.1f} KB image …\n")

    try:
        resp = httpx.post(
            endpoint,
            data={
                "photo_id":   args.photo_id,
                "patient_id": args.patient_id,
            },
            files={"image": ("photo.jpg", image_bytes, "image/jpeg")},
            timeout=60,  # inference can be slow on CPU first run
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        print(f"❌  HTTP {exc.response.status_code}: {exc.response.text}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"❌  Request failed: {exc}", file=sys.stderr)
        sys.exit(1)

    result = resp.json()

    # ── Pretty print ──────────────────────────────────────────────────────────
    print(f"{'='*60}")
    print(f"  ANALYSIS RESULT")
    print(f"{'='*60}")
    print(f"  Total lesions    : {result['total_lesion_count']}")
    print(f"  Severity         : {result.get('severity', {}).get('label_tr', 'N/A')}")
    print(f"  Clinical summary : {result.get('clinical_summary', 'N/A')}")
    print(f"  Model version    : {result.get('model_version', 'N/A')}")
    print(f"  Annotated image  : {result['annotated_image_url']}")
    print(f"  Analyzed at      : {result['analyzed_at']}")
    print()

    detections = result.get("detections", [])
    if not detections:
        print("  ⚠️  No detections found (try lowering DERMAI_CONF_THRESHOLD)")
    else:
        print(f"  Detections ({len(detections)}):")
        for i, d in enumerate(detections, 1):
            bbox = d["bbox"]
            print(
                f"    [{i}] {d['label']} ({d['label_en']})"
                f"  conf={d['confidence']:.2%}"
                f"  bbox=(x={bbox['x']}, y={bbox['y']}, w={bbox['w']}, h={bbox['h']})"
            )

    print()
    print("Full JSON response:")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
