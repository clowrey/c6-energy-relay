"""Part catalogue: stock at JLC, datasheet-backed ratings, footprints that resolve."""
import pytest
from conftest import HW, KICAD_SHARE

from hw import parts
from hw.parts import PARTS

BOARDS = 30


@pytest.mark.net
@pytest.mark.parametrize("key", [k for k, p in PARTS.items() if p.lcsc])
def test_all_parts_in_stock_for_30(key):
    from hw.tools import jlc
    p = PARTS[key]
    info = jlc.lookup(p.lcsc)
    need = BOARDS * p.per_board
    assert info["stock"] >= need, f"{key} {p.lcsc}: stock {info['stock']} < {need}"


def test_ldo_dropout():
    """On USB power +5V is VBUS less D1 (SS14, ~0.5 V): 4.5 V must still cover 3.3 V plus the dropout at the
    module's transmit peak, and the regulator must carry that peak."""
    ldo, esp = PARTS["ldo"], PARTS["esp"]
    assert ldo.extra["dropout_at_ma"] >= esp.extra["tx_peak_ma"]
    assert 5.0 - 0.5 >= 3.3 + ldo.extra["dropout_mv"] / 1000
    assert ldo.extra["imax_ma"] >= 600


def test_terminal_508_rating():
    assert PARTS["term508_hdr"].extra["rated_a"] >= 15


def _fp_file(fp: str):
    lib, name = fp.split(":")
    if lib == "c6er":
        return HW / "lib" / "c6er.pretty" / f"{name}.kicad_mod"
    return KICAD_SHARE / "footprints" / f"{lib}.pretty" / f"{name}.kicad_mod"


@pytest.mark.parametrize("key", [k for k, p in PARTS.items() if p.footprint and not p.footprint.startswith("c6er:")])
def test_footprints_exist(key):
    assert _fp_file(PARTS[key].footprint).is_file(), PARTS[key].footprint


def test_every_placed_part_has_lcsc():
    for k, p in PARTS.items():
        if p.footprint:
            assert p.lcsc.startswith("C"), k


def test_price_at_tiers():
    from hw.tools import jlc
    prices = [(1, 0.5), (10, 0.4), (100, 0.3)]
    assert jlc.price_at(prices, 1) == 0.5
    assert jlc.price_at(prices, 30) == 0.4
    assert jlc.price_at(prices, 500) == 0.3
