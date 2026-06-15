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
    import random
    import hashlib
    import math

    # Use title as a seed to ensure a consistent, unique design for this specific post title
    hasher = hashlib.md5(title.encode('utf-8', errors='ignore'))
    seed_int = int(hasher.hexdigest(), 16)
    rng = random.Random(seed_int)

    # Curated premium color themes: (theme_name, bg_start, bg_end, accent_color, shape_colors)
    themes = [
        ("indigo-midnight", (15, 23, 42), (30, 27, 75), (99, 102, 241), [
            (6, 182, 212),   # Cyan
            (168, 85, 247),  # Purple
            (16, 185, 129),  # Emerald
            (245, 158, 11),  # Amber
            (239, 68, 68),   # Red
        ]),
        ("emerald-forest", (9, 28, 20), (6, 78, 59), (16, 185, 129), [
            (52, 211, 153),  # Mint
            (20, 184, 166),  # Teal
            (245, 158, 11),  # Amber
            (14, 165, 233),  # Sky
            (168, 85, 247),  # Purple
        ]),
        ("cyberpunk-magenta", (17, 24, 39), (88, 28, 135), (236, 72, 153), [
            (168, 85, 247),  # Purple
            (249, 115, 22),  # Orange
            (6, 182, 212),   # Cyan
            (236, 72, 153),  # Pink
            (234, 179, 8),   # Yellow
        ]),
        ("oceanic-teal", (8, 51, 68), (23, 37, 84), (6, 182, 212), [
            (59, 130, 246),  # Blue
            (139, 92, 246),  # Violet
            (110, 231, 183), # Mint
            (6, 182, 212),   # Cyan
            (245, 158, 11),  # Amber
        ]),
        ("sunset-crimson", (24, 24, 27), (127, 29, 29), (239, 68, 68), [
            (244, 63, 94),   # Rose
            (245, 158, 11),  # Amber
            (234, 179, 8),   # Yellow
            (139, 92, 246),  # Violet
            (14, 165, 233),  # Sky
        ]),
        ("carbon-gold", (18, 18, 18), (38, 38, 38), (234, 179, 8), [
            (217, 119, 6),   # Amber
            (253, 224, 71),  # Yellow
            (245, 245, 245), # White
            (148, 163, 184), # Gray
            (168, 85, 247),  # Purple
        ]),
    ]

    theme = rng.choice(themes)
    theme_name, bg_start, bg_end, accent_color, shape_colors = theme

    width, height = 1200, 628
    # Enable RGBA for semi-transparent drawing capabilities
    image = Image.new("RGBA", (width, height), color=(15, 23, 42, 255))
    draw = ImageDraw.Draw(image, "RGBA")

    # Draw theme-specific premium gradient background
    _draw_gradient(draw, width, height, bg_start, bg_end)

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

    # Choose a randomized graphic layout style for the left side (x: 0 to 440)
    graphic_style = rng.choice(["network", "waves", "isometric", "matrix"])

    if graphic_style == "network":
        # Dynamic node count and positions
        node_count = rng.randint(4, 5)
        nodes = []
        for _ in range(node_count):
            x = rng.randint(120, 340)
            y = rng.randint(150, 470)
            color = rng.choice(shape_colors)
            nodes.append((x, y, color))
        
        # Connections
        for i in range(node_count):
            for j in range(i + 1, node_count):
                if rng.random() > 0.4:
                    p1 = nodes[i]
                    p2 = nodes[j]
                    draw.line([(p1[0], p1[1]), (p2[0], p2[1])], fill=(71, 85, 105, 180), width=2)
                    
        for x, y, color in nodes:
            draw.ellipse([(x - 20, y - 20), (x + 20, y + 20)], fill=(color[0], color[1], color[2], 100))
            draw.ellipse([(x - 12, y - 12), (x + 12, y + 12)], fill=color, outline=(255, 255, 255, 255), width=2)

    elif graphic_style == "waves":
        center_x, center_y = 230, 314
        # Concentric dotted circles
        for radius in [80, 140, 200, 260]:
            for angle in range(0, 360, 15):
                rad = math.radians(angle)
                x = int(center_x + radius * math.cos(rad))
                y = int(center_y + radius * math.sin(rad))
                draw.ellipse([(x - 2, y - 2), (x + 2, y + 2)], fill=(148, 163, 184, 100))
                
        # Colored radar/vector sweeps
        for _ in range(3):
            radius = rng.randint(80, 240)
            start_angle = rng.randint(0, 270)
            end_angle = start_angle + rng.randint(60, 150)
            color = rng.choice(shape_colors)
            draw.arc(
                [(center_x - radius, center_y - radius), (center_x + radius, center_y + radius)],
                start=start_angle,
                end=end_angle,
                fill=color,
                width=3
            )
            
        # Target/accent dots
        for _ in range(4):
            radius = rng.choice([80, 140, 200, 260])
            angle = rng.randint(0, 360)
            rad = math.radians(angle)
            x = int(center_x + radius * math.cos(rad))
            y = int(center_y + radius * math.sin(rad))
            color = rng.choice(shape_colors)
            draw.ellipse([(x - 8, y - 8), (x + 8, y + 8)], fill=color, outline=(255, 255, 255, 255), width=1)

    elif graphic_style == "isometric":
        # Slanted parallel platforms
        layer_y_centers = [200, 314, 428]
        for idx, cy in enumerate(layer_y_centers):
            color = shape_colors[idx % len(shape_colors)]
            pts = [
                (230, cy - 40), # Top
                (350, cy),     # Right
                (230, cy + 40), # Bottom
                (110, cy)      # Left
            ]
            draw.polygon(pts, fill=(color[0], color[1], color[2], 80), outline=color, width=2)
            draw.ellipse([(230 - 6, cy - 6), (230 + 6, cy + 6)], fill=(255, 255, 255, 255))

        # Central linking line
        for y in range(140, 480, 10):
            if y % 20 == 0:
                draw.line([(230, y), (230, y + 10)], fill=(148, 163, 184, 150), width=2)

    elif graphic_style == "matrix":
        start_x, start_y = 110, 134
        cols, rows = 7, 9
        spacing = 40
        for r in range(rows):
            for c in range(cols):
                x = start_x + c * spacing
                y = start_y + r * spacing
                opacity = rng.choice([40, 80, 120])
                draw.ellipse([(x - 3, y - 3), (x + 3, y + 3)], fill=(148, 163, 184, opacity))
                
        # Connecting paths
        highlights = []
        for _ in range(rng.randint(3, 4)):
            r = rng.randint(0, rows - 1)
            c = rng.randint(0, cols - 1)
            highlights.append((start_x + c * spacing, start_y + r * spacing))
            
        for i in range(len(highlights) - 1):
            p1 = highlights[i]
            p2 = highlights[i + 1]
            color = rng.choice(shape_colors)
            draw.line([p1, p2], fill=color, width=2)
            
        for x, y in highlights:
            color = rng.choice(shape_colors)
            draw.ellipse([(x - 8, y - 8), (x + 8, y + 8)], fill=color, outline=(255, 255, 255, 255), width=2)

    # Decorative frame boundaries on the left panel
    draw.line([(80, 100), (420, 100)], fill=accent_color, width=1)
    draw.line([(80, 528), (420, 528)], fill=accent_color, width=1)

    # Draw text content on the right (x start: 480)
    badge_text = subtitle.upper()
    bbox = draw.textbbox((0, 0), badge_text, font=subtitle_font)
    badge_w = bbox[2] - bbox[0]
    badge_h = bbox[3] - bbox[1]

    draw.rounded_rectangle(
        [(480, 80), (480 + badge_w + 30, 80 + badge_h + 16)],
        radius=8,
        fill=accent_color,
    )
    draw.text((495, 86), badge_text, font=subtitle_font, fill=(255, 255, 255, 255))

    title_lines = wrap_text(title, title_font, 650, draw)
    y_cursor = 160
    for line in title_lines[:2]:
        draw.text((480, y_cursor), line, font=title_font, fill=(255, 255, 255, 255))
        y_cursor += 50

    y_cursor += 20
    for bullet in bullets[:3]:
        bullet_lines = wrap_text(f"- {bullet}", body_font, 650, draw)
        for line in bullet_lines:
            draw.text((480, y_cursor), line, font=body_font, fill=(226, 232, 240, 255))
            y_cursor += 30
        y_cursor += 10

    footer_text = "DESHRAJ RAMESHKUMAR JOGIYA  |  DATA & AI INTELLIGENCE"
    draw.line([(480, 545), (1120, 545)], fill=(71, 85, 105, 255), width=1)
    draw.text((480, 560), footer_text, font=footer_font, fill=(148, 163, 184, 255))

    os.makedirs("./data/graphics", exist_ok=True)
    filepath = os.path.abspath(f"./data/graphics/post_image_{os.getpid()}.png")
    
    # Convert RGBA to RGB for saving as PNG/JPEG without alpha channel issues
    final_image = image.convert("RGB")
    final_image.save(filepath)
    return filepath
