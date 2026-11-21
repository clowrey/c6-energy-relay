"""ESPHome starter config: pins agree with hw/design.py, and ESPHome accepts it."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import ROOT

from hw import design

YAML = ROOT / "firmware" / "c6-energy-relay.yaml"
ESPHOME_WSL = "/home/devcontainers/.local/bin/esphome-wsl"


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


@pytest.mark.skipif(shutil.which("wsl") is None, reason="WSL not available")
def test_esphome_config_valid(tmp_path):
    work = ROOT / "firmware" / ".validate"
    work.mkdir(exist_ok=True)
    try:
        shutil.copy(YAML, work / YAML.name)
        (work / "secrets.yaml").write_text('wifi_ssid: "test"\nwifi_password: "testtest"\n'
                                           'api_key: "MTIzNDU2Nzg5MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTI="\n'
                                           'ota_password: "test"\nap_password: "testtest"\n')
        wpath = "/mnt/" + str(work / YAML.name).replace(":", "").replace("\\", "/")
        wpath = wpath[:5] + wpath[5].lower() + wpath[6:]
        r = subprocess.run(["wsl", "-d", "Ubuntu", "-e", ESPHOME_WSL, "config", wpath],
                           capture_output=True, text=True, timeout=600)
        assert r.returncode == 0, (r.stdout[-3000:] + r.stderr[-3000:])
    finally:
        shutil.rmtree(work, ignore_errors=True)
