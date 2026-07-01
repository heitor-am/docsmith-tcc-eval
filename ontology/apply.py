"""Applies the JSON Merge Patch of the diários oficiais ontology on top of
DocSmith's built-in juridico ontology for a target collection.

The patch adds domain entities (número do edital, secretaria municipal,
município, data de publicação) on top of the built-in legal ontology.
The DocSmith cache merges the built-in ontology into the collection's custom
ontology on every read, so this script only PATCHes the custom side.

Usage:
    DOCSMITH_API_KEY=<key> DOCSMITH_COLLECTION_ID=<uuid> \
        python ontology/apply.py

    # Preview without hitting the API:
    python ontology/apply.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

API_BASE = os.getenv("DOCSMITH_API_BASE", "http://localhost:8004/api/v1")
API_KEY = os.getenv("DOCSMITH_API_KEY")
COLLECTION_ID = os.getenv("DOCSMITH_COLLECTION_ID")
PATCH_FILE = Path(__file__).parent / "juridico-diarios.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--collection-id",
        default=COLLECTION_ID,
        help="Collection UUID (or set DOCSMITH_COLLECTION_ID).",
    )
    args = parser.parse_args()

    patch = json.loads(PATCH_FILE.read_text())
    n_new_classes = len(patch.get("classes", {}))
    print(f"patch: {n_new_classes} classes novas em {PATCH_FILE.name}")

    if args.dry_run:
        print("[DRY] no request sent")
        return

    if not API_KEY:
        sys.exit("ERRO: defina DOCSMITH_API_KEY")
    if not args.collection_id:
        sys.exit("ERRO: defina DOCSMITH_COLLECTION_ID ou passe --collection-id")

    with httpx.Client(
        base_url=API_BASE,
        headers={"X-API-Key": API_KEY},
        timeout=30.0,
    ) as client:
        url = f"/collections/{args.collection_id}/ontology"
        print(f"PATCH {API_BASE}{url}")
        try:
            resp = client.patch(url, json=patch)
            resp.raise_for_status()
            n_total = len(resp.json().get("classes", {}))
            print(f"[+] patch aplicado; {n_total} classes na ontologia custom")
        except httpx.HTTPStatusError as e:
            sys.exit(f"[erro] PATCH {e.response.status_code}: {e.response.text[:200]}")


if __name__ == "__main__":
    main()
