"""Programmatic graphic generation for LinkedIn posts."""

import os
import re
from PIL import Image, ImageDraw, ImageFont


def _draw_gradient(draw, width, height, start_color, end_color):
    """Draw a horizontal gradient background."""
    for x in range(width):
        r = int(start_color[0] + (end_color[0] - start_color[0]) * (x / width))
        g = int(start_color[1] + (end_color[1] - start_color[1]) * (x / width))
        b = int(start_color[2] + (end_color[2] - start_color[2]) * (x / width))
        draw.line([(x, 0), (x, height)], fill=(r, g, b))


def _find_font(font_name="arial.ttf", bold=False):
    """Find a system font path, or return None to use default."""
    filename = "arialbd.ttf" if (bold and font_name == "arial.ttf") else font_name
    paths = [
        os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", filename),
        os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", filename.lower()),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for path in paths:
        if os.path.exists(path):
            return path
    return None


def wrap_text(text, font, max_width, draw):
    """Wrap text to fit a maximum width in pixels."""
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        current_line.append(word)
        line_str = " ".join(current_line)
        bbox = draw.textbbox((0, 0), line_str, font=font)
        w = bbox[2] - bbox[0]
        if w > max_width:
            current_line.pop()
            lines.append(" ".join(current_line))
            current_line = [word]

    if current_line:
        lines.append(" ".join(current_line))
    return lines


def parse_draft_for_image(text: str) -> tuple[str, list[str]]:
    """Parse draft text to extract a clean title and up to 3 bullet points for the graphic."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "Enterprise AI & Data Strategy", []

    # Find the first line that doesn't start with a bullet point or hashtag
    title = ""
    for line in lines:
        if not line.startswith(("*", "-", "•", "#")):
            title = line
            break
    if not title:
        title = "Enterprise AI & Data Strategy"
    else:
        # Clean title
        title = re.sub(r'^[":\-\s]+|[":\-\s]+$', '', title)
        if len(title) > 60:
            title = title[:57] + "..."

    # Extract bullets
    bullets = []
    for line in lines:
        if line.startswith(("*", "-", "•")):
            bullet_clean = re.sub(r'^[*\-•\s]+', '', line).strip()
            if len(bullet_clean) > 85:
                bullet_clean = bullet_clean[:82] + "..."
            bullets.append(bullet_clean)
            if len(bullets) >= 3:
                break

    return title, bullets


def generate_linkedin_image(title: str, bullets: list[str], subtitle: str = "Enterprise AI & Data Strategy") -> str:
    """Generate a premium technical graphic and save it locally.

    Returns the absolute path to the generated image file.
    """
    width, height = 1200, 628
    image = Image.new("RGB", (width, height), color=(15, 23, 42))
    draw = ImageDraw.Draw(image)

    # Draw dark premium slate-indigo gradient background
    _draw_gradient(draw, width, height, (15, 23, 42), (30, 27, 75))

    # Load fonts
    font_bold_path = _find_font("arial.ttf", bold=True)
    font_reg_path = _find_font("arial.ttf", bold=False)

    if font_bold_path:
        title_font = ImageFont.truetype(font_bold_path, 38)
        subtitle_font = ImageFont.truetype(font_bold_path, 22)
        footer_font = ImageFont.truetype(font_bold_path, 16)
    else:
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
        footer_font = ImageFont.load_default()

    if font_reg_path:
        body_font = ImageFont.truetype(font_reg_path, 20)
    else:
        body_font = ImageFont.load_default()

    # Draw abstract architectural network graph on the left-third
    nodes = [
        (150, 180, (6, 182, 212)),  # Cyan
        (280, 240, (168, 85, 247)), # Purple
        (180, 380, (16, 185, 129)), # Emerald
        (320, 360, (245, 158, 11)), # Amber
        (120, 280, (239, 68, 68)),   # Red
    ]
    connections = [(0, 1), (0, 4), (1, 3), (2, 4), (2, 3), (1, 2)]
    for start_idx, end_idx in connections:
        p1 = nodes[start_idx]
        p2 = nodes[end_idx]
        draw.line([(p1[0], p1[1]), (p2[0], p2[1])], fill=(71, 85, 105), width=2)

    for x, y, color in nodes:
        # Drawing nodes
        draw.ellipse([(x - 20, y - 20), (x + 20, y + 20)], fill=(color[0], color[1], color[2], 100))
        draw.ellipse([(x - 12, y - 12), (x + 12, y + 12)], fill=color, outline=(255, 255, 255), width=2)

    # Decorative overlay lines
    draw.line([(80, 100), (420, 100)], fill=(99, 102, 241), width=1)
    draw.line([(80, 528), (420, 528)], fill=(99, 102, 241), width=1)

    # Draw text content on the right (x start: 480)
    badge_text = subtitle.upper()
    bbox = draw.textbbox((0, 0), badge_text, font=subtitle_font)
    badge_w = bbox[2] - bbox[0]
    badge_h = bbox[3] - bbox[1]

    draw.rounded_rectangle(
        [(480, 80), (480 + badge_w + 30, 80 + badge_h + 16)],
        radius=8,
        fill=(99, 102, 241),
    )
    draw.text((495, 86), badge_text, font=subtitle_font, fill=(255, 255, 255))

    title_lines = wrap_text(title, title_font, 650, draw)
    y_cursor = 160
    for line in title_lines[:2]:
        draw.text((480, y_cursor), line, font=title_font, fill=(255, 255, 255))
        y_cursor += 50

    y_cursor += 20
    for bullet in bullets[:3]:
        bullet_lines = wrap_text(f"- {bullet}", body_font, 650, draw)
        for line in bullet_lines:
            draw.text((480, y_cursor), line, font=body_font, fill=(226, 232, 240))
            y_cursor += 30
        y_cursor += 10

    footer_text = "DESHRAJ RAMESHKUMAR JOGIYA  |  DATA & AI INTELLIGENCE"
    draw.line([(480, 545), (1120, 545)], fill=(71, 85, 105), width=1)
    draw.text((480, 560), footer_text, font=footer_font, fill=(148, 163, 184))

    os.makedirs("./data/graphics", exist_ok=True)
    filepath = os.path.abspath(f"./data/graphics/post_image_{os.getpid()}.png")
    image.save(filepath)
    return filepath
