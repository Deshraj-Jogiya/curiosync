"""The image that goes with a scheduled post.

Order of preference:
1. A real visual of the work (dashboard, app screenshot, chart) listed in assets/visuals/index.json for that subject.
2. A breakdown card (1080x1350, the 4:5 feed size) whose every label is checked against the subject's facts: no number or tool may appear
   that the facts do not contain, and text is shrunk to fit its box instead of being cut off.
3. A stat card built directly from the facts without any model call.
There is no generic fallback diagram: a picture must describe this subject or there is no picture.
"""

import hashlib
import json
import os
import re
import tempfile

from PIL import Image, ImageDraw, ImageFont

from app.services.post_rules import numbers_in, unsupported_numbers, unsupported_tools
from app.utils.logging import logger

W, H = 1080, 1350
MARGIN = 80
VISUALS_DIR = os.path.join("assets", "visuals")

# The portfolio's identity (graphite, one sage accent, IBM Plex, flat), so every card matches the site.
BG = (17, 19, 21)          # #111315
PANEL = (24, 27, 31)       # #181b1f
TEXT = (236, 235, 230)     # #ecebe6
MUTED = (168, 172, 178)    # #a8acb2
ACCENTS = [(140, 196, 173)]  # #8cc4ad, the only accent
FONTS_DIR = os.path.join("assets", "fonts")
FOOTER = "Deshraj Jogiya  |  Data Engineer & Machine Learning Engineer"


def _font_path(bold: bool) -> str | None:
    # IBM Plex ships in assets/fonts (SIL OFL); the system fonts are only a fallback.
    names = (["IBMPlexSansCondensed-Bold.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold
             else ["IBMPlexSans-Regular.ttf", "arial.ttf", "DejaVuSans.ttf"])
    dirs = [FONTS_DIR, os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"), "/usr/share/fonts/truetype/dejavu",
            "/System/Library/Fonts/Supplemental"]
    for d in dirs:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return p
    return None


def _font(size: int, bold: bool = False):
    path = _font_path(bold)
    return ImageFont.truetype(path, size) if path else ImageFont.load_default()


def _wrap(draw, text: str, font, width: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=font) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def fit_text(draw, text: str, width: int, max_lines: int, sizes: list[int], bold: bool = False):
    """Largest font size at which the whole text fits in max_lines; None if it never fits (the caller must not cut it)."""
    for size in sizes:
        font = _font(size, bold)
        lines = _wrap(draw, text, font, width)
        if len(lines) <= max_lines and all(draw.textlength(ln, font=font) <= width for ln in lines):
            return font, lines
    return None


def _accent(subject: str):
    return ACCENTS[int(hashlib.md5(subject.encode()).hexdigest(), 16) % len(ACCENTS)]


def _canvas():
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)


def _header(draw, item: dict, accent) -> int:
    y = MARGIN
    tag = item.get("context") or (item.get("org") or "")
    if item.get("simulated"):
        tag = (tag + "  |  " if tag else "") + "Simulated data"
    if tag:
        fitted = fit_text(draw, tag.upper(), W - 2 * MARGIN, 2, [26, 24, 22, 20], bold=True)
        if fitted:
            font, lines = fitted
            for ln in lines:
                draw.text((MARGIN, y), ln, font=font, fill=accent)
                y += font.size + 8
            y += 18
    title = re.sub(r":.*$", "", item["title"]) if len(item["title"]) > 60 else item["title"]
    fitted = fit_text(draw, title, W - 2 * MARGIN, 3, [64, 58, 52, 46, 40], bold=True)
    font, lines = fitted or (_font(40, True), _wrap(draw, title, _font(40, True), W - 2 * MARGIN)[:3])
    for ln in lines:
        draw.text((MARGIN, y), ln, font=font, fill=TEXT)
        y += font.size + 12
    draw.rectangle([MARGIN, y + 20, MARGIN + 120, y + 28], fill=accent)
    return y + 70


def _footer(draw):
    font = _font(24, True)
    draw.line([(MARGIN, H - 120), (W - MARGIN, H - 120)], fill=(43, 48, 54), width=2)
    draw.text((MARGIN, H - 95), FOOTER, font=font, fill=MUTED)


def _save(img) -> str:
    fd, path = tempfile.mkstemp(prefix="curiosync_", suffix=".png")
    os.close(fd)
    img.save(path, "PNG")
    return path


