from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_report_renderer_sanitizes_marked_output() -> None:
    script = (ROOT / "frontend" / "assets" / "app.js").read_text(encoding="utf-8")

    assert "function sanitizeReportHtml" in script
    assert "sanitizeReportHtml(window.marked.parse(markdownText))" in script


def test_marked_dependency_is_version_pinned() -> None:
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

    assert "cdn.jsdelivr.net/npm/marked@" in html
    assert "cdn.jsdelivr.net/npm/marked/marked.min.js" not in html
