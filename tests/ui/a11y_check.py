"""Accessibility and mobile check for the demo page (axe-core, WCAG 2.2 AA + best practice).

    pip install playwright && playwright install chromium
    python tests/ui/a11y_check.py http://127.0.0.1:8080/
Exits non-zero on any violation or horizontal overflow at 390 px.
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

site = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080/"
js = (Path(__file__).parent / "axe_run.js").read_text()
bad = 0
with sync_playwright() as p:
    b = p.chromium.launch()
    for scheme in ("light", "dark"):
        pg = b.new_page(viewport={"width": 1280, "height": 900}, color_scheme=scheme)
        pg.goto(site)
        pg.wait_for_timeout(1500)
        pg.add_script_tag(url="https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js")
        v = pg.evaluate(js)
        bad += len(v)
        print(scheme, "violations:", json.dumps(v, indent=1) if v else 0)
    m = b.new_page(viewport={"width": 390, "height": 844}, is_mobile=True)
    m.goto(site)
    m.wait_for_timeout(1000)
    overflow = m.evaluate("document.documentElement.scrollWidth > innerWidth")
    print("mobile horizontal overflow:", overflow)
    bad += int(overflow)
    b.close()
sys.exit(1 if bad else 0)
