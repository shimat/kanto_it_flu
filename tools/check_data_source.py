import argparse
import json
import sys

from data import fetch_xls_data, merge_coordinates, parse_xls, read_coordinates_frame


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="東振協Excelのスキーマと座標網羅率を検査します。")
    parser.add_argument("--minimum-rows", type=int, default=3_000)
    parser.add_argument("--minimum-coordinate-coverage", type=float, default=0.80)
    args = parser.parse_args()

    last_update, facilities = parse_xls(fetch_xls_data())
    merged = merge_coordinates(facilities, read_coordinates_frame())
    mapped = merged[["longitude", "latitude"]].notna().all(axis=1)
    coverage = float(mapped.mean())
    report = {
        "last_update": last_update,
        "rows": len(facilities),
        "mapped_rows": int(mapped.sum()),
        "unmapped_rows": int((~mapped).sum()),
        "coordinate_coverage": round(coverage, 4),
        "duplicate_facilities": int(facilities.duplicated(["医療機関名称", "住所"]).sum()),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))

    errors = []
    if len(facilities) < args.minimum_rows:
        errors.append(f"rows={len(facilities)} < minimum={args.minimum_rows}")
    if coverage < args.minimum_coordinate_coverage:
        errors.append(f"coverage={coverage:.2%} < minimum={args.minimum_coordinate_coverage:.2%}")
    if errors:
        print("data health check failed: " + "; ".join(errors), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