def render_breakdown(item: dict, meta: dict) -> str | None:
    """Card with an optional headline number and 3-4 steps. Returns None if any text cannot fit without cutting."""
    accent = _accent(item["title"])
    img, draw = _canvas()
    y = _header(draw, item, accent)
    inner = W - 2 * MARGIN - 60

    number, label = (meta.get("headline_number") or "").strip(), (meta.get("headline_label") or "").strip()
    if number and label:
        nfont = _font(120, True)
        draw.text((MARGIN, y), number, font=nfont, fill=accent)
        nw = draw.textlength(number, font=nfont)
        fitted = fit_text(draw, label, W - 2 * MARGIN - int(nw) - 30, 3, [34, 30, 28, 26])
        if not fitted:
            return None
        lfont, llines = fitted
        ly = y + (120 - len(llines) * (lfont.size + 6)) // 2 + 10
        for ln in llines:
            draw.text((MARGIN + nw + 30, ly), ln, font=lfont, fill=TEXT)
            ly += lfont.size + 6
        y += 170

    steps = meta.get("steps", [])[:4]
    footer_top = H - 150
    gap = 20
    box_h = (footer_top - y - gap * (len(steps) - 1)) // max(1, len(steps))
    if box_h < 130:
        return None
    for i, step in enumerate(steps, 1):
        draw.rounded_rectangle([MARGIN, y, W - MARGIN, y + box_h], radius=18, fill=PANEL)
        draw.ellipse([MARGIN + 28, y + 28, MARGIN + 76, y + 76], fill=accent)
        num_font = _font(28, True)
        draw.text((MARGIN + 52 - draw.textlength(str(i), font=num_font) / 2, y + 36), str(i), font=num_font, fill=BG)
        head = fit_text(draw, step.get("label", ""), inner - 60, 1, [34, 32, 30, 28, 26, 24], bold=True)
        if not head:
            return None
        hfont, hl = head
        draw.text((MARGIN + 100, y + 32), hl[0], font=hfont, fill=TEXT)
        avail_lines = max(1, (box_h - 32 - hfont.size - 18 - 16) // 32)
        body = fit_text(draw, step.get("detail", ""), inner - 60, avail_lines, [30, 28, 26, 24, 22])
        if not body:
            return None
        bfont, bl = body
        by = y + 32 + hfont.size + 18
        for ln in bl:
            draw.text((MARGIN + 100, by), ln, font=bfont, fill=MUTED)
            by += bfont.size + 8
        y += box_h + gap
    _footer(draw)
    return _save(img)


# A measured result: a percentage, a count with "+", a multiple, or a number with thousands separators.
_STRONG_NUMBER = re.compile(r"(?<![\w./])(?:\d[\d,]*(?:\.\d+)?\s*%|\d[\d,]*\+|\d[\d,]*(?:\.\d+)?x\b|\d{1,3}(?:,\d{3})+)(?![\w/])")
# A plain count is only a result when a counted noun follows it ("19 xUnit tests"), never a ratio ("80/20"), a year or a code.
_COUNT_NUMBER = re.compile(r"(?<![\w./])(\d{2,})(?=\s+(?:[\w-]+\s+){0,2}[a-z][\w-]*s\b)(?![\w/])")


def _numeric_facts(item: dict) -> list[tuple[str, str]]:
    """(number, sentence) pairs for the stat card: measured results first, each number used once."""
    strong, counts, seen = [], [], set()
    for fact in item["facts"]:
        text = re.sub(r"^[A-Z][\w &/-]{2,40}:\s*", "", fact)
        m = _STRONG_NUMBER.search(text)
        target = strong
        if not m:
            m = _COUNT_NUMBER.search(text)
            if not m or re.fullmatch(r"(?:19|20)\d\d", m.group(1)):
                continue
            target = counts
        number = m.group(0).replace(" ", "")
        if number in seen:
            continue  # the same figure restated in another fact
        seen.add(number)
        target.append((number, text))
    return strong + counts


def render_stat_card(item: dict) -> tuple[str, str]:
    """Up to three real numbers from the facts, each with its own fact sentence. No model involved."""
    accent = _accent(item["title"])
    img, draw = _canvas()
    y = _header(draw, item, accent)
    candidates = _numeric_facts(item) or [("", f) for f in sorted(item["facts"], key=len)]
    footer_top = H - 150
    slots = min(3, len(candidates))
    slot = min(330, (footer_top - y) // max(1, slots))
    # Keep only facts whose sentence fits under its number: a number is never drawn without the words that explain it.
    chosen = []
    for number, text in candidates:
        room = slot - (120 if number else 0) - 20
        fitted = fit_text(draw, text, W - 2 * MARGIN, max(2, room // 38), [32, 30, 28, 26, 24])
        if fitted:
            chosen.append((number, text, fitted))
        if len(chosen) == slots:
            break
    y += max(0, (footer_top - y - slot * len(chosen)) // 2)
    alt_parts = []
    for number, text, (font, lines) in chosen:
        ty = y
        if number:
            draw.text((MARGIN, y), number, font=_font(96, True), fill=accent)
            ty = y + 120
        for ln in lines:
            draw.text((MARGIN, ty), ln, font=font, fill=TEXT)
            ty += font.size + 8
        alt_parts.append(text)
        y += slot
    _footer(draw)
    alt = f"{item['title']}: " + " ".join(alt_parts)
    return _save(img), alt


METADATA_PROMPT = """Design the content of a portrait image card that summarizes the work below for a LinkedIn post.
Use only words, numbers and tools that appear in FACTS. Do not add any tool, number or claim that is not in FACTS.

Return only JSON:
{{"headline_number": "one number from FACTS such as 60% or 10,000+ (or empty string)",
  "headline_label": "what that number measures, at most 8 words",
  "steps": [{{"label": "at most 4 words", "detail": "at most 14 words"}}],
  "alt_text": "one or two sentences describing the card for screen readers"}}
Give 3 or 4 steps that walk through how the work was built, in order.
{sim}
FACTS:
{facts}
"""


async def build_visual(item: dict, settings, facts_source: str) -> tuple[str | None, str | None, str]:
    """Return (image path, alt text, kind) where kind is real, breakdown, stat or none."""
    real = _real_visual(item)
    if real:
        return real[0], real[1], "real"

    from app.services.llm_service import call_llm_with_fallback

    facts = "\n".join(f"- {f}" for f in item["facts"])
    sim = "This work used simulated or synthetic data." if item.get("simulated") else ""
    try:
        raw = await call_llm_with_fallback(
            messages=[{"role": "user", "content": METADATA_PROMPT.format(facts=facts, sim=sim)}], settings=settings, temperature=0.2)
        raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        meta = json.loads(raw)
        card_text = " ".join([meta.get("headline_number", ""), meta.get("headline_label", "")] +
                             [f"{s.get('label', '')} {s.get('detail', '')}" for s in meta.get("steps", [])])
        bad = unsupported_numbers(card_text, facts_source) + unsupported_tools(card_text, facts_source)
        if meta.get("headline_number") and not numbers_in(meta["headline_number"]):
            bad.append("headline is not a number")
        if bad or not 3 <= len(meta.get("steps", [])) <= 4:
            logger.warning("Breakdown card rejected: %s", bad or "wrong step count")
        else:
            path = render_breakdown(item, meta) or render_breakdown(item, {**meta, "steps": meta["steps"][:3]})
            if path:
                return path, meta.get("alt_text") or f"Summary of {item['title']}", "breakdown"
            logger.warning("Breakdown card text did not fit; using the stat card")
    except Exception as exc:
        logger.warning("Breakdown card failed (%s); using the stat card", exc)

    path, alt = render_stat_card(item)
    return path, alt, "stat"


def _real_visual(item: dict) -> tuple[str, str] | None:
    try:
        with open(os.path.join(VISUALS_DIR, "index.json"), encoding="utf-8") as f:
            index = json.load(f)
    except (OSError, ValueError):
        return None
    title = item["title"].lower()
    for key, entry in index.items():
        if title.startswith(key.lower()):
            path = os.path.join(VISUALS_DIR, entry["file"])
            if os.path.exists(path):
                # Callers delete the image after posting, so hand them a copy, never the file in the repo.
                copy = _save(Image.open(path).convert("RGB"))
                return copy, entry.get("alt", f"Screenshot of {item['title']}")
    return None


def _value_number(value: str) -> float | None:
    m = re.search(r"\d[\d,]*(?:\.\d+)?", value)
    return float(m.group(0).replace(",", "")) if m else None


def _unit(value: str) -> str:
    return re.sub(r"[\d,.\s]+", "", value).strip().lower()


def story_results_in_post(story: dict, post_text: str) -> list[dict]:
    """The story's results whose number the post itself states, so the image never shows a figure the text does not."""
    from app.services.post_rules import _exact_conversions, numbers_in

    in_post = numbers_in(post_text)
    in_post |= _exact_conversions(in_post)  # the post may write 0.9813 as 98.13%
    return [r for r in story["results"] if numbers_in(str(r["value"])) & in_post]


def _rate(value: str) -> float | None:
    """A score on a 0-1 scale: "86.20%" -> 0.862, "0.65" -> 0.65; None for anything else (counts, times, money)."""
    v = str(value).strip()
    n = _value_number(v)
    if n is None or v[:1] in "-+−":  # a signed figure is a change (a return of -2.58%), not a share of a whole
        return None
    if v.endswith("%"):
        return n / 100 if 0 <= n <= 100 else None
    return n if 0 <= n <= 1 and re.fullmatch(r"0?\.\d+|[01](?:\.0+)?", v) else None


def expand_pairs(results: list[dict]) -> list[dict]:
    """"Completed-contract precision / recall" = "0.89 / 0.94" becomes two results, so each value gets its own bar."""
    out = []
    for r in results:
        values = [x.strip() for x in str(r["value"]).split(" / ")]
        names = [x.strip() for x in r["label"].split(" / ")]
        if len(values) == 2 and len(names) == 2:
            prefix = names[0].rsplit(" ", 1)[0] if " " in names[0] else ""
            second = names[1] if " " in names[1] or not prefix else f"{prefix} {names[1]}"
            out += [{**r, "label": names[0], "value": values[0]}, {**r, "label": second, "value": values[1]}]
        else:
            out.append(r)
    return out


def _as_written(value: str, post_text: str) -> str:
    """0.9813 shown as "98.13%" when that is how the post writes it, so the image and the text read the same."""
    from app.services.post_rules import _exact_conversions, numbers_in

    v = str(value).strip()
    if v.endswith("%") or not post_text:
        return v
    shown = [n for n in _exact_conversions(numbers_in(v)) if n.endswith("%")]
    return shown[0] if shown and shown[0] in numbers_in(post_text) else v


def _rate_bars(story: dict, item: dict, results: list[dict], post_text: str = "") -> tuple[str, str] | None:
    """Bars on one fixed 0-1 axis (100% for percentages) with grid lines, so close scores look close and a weak one stands out:
    the lowest bar is drawn in the accent, the rest muted."""
    accent = _accent(item["title"])
    img, draw = _canvas()
    y = _header(draw, {**item, "simulated": story.get("simulated") or item.get("simulated")}, accent)
    width = W - 2 * MARGIN
    fitted = fit_text(draw, story["chart_title"], width, 2, [40, 36, 32, 28], bold=True)
    if fitted:
        font, lines = fitted
        for ln in lines:
            draw.text((MARGIN, y), ln, font=font, fill=TEXT)
            y += font.size + 10
        y += 20
    results = [{**r, "value": _as_written(r["value"], post_text)} for r in results]
    rates = [_rate(r["value"]) for r in results]
    low = min(rates)
    top = y + 40
    slot = min((H - 190 - top) // len(results), 190)  # keep a few bars together instead of spreading them over the card
    bottom = top + slot * len(results)
    bar_h = min(56, slot - 52)
    tick_font = _font(26)
    for k in range(5):  # 0, 0.25, 0.5, 0.75, 1
        x = MARGIN + int(width * k / 4)
        label = f"{k * 25}%" if any(str(r["value"]).endswith("%") for r in results) else f"{k / 4:g}"
        tw = draw.textlength(label, font=tick_font)
        draw.text((min(max(x - tw / 2, MARGIN), W - MARGIN - tw), bottom + 12), label, font=tick_font, fill=MUTED)
    for n, (r, v) in enumerate(zip(results, rates)):
        ty = top + n * slot
        lf = fit_text(draw, r["label"], width - 160, 1, [30, 28, 26, 24])
        if not lf:
            return None
        draw.text((MARGIN, ty), lf[1][0], font=lf[0], fill=TEXT)
        by = ty + lf[0].size + 12
        draw.rounded_rectangle([MARGIN, by, MARGIN + width, by + bar_h], radius=6, fill=PANEL)
        for k in range(1, 4):  # quarter marks inside the track only, clear of the labels
            gx = MARGIN + int(width * k / 4)
            draw.line([(gx, by), (gx, by + bar_h)], fill=(52, 58, 64), width=2)
        draw.rounded_rectangle([MARGIN, by, MARGIN + max(8, int(width * v)), by + bar_h], radius=6,
                               fill=accent if v == low else (96, 110, 104))
        vf = _font(34, True)
        value = str(r["value"])
        draw.text((W - MARGIN - draw.textlength(value, font=vf), ty - 2), value, font=vf, fill=accent if v == low else TEXT)
    _footer(draw)
    alt = f"Bar chart, {story['chart_title']}: " + "; ".join(f"{r['label']} {r['value']}" for r in results) + "."
    if story.get("simulated"):
        alt += " Simulated data."
    return _save(img), alt


_TOTAL_LABEL = re.compile(r"\b(?:total|whole|overall|end[- ]to[- ]end)\b", re.IGNORECASE)


def parts_of_total(results: list[dict]) -> tuple[list[dict], dict, list[dict]] | None:
    """(parts, total, other totals) when 2+ results in one unit add up to a result labelled total (within 2%, as medians of stages
    need not sum exactly): decode 76.2 + hands 997.0 + model 8.9 against a total of 1081.2 ms. Else None."""
    totals = [r for r in results if _TOTAL_LABEL.search(r["label"]) and _value_number(str(r["value"])) is not None]
    parts = [r for r in results if r not in totals and _value_number(str(r["value"])) is not None]
    if not totals or len(parts) < 2 or len({_unit(str(r["value"])) for r in parts + totals}) != 1:
        return None
    whole = sum(_value_number(str(r["value"])) for r in parts)
    for t in totals:
        tv = _value_number(str(t["value"]))
        if tv and abs(whole - tv) / tv <= 0.02:
            return sorted(parts, key=lambda r: -_value_number(str(r["value"]))), t, [o for o in totals if o is not t]
    return None


def _short_labels(rows: list[dict]) -> tuple[list[str], str]:
    """Labels without the word every one of them repeats ("Median ... time"), and that word said once: ("Hand features", ...), "Median"."""
    labels = [r["label"].strip() for r in rows]
    stat = ""
    m = re.match(r"(median|mean|average|p\d\d)\s+", labels[0], re.IGNORECASE)
    if m and all(lb.lower().startswith(m.group(1).lower() + " ") for lb in labels):
        stat = m.group(1).capitalize()
        labels = [lb[len(m.group(0)):] for lb in labels]
    if sum(lb.lower().endswith(" time") for lb in labels) >= 2:
        labels = [lb[:-5] if lb.lower().endswith(" time") else lb for lb in labels]
    return [lb[:1].upper() + lb[1:] for lb in labels], stat


def _parts_chart(story: dict, item: dict, parts: list[dict], total: dict, others: list[dict]) -> tuple[str, str]:
    """One bar split into the parts of a total, largest first, so a reader sees at once which part takes the time; each part is listed
    under it with its own value, and the total (and any wider total, such as the whole request) closes the card."""
    accent = _accent(item["title"])
    img, draw = _canvas()
    y = _header(draw, {**item, "simulated": story.get("simulated") or item.get("simulated")}, accent)
    width = W - 2 * MARGIN
    fitted = fit_text(draw, story["chart_title"], width, 2, [40, 36, 32, 28], bold=True)
    if fitted:
        font, lines = fitted
        for ln in lines:
            draw.text((MARGIN, y), ln, font=font, fill=TEXT)
            y += font.size + 10
    names, stat = _short_labels(parts + [total] + others)
    part_names, total_names = names[:len(parts)], names[len(parts):]
    lead = fit_text(draw, f"{part_names[0]}: {parts[0]['value']} of the {total['value']} total" + (f" ({stat.lower()} times)" if stat else ""),
                    width, 2, [34, 30, 28, 26])
    y += 24
    if lead:
        for ln in lead[1]:
            draw.text((MARGIN, y), ln, font=lead[0], fill=accent)
            y += lead[0].size + 8
    y += 36
    values = [_value_number(str(r["value"])) for r in parts]
    whole = sum(values)
    bar_h, x = 120, MARGIN
    shades = [accent, (96, 110, 104), (70, 80, 76), (58, 64, 62)]
    for n, v in enumerate(values):
        seg = max(6, round(width * v / whole)) if n < len(values) - 1 else MARGIN + width - x
        draw.rectangle([x, y, x + seg, y + bar_h], fill=shades[min(n, len(shades) - 1)])
        if n:
            draw.line([(x, y), (x, y + bar_h)], fill=BG, width=3)
        x += seg
    y += bar_h + 48
    row = min(130, (H - 330 - y) // max(1, len(parts)))
    vf, lf = _font(52, True), _font(30)
    for n, r in enumerate(parts):
        draw.rectangle([MARGIN, y + 14, MARGIN + 28, y + 42], fill=shades[min(n, len(shades) - 1)])
        draw.text((MARGIN + 50, y + 8), part_names[n], font=lf, fill=TEXT if n == 0 else MUTED)
        value = str(r["value"])
        draw.text((W - MARGIN - draw.textlength(value, font=vf), y), value, font=vf, fill=accent if n == 0 else TEXT)
        y += row
    draw.line([(MARGIN, y), (W - MARGIN, y)], fill=(52, 58, 64), width=2)
    y += 22
    for r, name in zip([total] + others, total_names):
        value = str(r["value"])
        draw.text((MARGIN, y + 8), name, font=lf, fill=MUTED)
        draw.text((W - MARGIN - draw.textlength(value, font=vf), y), value, font=vf, fill=TEXT)
        y += 80
    _footer(draw)
    alt = (f"Split bar, {story['chart_title']}: " + "; ".join(f"{r['label']} {r['value']}" for r in parts) +
           "; " + "; ".join(f"{r['label']} {r['value']}" for r in [total] + others) + ".")
    return _save(img), alt + (" Simulated data." if story.get("simulated") else "")


def _measure_group(results: list[dict]) -> list[dict] | None:
    """The largest set (2+) of results that measure the same thing in the same unit, read from the label's last word: "2026-06-05
    Z-score" and "2026-05-15 Z-score" chart together as bars, while the returns beside them, a different measure, stay in the text.
    Signed changes are left out (a bar from zero cannot show a negative return)."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in results:
        value = str(r["value"]).strip()
        if _value_number(value) is None or value[:1] in "-+−":
            continue
        groups.setdefault((r["label"].split()[-1].lower(), _unit(value)), []).append(r)
    best = max(groups.values(), key=len, default=[])
    return best if 2 <= len(best) < len(results) else None


def render_story_chart(story: dict, item: dict, post_text: str) -> tuple[str, str] | None:
    """A chart of the story's results that the post mentions: bars when they share a unit, otherwise one figure per result.
    Returns None when fewer than two of them appear in the post."""
    results = story_results_in_post(story, post_text)
    if len(results) < 2:
        return None
    split = parts_of_total(results)
    if split:
        return _parts_chart(story, item, *split)
    pairs = expand_pairs(results)
    rates = [r for r in pairs if _rate(r["value"]) is not None]
    if 2 <= len(rates) <= 7:
        # Counts next to the rates stay in the post text; the chart compares the scores on one scale.
        return _rate_bars(story, item, rates, post_text)
    group = _measure_group(results)
    if group:
        results = group
    accent = _accent(item["title"])
    img, draw = _canvas()
    y = _header(draw, {**item, "simulated": story.get("simulated") or item.get("simulated")}, accent)
    width = W - 2 * MARGIN
    fitted = fit_text(draw, story["chart_title"], width, 2, [40, 36, 32, 28], bold=True)
    if fitted:
        font, lines = fitted
        for ln in lines:
            draw.text((MARGIN, y), ln, font=font, fill=TEXT)
            y += font.size + 10
        y += 30
    footer_top = H - 150
    results = results[:5]
    slot = min((footer_top - y) // len(results), 200)  # a few results sit together instead of spreading over the card
    values = [_value_number(str(r["value"])) for r in results]
    same_unit = len({_unit(str(r["value"])) for r in results}) == 1 and all(v is not None for v in values)
    top = max(values) if same_unit and max(values) > 0 else None
    for r, v in zip(results, values):
        label_fit = fit_text(draw, r["label"], width, 2, [30, 28, 26, 24])
        if not label_fit:
            return None
        lfont, llines = label_fit
        ty = y
        for ln in llines:
            draw.text((MARGIN, ty), ln, font=lfont, fill=MUTED)
            ty += lfont.size + 6
        vfont = _font(56, True)
        value = str(r["value"])
        if top:
            bar_w = width - draw.textlength(value, font=vfont) - 30
            length = max(8, int(bar_w * v / top))
            draw.rounded_rectangle([MARGIN, ty + 8, MARGIN + length, ty + 56], radius=6, fill=accent)
            draw.text((MARGIN + length + 20, ty), value, font=vfont, fill=TEXT)
        else:
            draw.text((MARGIN, ty), value, font=vfont, fill=accent)
        y += slot
    _footer(draw)
    alt = f"{story['chart_title']}: " + "; ".join(f"{r['label']} {r['value']}" for r in results) + "."
    if story.get("simulated"):
        alt += " Simulated data."
    return _save(img), alt
