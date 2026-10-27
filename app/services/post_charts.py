"""Charts drawn from a story's data series, so the image fits what the result is: a curve over time, a trade-off, a before and after.

Every image keeps the portfolio identity (graphite ground, one sage accent, IBM Plex); what changes from post to post is the form,
chosen by the shape of the data, as in the owner's approved posts (a scatter of accuracy against download size, a line of problems
found against entries opened). Every point plotted is a number from the project's own documents (story_bank.verify_series).
"""

import math
import re

from PIL import Image

from app.services.post_visual import H, MARGIN, MUTED, TEXT, W, _accent, _canvas, _font, _footer, _header, _save, fit_text

GRID = (43, 48, 54)
SECOND = (168, 172, 178)  # a second series is drawn in the muted tone, never a second accent colour
KIND_NAMES = {"line": "Line chart", "scatter": "Scatter chart", "before_after": "Before and after"}


def number(value) -> float | None:
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(value))
    return float(m.group(0).replace(",", "")) if m else None


def _ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    if hi == lo:
        hi = lo + 1
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw)
    ticks, t = [], math.floor(lo / step) * step
    while t <= hi + step * 0.5:
        ticks.append(round(t, 10))
        t += step
    return ticks


def _fmt(v: float) -> str:
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    return f"{v:g}" if abs(v) >= 1 or v == 0 else f"{v:.3g}"


def _title(draw, story: dict, y: int) -> int:
    title = (story.get("series") or {}).get("title") or story["chart_title"]
    fitted = fit_text(draw, title, W - 2 * MARGIN, 2, [40, 36, 32, 28], bold=True)
    if fitted:
        font, lines = fitted
        for ln in lines:
            draw.text((MARGIN, y), ln, font=font, fill=TEXT)
            y += font.size + 10
    return y + 24


def _plot_area(draw, top: int, x_label: str, y_label: str, gutter: int = 20):
    left, right, bottom = MARGIN + 90, W - MARGIN - gutter, H - 260
    small = _font(24)
    draw.text((left, bottom + 62), x_label, font=small, fill=MUTED)
    draw.text((MARGIN, top - 4), y_label, font=small, fill=MUTED)
    return left, right, top + 60, bottom


def _axes(draw, box, xs: tuple[float, float], ys: tuple[float, float]):
    left, right, top, bottom = box
    small = _font(22)
    yt = _ticks(*ys)
    lo, hi = yt[0], yt[-1]

    def sy(v):
        return bottom - (v - lo) / (hi - lo) * (bottom - top)

    for t in yt:
        draw.line([(left, sy(t)), (right, sy(t))], fill=GRID, width=1)
        label = _fmt(t)
        draw.text((left - 14 - draw.textlength(label, font=small), sy(t) - 12), label, font=small, fill=MUTED)
    xt = _ticks(*xs)
    xlo, xhi = xt[0], xt[-1]

    def sx(v):
        return left + (v - xlo) / (xhi - xlo) * (right - left)

    for t in xt:
        label = _fmt(t)
        draw.text((sx(t) - draw.textlength(label, font=small) / 2, bottom + 14), label, font=small, fill=MUTED)
    draw.line([(left, bottom), (right, bottom)], fill=MUTED, width=2)
    return sx, sy


def _points(series: dict, label_key: str):
    pts = [(number(p.get("x")), number(p.get("y")), str(p.get(label_key) or "")) for p in series["points"]]
    return None if any(x is None or y is None for x, y, _ in pts) or len(pts) < 2 else pts


def _line(story: dict, item: dict) -> Image.Image | None:
    s = story["series"]
    pts = _points(s, "series")
    if not pts:
        return None
    accent = _accent(item["title"])
    img, draw = _canvas()
    y0 = _title(draw, story, _header(draw, item, accent))
    box = _plot_area(draw, y0, s.get("x_label", ""), s.get("y_label", ""), gutter=230)
    ys = [p[1] for p in pts]
    spread = (max(ys) - min(ys)) or abs(max(ys)) or 1
    # A line chart may start above zero: the change is the point, and the axis labels say where it starts.
    lo = 0 if min(ys) >= 0 and min(ys) < spread else min(ys) - spread * 0.15
    sx, sy = _axes(draw, box, (min(p[0] for p in pts), max(p[0] for p in pts)), (lo, max(ys) + spread * 0.05))
    f = _font(26, True)
    ends = []
    for n, name in enumerate(list(dict.fromkeys(p[2] for p in pts))[:2]):
        line = sorted((x, y) for x, y, g in pts if g == name)
        colour = accent if n == 0 else SECOND
        if len(line) > 1:
            draw.line([(sx(x), sy(y)) for x, y in line], fill=colour, width=6, joint="curve")
        for x, y in line:
            draw.ellipse([sx(x) - 7, sy(y) - 7, sx(x) + 7, sy(y) + 7], fill=colour)
        ends.append([sy(line[-1][1]), f"{name} {_fmt(line[-1][1])}".strip(), colour])
    # End labels sit in the right gutter, beside their last point, pushed apart when they would overlap.
    ends.sort()
    for k in range(1, len(ends)):
        ends[k][0] = max(ends[k][0], ends[k - 1][0] + 40)
    for y, tag, colour in ends:
        fitted = fit_text(draw, tag, 200, 2, [26, 24, 22], bold=True)
        tf, tl = fitted or (f, [tag])
        for k, ln in enumerate(tl):
            draw.text((box[1] + 20, y - 16 + k * (tf.size + 2)), ln, font=tf, fill=colour)
    _footer(draw)
    return img


