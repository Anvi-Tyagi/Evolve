"""Load EV_data/New/, validate it, and write outputs/ (tidy CSV + validation report).

Usage: python run.py [--data-dir DIR] [--out-dir DIR]
Exit code is 1 if any validation error was found, 0 otherwise.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from evolve import config  # noqa: E402
from evolve.load import load_all, to_long  # noqa: E402
from evolve.validate import has_errors, render_report, validate_all  # noqa: E402

LONG_CSV = "ev_registrations_long.csv"
REPORT_MD = "validation_report.md"


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=config.DATA_DIR)
    parser.add_argument("--out-dir", type=Path, default=config.OUTPUT_DIR)
    args = parser.parse_args(argv)

    if _inside(args.out_dir, config.PROTECTED_DIR):
        parser.error(f"refusing to write into {config.PROTECTED_DIR} (raw data directory)")

    result = load_all(args.data_dir)
    issues = validate_all(result)
    long = to_long(result.frame) if not result.frame.empty else None
    n_rows = 0 if long is None else len(long)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    if long is not None:
        long.to_csv(args.out_dir / LONG_CSV, index=False)
    (args.out_dir / REPORT_MD).write_text(render_report(issues, result.frame, n_rows), encoding="utf-8")

    failed = has_errors(issues)
    print(f"{'FAILED' if failed else 'PASSED'}: {n_rows:,} rows -> {args.out_dir / LONG_CSV}; "
          f"report -> {args.out_dir / REPORT_MD}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
