import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from evolve import config

RUN = config.REPO_ROOT / "run.py"


def _snapshot(d: Path):
    return {p: p.stat().st_mtime_ns for p in d.rglob("*") if p.is_file()}


def _run(*args):
    return subprocess.run([sys.executable, str(RUN), *args], capture_output=True, text=True)


def test_end_to_end(tmp_path):
    before = _snapshot(config.PROTECTED_DIR)
    proc = _run("--out-dir", str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert _snapshot(config.PROTECTED_DIR) == before  # nothing written under EV_data/

    long = pd.read_csv(tmp_path / "ev_registrations_long.csv")
    assert list(long.columns) == ["state", "year", "category", "count"]
    assert long.groupby("year")["count"].sum().to_dict() == config.EXPECTED_NATIONAL_TOTALS
    assert "**Status: PASSED**" in (tmp_path / "validation_report.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("sub", ["", "New", "out"])
def test_refuses_to_write_into_ev_data(sub):
    target = config.PROTECTED_DIR / sub if sub else config.PROTECTED_DIR
    proc = _run("--out-dir", str(target))
    assert proc.returncode != 0
    assert "refusing" in proc.stderr
    if sub == "out":
        assert not target.exists()


def test_fails_on_bad_data(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    df = pd.read_csv(config.DATA_DIR / "ev_2020.csv")
    df.loc[0, "car"] = -5
    df.to_csv(data / "ev_2020.csv", index=False)
    out = tmp_path / "out"
    proc = _run("--data-dir", str(data), "--out-dir", str(out))
    assert proc.returncode == 1
    report = (out / "validation_report.md").read_text(encoding="utf-8")
    assert "**Status: FAILED**" in report
    assert "missing_file" in report  # 2021-2025 absent in this temp dir
