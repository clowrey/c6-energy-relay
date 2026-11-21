"""Download datasheets for catalogue parts into hw/datasheets/ (git-ignored). LCSC pages wrap the PDF.

    python -m hw.tools.fetch_datasheets key=C12345 ...
"""
import pathlib
import re
import sys
import urllib.request

from hw.tools import jlc

OUT = pathlib.Path(__file__).resolve().parents[1] / "datasheets"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.lcsc.com/"})
    return urllib.request.urlopen(req, timeout=60).read()


def fetch(key, lcsc):
    url = jlc.lookup(lcsc)["datasheet"]
    for _ in range(4):
        data = get(url)
        if data[:4] == b"%PDF":
            OUT.mkdir(exist_ok=True)
            p = OUT / f"{key}_{lcsc}.pdf"
            p.write_bytes(data)
            return p
        m = re.search(rb"https://(?:datasheet|wmsc)\.lcsc\.com/[^\"'\s<>]+?\.pdf[^\"'\s<>]*", data)
        if not m:
            raise RuntimeError(f"no pdf link in {url}")
        url = m.group(0).decode().replace("&amp;", "&")
    raise RuntimeError(f"too many redirects for {lcsc}")


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        k, c = arg.split("=")
        try:
            print(k, fetch(k, c))
        except Exception as e:
            print("ERR", k, c, e)
