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

BG = (13, 20, 36)
PANEL = (22, 32, 54)
TEXT = (241, 245, 249)
MUTED = (148, 163, 184)
ACCENTS = [(56, 189, 248), (52, 211, 153), (251, 191, 36), (167, 139, 250)]
FOOTER = "Deshraj Jogiya  |  Data Engineer & Machine Learning Engineer"


def _font_path(bold: bool) -> str | None:
    names = ["arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold else ["arial.ttf", "DejaVuSans.ttf"]
    dirs = [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"), "/usr/share/fonts/truetype/dejavu",
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
    draw.line([(MARGIN, H - 120), (W - MARGIN, H - 120)], fill=(51, 65, 85), width=2)
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


def _numeric_facts(item: dict) -> list[tuple[str, str]]:
    out = []
    for fact in item["facts"]:
        m = re.search(r"\d[\d,]*(?:\.\d+)?\s*%|\d[\d,]*\+|\d[\d,]*(?:\.\d+)?x\b|\b\d{2,}[\d,]*\b", fact)
        if m:
            text = re.sub(r"^[A-Z][\w &/-]{2,40}:\s*", "", fact)
            out.append((m.group(0).replace(" ", ""), text))
    return out


def render_stat_card(item: dict) -> tuple[str, str]:
    """Up to three real numbers from the facts, each with its own fact sentence. No model involved."""
    accent = _accent(item["title"])
    img, draw = _canvas()
    y = _header(draw, item, accent)
    facts = sorted(_numeric_facts(item), key=lambda f: len(f[1]))[:3]
    if not facts:
        facts = [("", f) for f in sorted(item["facts"], key=len)[:3]]
    footer_top = H - 150
    slot = min(330, (footer_top - y) // max(1, len(facts)))
    y += max(0, (footer_top - y - slot * len(facts)) // 2)
    alt_parts = []
    for number, text in facts:
        nfont = _font(96, True)
        if number:
            draw.text((MARGIN, y), number, font=nfont, fill=accent)
            ty = y + 120
        else:
            ty = y
        fitted = fit_text(draw, text, W - 2 * MARGIN, max(2, (slot - (ty - y) - 20) // 38), [32, 30, 28, 26, 24])
        if fitted:
            font, lines = fitted
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
