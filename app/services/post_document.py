"""A multi-page document (LinkedIn shows a PDF post as a swipeable carousel) built from one story.

The owner's first approved post went out with an 8-page document; a story with enough material gets the same treatment: the question,
how it was tested, the results chart, the decision, and where the code and findings live. Every page is drawn from the story alone,
whose numbers were checked against the project's own documents, in the same graphite-and-sage identity as the single images.
"""

import os
import tempfile

from PIL import Image

from app.services.post_charts import render_series
from app.services.post_visual import (ACCENTS, BG, H, MARGIN, MUTED, TEXT, W, _accent, _canvas, _font, _footer, _header, fit_text,
                                      render_story_chart)

# A story gets a document instead of a single image when it has this many results (enough for a results page that is not thin).
MIN_RESULTS_FOR_DOCUMENT = 4


def wants_document(story: dict) -> bool:
    return len(story.get("results", [])) >= MIN_RESULTS_FOR_DOCUMENT


def _cover(story: dict, item: dict, total: int) -> Image.Image | None:
    """Title page: the question large and centred in the free space, with the simulated-data note when it applies."""
    accent = _accent(item["title"])
    img, draw = _canvas()
    top = _header(draw, item, accent)
    fitted = fit_text(draw, story["question"], W - 2 * MARGIN, 7, [72, 64, 58, 52, 46], bold=True)
    if not fitted:
        return None
    font, lines = fitted
    block = len(lines) * (font.size + 16) + 120
    y = top + max(0, (H - 170 - top - block) // 2)
    draw.text((MARGIN, y), "THE QUESTION", font=_font(28, True), fill=accent)
    y += 70
    for ln in lines:
        draw.text((MARGIN, y), ln, font=font, fill=TEXT)
        y += font.size + 16
    draw.text((MARGIN, y + 30), "Swipe for the test, the results and the decision", font=_font(28), fill=MUTED)
    draw.text((W - MARGIN - 90, H - 95), f"1 / {total}", font=_font(24, True), fill=MUTED)
    _footer(draw)
    return img


def _text_page(item: dict, label: str, body: str, page: int, total: int, extra: list[str] | None = None) -> Image.Image | None:
    accent = _accent(item["title"])
    img, draw = _canvas()
    y = _header(draw, item, accent)
    draw.text((MARGIN, y), label.upper(), font=_font(28, True), fill=accent)
    y += 60
    fitted = fit_text(draw, body, W - 2 * MARGIN, 9, [52, 46, 42, 38, 34, 30], bold=True)
    if not fitted:
        return None
    font, lines = fitted
    for ln in lines:
        draw.text((MARGIN, y), ln, font=font, fill=TEXT)
        y += font.size + 14
    for line in extra or []:
        y += 24
        small = fit_text(draw, line, W - 2 * MARGIN, 3, [30, 28, 26])
        if not small:
            continue
        sf, sl = small
        for ln in sl:
            draw.text((MARGIN, y), ln, font=sf, fill=MUTED)
            y += sf.size + 8
    draw.text((W - MARGIN - 90, H - 95), f"{page} / {total}", font=_font(24, True), fill=MUTED)
    _footer(draw)
    return img


def comparison_grid(results: list[dict]) -> tuple[list[str], list[str], dict] | None:
    """Split labels like "Random Forest ROC AUC" / "XGBoost ROC AUC" into options (columns) and metrics (rows). None when the results
    are not a clean comparison: every label must end in a metric shared by at least two options."""
    labels = [r["label"].split() for r in results]
    suffixes: dict[str, int] = {}
    for words in labels:
        for k in range(1, len(words)):
            key = " ".join(words[-k:]).lower()
            suffixes[key] = suffixes.get(key, 0) + 1
    options, metrics, cells = [], [], {}
    for r, words in zip(results, labels):
        split = next((k for k in range(len(words) - 1, 0, -1) if suffixes.get(" ".join(words[-k:]).lower(), 0) >= 2), None)
        if split is None:
            return None
        option, metric = " ".join(words[:-split]), " ".join(words[-split:])
        if option not in options:
            options.append(option)
        if metric.lower() not in [m.lower() for m in metrics]:
            metrics.append(metric)
        cells[(option, metric.lower())] = str(r["value"])
    if len(options) < 2 or len(options) > 3:
        return None
    return options, metrics, cells


def _results_page(story: dict, item: dict, page: int, total: int, numbered: bool = True) -> Image.Image | None:
    """All of the story's results: a table of options against metrics when it is a comparison, otherwise the results chart."""
    grid = comparison_grid(story["results"])
    if not grid:
        chart = render_story_chart(story, item, " ".join(str(r["value"]) for r in story["results"]))
        return Image.open(chart[0]).convert("RGB") if chart else None
    options, metrics, cells = grid
    accent = _accent(item["title"])
    img, draw = _canvas()
    y = _header(draw, item, accent)
    fitted = fit_text(draw, story["chart_title"], W - 2 * MARGIN, 2, [40, 36, 32, 28], bold=True)
    if fitted:
        font, lines = fitted
        for ln in lines:
            draw.text((MARGIN, y), ln, font=font, fill=TEXT)
            y += font.size + 10
        y += 30
    label_w = 380
    col_w = (W - 2 * MARGIN - label_w) // len(options)
    row_h = min(110, (H - 170 - y) // (len(metrics) + 1))
    head = _font(30, True)
    for n, opt in enumerate(options):
        fitted = fit_text(draw, opt, col_w - 20, 2, [30, 26, 22], bold=True)
        if not fitted:
            return None
        f, ls = fitted
        for k, ln in enumerate(ls):
            draw.text((MARGIN + label_w + n * col_w, y + k * (f.size + 4)), ln, font=f, fill=accent)
    y += row_h
    vfont = _font(44, True)
    for metric in metrics:
        draw.line([(MARGIN, y - 14), (W - MARGIN, y - 14)], fill=(43, 48, 54), width=2)
        fitted = fit_text(draw, metric, label_w - 20, 2, [30, 26, 22])
        if not fitted:
            return None
        f, ls = fitted
        for k, ln in enumerate(ls):
            draw.text((MARGIN, y + k * (f.size + 4)), ln, font=f, fill=MUTED)
        for n, opt in enumerate(options):
            draw.text((MARGIN + label_w + n * col_w, y - 6), cells.get((opt, metric.lower()), "-"), font=vfont, fill=TEXT)
        y += row_h
    if numbered:
        draw.text((W - MARGIN - 90, H - 95), f"{page} / {total}", font=head, fill=MUTED)
    _footer(draw)
    return img


def _repo_line(story: dict) -> str:
    for src in story.get("sources", []):
        if "github.com/" in src:
            parts = src.split("github.com/")[1].split("/")
            if len(parts) >= 2:
                return f"Code and findings: github.com/{parts[0]}/{parts[1]}"
    return ""


def story_image(story: dict, item: dict, post_text: str) -> tuple[str, str, str] | None:
    """The single image for a story, in order of fit: its series chart (line, scatter or before and after), a table of options
    against metrics, then a chart of the results the post states. Returns (path, alt text, kind)."""
    series = render_series(story, item)
    if series:
        return series[0], series[1], (story.get("series") or {}).get("type", "series")
    if comparison_grid(story["results"]):
        page = _results_page(story, item, 0, 0, numbered=False)
        if page:
            fd, path = tempfile.mkstemp(prefix="curiosync_table_", suffix=".png")
            os.close(fd)
            page.save(path, "PNG")
            alt = f"Table: {story['chart_title']}. " + "; ".join(f"{r['label']} {r['value']}" for r in story["results"]) + "."
            return path, alt + (" Simulated data." if story.get("simulated") else ""), "table"
    chart = render_story_chart(story, item, post_text)
    return (chart[0], chart[1], "results chart") if chart else None


def render_story_document(story: dict, item: dict, post_text: str) -> tuple[str, list[str], str] | None:
    """Return (pdf path, page png paths, document title), or None if a page cannot be drawn without cutting text."""
    item = {**item, "simulated": story.get("simulated") or item.get("simulated")}
    series = render_series(story, item)
    extra = [Image.open(series[0]).convert("RGB")] if series else []
    total = 5 + len(extra)
    pages = [
        _cover(story, item, total),
        _text_page(item, "How it was tested", story["test"], 2, total, [story.get("detail") or ""]),
        # Every result in the story (all checked against the repository), not only those the post states.
        _results_page(story, item, 3, total),
    ] + extra
    pages.append(_text_page(item, "The decision", story["decision"], 4 + len(extra), total))
    skills = ", ".join(story.get("skills", []))
    pages.append(_text_page(item, "Where to see it", _repo_line(story) or item["title"], 5 + len(extra), total,
                            [f"Skills: {skills}" if skills else ""]))
    if any(p is None for p in pages):
        return None
    pngs = []
    for n, page in enumerate(pages, 1):
        fd, png = tempfile.mkstemp(prefix=f"curiosync_page{n}_", suffix=".png")
        os.close(fd)
        page.save(png, "PNG")
        pngs.append(png)
    fd, pdf = tempfile.mkstemp(prefix="curiosync_doc_", suffix=".pdf")
    os.close(fd)
    pages[0].save(pdf, "PDF", save_all=True, append_images=pages[1:], resolution=150)
    title = story["chart_title"] if len(story["chart_title"]) <= 60 else item["title"][:60]
    return pdf, pngs, title
