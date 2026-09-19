"""Validate Flink + Iceberg catalog configuration for release gates."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path


CATALOG_REQUIRED = {
    "hive": ["ICEBERG_HIVE_METASTORE_URI", "ICEBERG_WAREHOUSE"],
    "glue": ["AWS_REGION", "ICEBERG_WAREHOUSE"],
    "nessie": ["NESSIE_URI", "NESSIE_REF", "ICEBERG_WAREHOUSE"],
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Flink/Iceberg config")
    parser.add_argument("--catalog-type", default=os.getenv("ICEBERG_CATALOG_TYPE", ""))
    parser.add_argument("--out-json", default="stress/flink_iceberg_config_report.json")
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    catalog = str(args.catalog_type or "").strip().lower()
    required = CATALOG_REQUIRED.get(catalog, [])
    missing = [name for name in required if not str(os.getenv(name, "")).strip()]

    passed = bool(required) and not missing
    result = {
        "generatedAt": int(time.time()),
        "catalogType": catalog,
        "requiredKeys": required,
        "missingKeys": missing,
        "pass": passed,
    }

    out = root / args.out_json
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated: {out}")
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())

