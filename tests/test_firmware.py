"""ESPHome starter config: pins agree with hw/design.py, and ESPHome accepts it."""
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import ROOT

from hw import design

YAML = ROOT / "firmware" / "c6-energy-relay.yaml"


def _esphome():
    """How to run ESPHome here: $ESPHOME_CMD, else `esphome` on PATH, else `esphome-wsl` inside WSL
    (a wrapper on the WSL user's PATH). None: skip the check."""
    if os.environ.get("ESPHOME_CMD"):
        return shlex.split(os.environ["ESPHOME_CMD"]), False
    if shutil.which("esphome"):
        return ["esphome"], False
    if shutil.which("wsl"):
        return ["wsl", "-d", os.environ.get("ESPHOME_WSL_DISTRO", "Ubuntu"), "-e", "bash", "-lc"], True
    return None, False


def _pin(key):
    m = re.search(rf"^\s*{key}:\s*GPIO(\d+)", YAML.read_text(), re.M)
    assert m, key
    return int(m.group(1))


def test_pins_match_design():
    text = YAML.read_text()
    assert _pin("uart_tx_pin") == design.GPIO["UART_TX"]
    assert _pin("uart_rx_pin") == design.GPIO["UART_RX"]
    for name, gpio in (("RELAY1", "relay1_pin"), ("RELAY2", "relay2_pin"), ("LED", "led_pin"), ("BOOT", "boot_pin")):
        m = re.search(rf"^\s*{gpio}:\s*GPIO(\d+)", text, re.M)
        assert m and int(m.group(1)) == design.GPIO[name], name
    assert "baud_rate: 4800" in text


def test_esphome_config_valid(tmp_path):
    cmd, in_wsl = _esphome()
    if cmd is None:
        pytest.skip("ESPHome not found (set ESPHOME_CMD)")
    work = ROOT / "firmware" / ".validate"
    work.mkdir(exist_ok=True)
    try:
        shutil.copy(YAML, work / YAML.name)
        (work / "secrets.yaml").write_text('wifi_ssid: "test"\nwifi_password: "testtest"\n'
                                           'api_key: "MTIzNDU2Nzg5MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTI="\n'
                                           'ota_password: "test"\nap_password: "testtest"\n')
        if in_wsl:
            wpath = "/mnt/" + str(work / YAML.name).replace(":", "").replace("\\", "/")
            wpath = wpath[:5] + wpath[5].lower() + wpath[6:]
            args = cmd + [f"esphome-wsl config '{wpath}'"]
        else:
            args = cmd + ["config", str(work / YAML.name)]
        r = subprocess.run(args, capture_output=True, text=True, timeout=600)
        if in_wsl and r.returncode == 127:
            pytest.skip("esphome-wsl not found in WSL (set ESPHOME_CMD)")
        assert r.returncode == 0, (r.stdout[-3000:] + r.stderr[-3000:])
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_energy_uses_power_calibration():
    """Energy is power x time: each energy sensor must carry the same factor as its power sensor."""
    text = YAML.read_text()
    for sensor, cal in (("energy_1", "power1_cal"), ("energy_2", "power2_cal")):
        block = re.search(rf"^\s*{sensor}:\n((?:\s{{6,}}.*\n)+)", text, re.M)
        assert block and f"multiply: ${{{cal}}}" in block.group(1), sensor
    block = re.search(r"^\s*energy_total:\n((?:\s{6,}.*\n)+)", text, re.M)
    assert block and "multiply" in block.group(1)


def _sub(key):
    m = re.search(rf'^\s*{key}:\s*"([\d.]+)"', YAML.read_text(), re.M)
    assert m, key
    return float(m.group(1))


def test_starting_calibration_matches_hardware():
    """ESPHome's bl0939 scales for a 1 mOhm shunt and a 0.51k / (5 x 390k + 0.51k) divider. The
    starting factors convert that to this board's CTs and ZMPT107 front end, within 2 %."""
    from hw import parts
    vals = {k: p.value for k, p in parts.PARTS.items()}
    ohms = lambda v: float(v.split()[0].replace("R", ".").rstrip(".").replace("k", "e3"))
    from hw import design
    divider = [c for c in design.COMPONENTS if c.block == "vsense" and c.ref in ("R1", "R2", "R3", "R4", "R5")]
    r_divider = sum(ohms(vals[c.part]) for c in divider)
    ct_ratio = 100 / 0.050                              # SCT-013-000: 100 A : 50 mA
    mv_per_a = 1000 * 2 * ohms(vals["r0r3"]) / ct_ratio  # burden: two 0.3 ohm in series
    v_per_v = ohms(vals[design.comp("R6").part]) / r_divider   # ZMPT107 is 2 mA : 2 mA
    esphome_v_per_v = 0.51 / (5 * 390 + 0.51)
    want = {"current1_cal": 1.0 / mv_per_a, "current2_cal": 1.0 / mv_per_a,
            "voltage_cal": esphome_v_per_v / v_per_v}
    want["power1_cal"] = want["power2_cal"] = want["current1_cal"] * want["voltage_cal"]
    for k, v in want.items():
        assert abs(_sub(k) / v - 1) < 0.02, (k, _sub(k), round(v, 3))


def test_relays_start_off():
    """A relay never switches its load back on by itself after a reboot or power cut."""
    modes = re.findall(r"^\s*restore_mode:\s*(\S+)", YAML.read_text(), re.M)
    assert modes == ["ALWAYS_OFF", "ALWAYS_OFF"]
