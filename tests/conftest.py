import os, sys, shutil, subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
HW = ROOT / "hw"
sys.path.insert(0, str(ROOT))
KICAD_BIN = Path(os.environ.get("KICAD_BIN", r"C:\Program Files\KiCad\10.0\bin"))
KPY = KICAD_BIN / "python.exe"
KCLI = KICAD_BIN / "kicad-cli.exe"
KICAD_SHARE = KICAD_BIN.parent / "share" / "kicad"


def kpy(script, *args, check=True):
    """Run a script with KiCad's bundled Python (has pcbnew)."""
    r = subprocess.run([str(KPY), str(script), *map(str, args)], capture_output=True, text=True, cwd=ROOT)
    if check and r.returncode:
        raise AssertionError(f"{script} failed:\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}")
    return r


def kcli(*args, check=True):
    r = subprocess.run([str(KCLI), *map(str, args)], capture_output=True, text=True, cwd=ROOT)
    if check and r.returncode:
        raise AssertionError(f"kicad-cli {args} failed:\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}")
    return r


def pytest_configure(config):
    config.addinivalue_line("markers", "net: needs internet (JLC API)")
