"""Offline tests for HypeWatch parsing (no network)."""

from hypecheck.hypewatch import _conclusion_from_abstract, iso_date, parse_release
import hypecheck.hypewatch as hw

RELEASE = """<html><body><article data-history-node-id="1">
<p class="nih-pretitle">Wednesday, October 14, 2026</p>
<h1>A drug may activate brown fat </h1>
<p class="nih-subtitle">Large study suggests a link.</p>
<p>In an NIH-funded study, scientists showed the drug boosts brown fat in mice. It was tested in 100 people.</p>
<p>&ldquo;This is a start,&rdquo; said Dr. Cohen.</p>
<p>NIH supported this research through grant X.</p>
<p>About the NIH: lots of boilerplate.</p>
</article>
<h2>Reference</h2><p>A. Author et al. Title. Nature. 2026. DOI: 10.1038/s41586-026-11162-7</p>
<div>Institute/Center</div><div>National Institute of Diabetes</div>
</body></html>"""


def test_parse_release(monkeypatch):
    monkeypatch.setattr(hw, "get", lambda url, polite=True: RELEASE)
    r = parse_release("https://www.nih.gov/x")
    assert r["title"] == "A drug may activate brown fat"
    assert r["subtitle"] == "Large study suggests a link."
    assert r["date"] == "Wednesday, October 14, 2026"
    assert r["doi"] == "10.1038/s41586-026-11162-7"
    assert r["body"][0].startswith("In an NIH-funded study")       # the date line is not a claim
    assert all("NIH supported" not in b and "About the" not in b for b in r["body"])  # boilerplate cut


def test_conclusion_extraction():
    assert _conclusion_from_abstract("Background x. Results y. Conclusions Deep learning captures z.") == "Deep learning captures z."
    assert _conclusion_from_abstract("BACKGROUND: x. CONCLUSIONS: Coffee was associated with lower risk.") == "Coffee was associated with lower risk."
    assert _conclusion_from_abstract("We found A. We also found B. This suggests C.") == "We also found B. This suggests C."


def test_iso_date():
    assert iso_date("Wednesday, October 14, 2026") == "2026-10-14"
    assert iso_date("Media Advisory Thursday, May 22, 2025") == "2025-05-22"
    assert iso_date("not a date") == ""


def test_every_headline_number_reproduces_offline():
    import subprocess
    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / "research" / "reproduce.py"
    out = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stdout[-2000:] + out.stderr[-2000:]
    assert "21 of 21 headline numbers reproduce" in out.stdout