def _scatter(story: dict, item: dict) -> Image.Image | None:
    s = story["series"]
    pts = _points(s, "label")
    if not pts:
        return None
    accent = _accent(item["title"])
    img, draw = _canvas()
    y0 = _title(draw, story, _header(draw, item, accent))
    box = _plot_area(draw, y0, s.get("x_label", ""), s.get("y_label", ""))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    xpad = (max(xs) - min(xs)) * 0.08 or 1
    ypad = (max(ys) - min(ys)) * 0.15 or 1
    xlo = max(0, min(xs) - xpad) if min(xs) >= 0 else min(xs) - xpad
    ylo = max(0, min(ys) - ypad) if min(ys) >= 0 else min(ys) - ypad
    sx, sy = _axes(draw, box, (xlo, max(xs) + xpad), (ylo, max(ys) + ypad * 0.6))
    best = max(pts, key=lambda p: p[1])
    f = _font(24, True)
    for x, y, label in pts:
        colour = accent if (x, y, label) == best else SECOND
        draw.ellipse([sx(x) - 12, sy(y) - 12, sx(x) + 12, sy(y) + 12], fill=colour)
        tag = f"{label} {_fmt(y)}".strip()
        tw = draw.textlength(tag, font=f)
        draw.text((min(max(sx(x) - tw / 2, box[0]), box[1] - tw), sy(y) - 46), tag, font=f, fill=colour)
    _footer(draw)
    return img


