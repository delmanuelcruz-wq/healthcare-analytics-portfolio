"""Site tests: every project has an on-site case study, and no link on the published pages is broken."""
import re
from pathlib import Path
from urllib.parse import unquote

import pytest

ROOT = Path(__file__).resolve().parents[2]
REPO = "https://github.com/delmanuelcruz-wq/healthcare-analytics-portfolio/"
READMES = sorted([p for p in ROOT.glob("*/README.md") if p.parent.name not in {"foundation", "shared", "_private", ".venv"}]
                 + list(ROOT.glob("tier*/*/README.md")))
PAGES = [ROOT / "index.html"] + [r.parent / "case-study.html" for r in READMES]


def links(page: Path):
    text = page.read_text(encoding="utf-8")
    return re.findall(r'(?:href|src)="([^"]+)"', text)


def test_every_project_has_a_case_study_page():
    assert len(READMES) == 12
    for r in READMES:
        assert (r.parent / "case-study.html").exists(), r


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_no_broken_links(page):
    for url in links(page):
        if url.startswith("#") or url.startswith("mailto:"):
            continue
        if url.startswith(REPO):
            # GitHub links must point at something that exists in the repository.
            path = re.sub(r"^(tree|blob)/main/?", "", url[len(REPO):]).split("#")[0]
            assert (ROOT / unquote(path)).exists(), (page.name, url)
            continue
        if url.startswith(("http://", "https://")):
            continue                                   # CDNs and external references
        target = (page.parent / unquote(url.split("#")[0])).resolve()
        assert target.exists(), (page.relative_to(ROOT).as_posix(), url)
        assert target.suffix != ".md", f"{page.name} links raw Markdown on the site: {url}"


def test_landing_page_case_study_links_stay_on_site():
    text = (ROOT / "index.html").read_text(encoding="utf-8")
    on_site = re.findall(r'href="([^"]+/case-study\.html)"', text)
    assert len(on_site) == 12
    assert ">Case study<" in text and REPO + "tree" not in text


def test_case_studies_keep_the_synthetic_label():
    for r in READMES:
        html = (r.parent / "case-study.html").read_text(encoding="utf-8")
        assert "SYNTHETIC DEMONSTRATION" in html