def _before_after(story: dict, item: dict) -> Image.Image | None:
    rows = story["series"]["points"][:4]
    if not rows or any(not (str(r.get("before", "")).strip() and str(r.get("after", "")).strip()) for r in rows):
        return None
    accent = _accent(item["title"])
    img, draw = _canvas()
    y = _title(draw, story, _header(draw, item, accent))
    # Rows share the whole card, so two changes do not leave the lower half empty.
    slot = min(330, (H - 190 - y) // len(rows))
    y += max(0, (H - 170 - y - slot * len(rows)) // 3)
    vf = _font(64 if slot < 260 else 96, True)
    for r in rows:
        fitted = fit_text(draw, str(r.get("label", "")), W - 2 * MARGIN, 1, [30, 28, 26, 24])
        if not fitted:
            return None
        lf, ll = fitted
        draw.text((MARGIN, y), ll[0], font=lf, fill=MUTED)
        before, after = str(r["before"]), str(r["after"])
        by = y + lf.size + 20
        draw.text((MARGIN, by), before, font=vf, fill=MUTED)
        ax = MARGIN + draw.textlength(before, font=vf) + 30
        if ax + 140 + draw.textlength(after, font=vf) > W - MARGIN:
            return None
        draw.line([(ax, by + 40), (ax + 90, by + 40)], fill=accent, width=6)
        draw.polygon([(ax + 90, by + 26), (ax + 114, by + 40), (ax + 90, by + 54)], fill=accent)
        draw.text((ax + 140, by), after, font=vf, fill=accent)
        y += slot
    _footer(draw)
    return img


RENDERERS = {"line": _line, "scatter": _scatter, "before_after": _before_after}


def stage_flow_results(story: dict) -> list[dict] | None:
    """Results that are steps of one process each scored on the same measure ("Member identification accuracy", "Message retrieval
    accuracy", ...): 2 to 5 results, all percentages, all labels ending in the same word. None otherwise."""
    results = story.get("results") or []
    if not 2 <= len(results) <= 5:
        return None
    if not all(str(r.get("value", "")).strip().endswith("%") for r in results):
        return None
    last = {r["label"].split()[-1].lower() for r in results if r.get("label")}
    return results if len(last) == 1 and all(len(r["label"].split()) >= 2 for r in results) else None


def render_stage_flow(story: dict, item: dict) -> tuple[str, str] | None:
    """The steps of a process as connected blocks down the card, each with its score as a large figure and a bar out of 100%, and
    the story's own detail (for example the one miss) as a note at the bottom, so a short result set still fills the card."""
    results = stage_flow_results(story)
    if not results:
        return None
    item = {**item, "simulated": story.get("simulated") or item.get("simulated")}
    accent = _accent(item["title"])
    img, draw = _canvas()
    y = _title(draw, story, _header(draw, item, accent))
    metric = results[0]["label"].split()[-1]
    detail = (story.get("detail") or "").strip()
    note_room = 170 if detail else 0
    slot = (H - 190 - y - note_room) // len(results)
    box_h = min(170, slot - 44)
    width = W - 2 * MARGIN
    for n, r in enumerate(results, 1):
        stage = " ".join(r["label"].split()[:-1])
        value = str(r["value"]).strip()
        pct = max(0.0, min(100.0, number(value) or 0.0))
        draw.rounded_rectangle([MARGIN, y, MARGIN + width, y + box_h], radius=14, fill=(24, 27, 31))
        draw.text((MARGIN + 28, y + 22), f"{n}", font=_font(30, True), fill=accent)
        fitted = fit_text(draw, stage, width - 330, 2, [34, 30, 28, 26], bold=True)
        if not fitted:
            return None
        sf, sl = fitted
        for k, ln in enumerate(sl):
            draw.text((MARGIN + 70, y + 20 + k * (sf.size + 4)), ln, font=sf, fill=TEXT)
        vf = _font(64, True)
        draw.text((MARGIN + width - 28 - draw.textlength(value, font=vf), y + 14), value, font=vf, fill=accent)
        bar_y = y + box_h - 40
        draw.rounded_rectangle([MARGIN + 70, bar_y, MARGIN + width - 28, bar_y + 14], radius=7, fill=GRID)
        draw.rounded_rectangle([MARGIN + 70, bar_y, MARGIN + 70 + int((width - 98) * pct / 100), bar_y + 14], radius=7, fill=accent)
        if n < len(results):
            cx = MARGIN + 40
            draw.line([(cx, y + box_h + 6), (cx, y + slot - 6)], fill=MUTED, width=3)
            draw.polygon([(cx - 9, y + slot - 16), (cx + 9, y + slot - 16), (cx, y + slot - 4)], fill=MUTED)
        y += slot
    draw.text((MARGIN, y - 24), f"{metric} of each step", font=_font(22), fill=MUTED)
    if detail:
        fitted = fit_text(draw, detail, width, 3, [30, 28, 26, 24])
        if fitted:
            df, dl = fitted
            ny = H - 170 - note_room + 20
            draw.line([(MARGIN, ny - 14), (MARGIN + 120, ny - 14)], fill=accent, width=4)
            for k, ln in enumerate(dl):
                draw.text((MARGIN, ny + k * (df.size + 8)), ln, font=df, fill=TEXT)
    _footer(draw)
    alt = (f"Process chart: {story['chart_title']}. " + "; then ".join(f"{' '.join(r['label'].split()[:-1])} {r['value']}"
                                                                        for r in results) + f" ({metric}).")
    if detail:
        alt += " " + detail
    if story.get("simulated"):
        alt += " Simulated data."
    return _save(img), alt


def series_alt(story: dict) -> str:
    s = story["series"]
    if s["type"] == "before_after":
        detail = "; ".join(f"{p.get('label')}: {p.get('before')} to {p.get('after')}" for p in s["points"][:4])
    else:
        detail = "; ".join(f"{(p.get('label') or p.get('series') or '').strip()} {s.get('x_label', 'x')} {p.get('x')}, "
                           f"{s.get('y_label', 'y')} {p.get('y')}".strip() for p in s["points"])
    alt = f"{KIND_NAMES[s['type']]}: {s.get('title') or story['chart_title']}. {detail}."
    return alt + (" Simulated data." if story.get("simulated") else "")


def render_series(story: dict, item: dict) -> tuple[str, str] | None:
    """The story's series as an image, or None when it has no usable series."""
    s = story.get("series") or {}
    renderer = RENDERERS.get(s.get("type"))
    if not renderer or not s.get("points"):
        return None
    try:
        img = renderer(story, {**item, "simulated": story.get("simulated") or item.get("simulated")})
    except Exception:
        return None
    return (_save(img), series_alt(story)) if img is not None else None
