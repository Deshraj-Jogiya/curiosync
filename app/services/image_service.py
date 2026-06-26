"""Programmatic graphic generation for LinkedIn posts, rendering structured flowcharts, comparisons, and system architectures."""

import os
import re
import json
import math
from PIL import Image, ImageDraw, ImageFont
from app.utils.logging import logger

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
    """Parse draft text to extract a clean title and up to 3 bullet points for the graphic (fallback)."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "Enterprise AI & Data Strategy", []

    title = ""
    for line in lines:
        if not line.startswith(("*", "-", "•", "#")):
            title = line
            break
    if not title:
        title = "Enterprise AI & Data Strategy"
    else:
        title = re.sub(r'^[":\-\s]+|[":\-\s]+$', '', title)
        if len(title) > 60:
            title = title[:57] + "..."

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

def _draw_arrow(draw, x1, y1, x2, y2, color, width=3, arrow_size=12):
    """Draw a line with a solid arrow head pointing from (x1, y1) to (x2, y2)."""
    draw.line([(x1, y1), (x2, y2)], fill=color, width=width)
    angle = math.atan2(y2 - y1, x2 - x1)
    x_b1 = x2 - arrow_size * math.cos(angle - math.pi / 6)
    y_b1 = y2 - arrow_size * math.sin(angle - math.pi / 6)
    x_b2 = x2 - arrow_size * math.cos(angle + math.pi / 6)
    y_b2 = y2 - arrow_size * math.sin(angle + math.pi / 6)
    draw.polygon([(x2, y2), (x_b1, y_b1), (x_b2, y_b2)], fill=color)

async def generate_graphic_metadata(draft_text: str, settings) -> dict:
    """Analyze LinkedIn post content and generate structured visualization metadata."""
    from app.services.llm_service import call_llm_with_fallback
    
    prompt = f"""\
You are a senior technical illustrator and visual system designer.
Based on the following LinkedIn post, generate a structured JSON object defining a premium visual infographic/diagram that illustrates the core technical concept discussed in the post.

Choose the most appropriate diagram type from:
- "flowchart": Best for sequential data pipelines, processing steps, or algorithms.
- "comparison": Best for comparing different frameworks, algorithms, or approaches.
- "architecture": Best for system setups showing components (clients, servers, databases, queues) and connections.

You must return ONLY a raw JSON object matching the schema below, with no markdown wrappers or backticks.

=== FLOWCHART SCHEMA ===
{{
  "type": "flowchart",
  "title": "Graphic Title",
  "steps": [
    {{"num": "1", "title": "Step 1 Title", "desc": "Brief step 1 description"}},
    {{"num": "2", "title": "Step 2 Title", "desc": "Brief step 2 description"}},
    {{"num": "3", "title": "Step 3 Title", "desc": "Brief step 3 description"}}
  ]
}}

=== COMPARISON SCHEMA ===
{{
  "type": "comparison",
  "title": "Graphic Title",
  "headers": ["Attribute", "Option A", "Option B"],
  "rows": [
    ["Criteria 1", "Val 1A", "Val 1B"],
    ["Criteria 2", "Val 2A", "Val 2B"],
    ["Criteria 3", "Val 3A", "Val 3B"]
  ]
}}

=== ARCHITECTURE SCHEMA ===
{{
  "type": "architecture",
  "title": "Graphic Title",
  "nodes": [
    {{"id": "n1", "label": "Node 1 Label"}},
    {{"id": "n2", "label": "Node 2 Label"}},
    {{"id": "n3", "label": "Node 3 Label"}},
    {{"id": "n4", "label": "Node 4 Label"}}
  ],
  "connections": [
    ["n1", "n2"],
    ["n2", "n3"],
    ["n3", "n4"]
  ]
}}

LinkedIn Post content:
{draft_text}"""

    try:
        messages = [
            {"role": "system", "content": "You are a professional technical visual architect. Return ONLY valid JSON."},
            {"role": "user", "content": prompt}
        ]
        raw_json = await call_llm_with_fallback(messages, settings, temperature=0.1)
        
        # Clean any markdown wrappers if returned
        if "```" in raw_json:
            raw_json = raw_json.replace("```json", "").replace("```", "").strip()
            
        data = json.loads(raw_json)
        logger.info("Successfully generated graphic metadata: type=%s", data.get("type"))
        return data
    except Exception as e:
        logger.error("Failed to generate graphic metadata, using fallback. Error: %s", e)
        # Safe fallback
        return {
            "type": "flowchart",
            "title": "Data Pipeline Workflow",
            "steps": [
                {"num": "1", "title": "Data Ingestion", "desc": "Process incoming stream segments"},
                {"num": "2", "title": "Model Validation", "desc": "Run Great Expectations checks"},
                {"num": "3", "title": "Insight Dashboard", "desc": "Deliver real-time operational KPIs"}
            ]
        }

def generate_linkedin_image(metadata, bullets=None, subtitle="Enterprise AI & Data Strategy") -> str:
    """Generate a premium technical graphic representing systems/pipelines/comparisons.
    
    Supports both the old signature (string title + bullets list) and the new metadata dict.
    Returns the absolute path to the generated image file.
    """
    import random
    import hashlib

    # 1. Backwards Compatibility check
    if isinstance(metadata, str):
        title_str = metadata
        bullets_list = bullets or []
        # Construct fallback flowchart metadata dict
        metadata = {
            "type": "flowchart",
            "title": title_str,
            "steps": [
                {
                    "num": str(i),
                    "title": b.split(":")[0] if ":" in b else f"Phase {i}",
                    "desc": b.split(":")[1].strip() if ":" in b else b
                }
                for i, b in enumerate(bullets_list[:3], 1)
            ]
        }

    # Extract details
    diag_type = metadata.get("type", "flowchart").lower()
    title = metadata.get("title", "Technical Architecture Overview")

    # Use title as seed for color selection
    hasher = hashlib.md5(title.encode('utf-8', errors='ignore'))
    seed_int = int(hasher.hexdigest(), 16)
    rng = random.Random(seed_int)

    # Curated premium color themes: (bg_start, bg_end, accent_color, shape_colors)
    themes = [
        ((15, 23, 42), (30, 27, 75), (99, 102, 241), [(6, 182, 212), (168, 85, 247), (16, 185, 129)]), # indigo-midnight
        ((9, 28, 20), (6, 78, 59), (16, 185, 129), [(52, 211, 153), (20, 184, 166), (14, 165, 233)]),   # emerald-forest
        ((17, 24, 39), (88, 28, 135), (236, 72, 153), [(168, 85, 247), (249, 115, 22), (6, 182, 212)]), # cyberpunk-pink
        ((8, 51, 68), (23, 37, 84), (6, 182, 212), [(59, 130, 246), (139, 92, 246), (110, 231, 183)]),  # oceanic-teal
    ]
    theme = rng.choice(themes)
    bg_start, bg_end, accent_color, colors = theme

    width, height = 1200, 628
    image = Image.new("RGBA", (width, height), color=(15, 23, 42, 255))
    draw = ImageDraw.Draw(image, "RGBA")

    # Draw gradient background
    _draw_gradient(draw, width, height, bg_start, bg_end)

    # Load fonts
    font_bold_path = _find_font("arial.ttf", bold=True)
    font_reg_path = _find_font("arial.ttf", bold=False)

    if font_bold_path:
        title_font = ImageFont.truetype(font_bold_path, 34)
        subtitle_font = ImageFont.truetype(font_bold_path, 18)
        footer_font = ImageFont.truetype(font_bold_path, 15)
        num_font = ImageFont.truetype(font_bold_path, 22)
    else:
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
        footer_font = ImageFont.load_default()
        num_font = ImageFont.load_default()

    if font_reg_path:
        body_font = ImageFont.truetype(font_reg_path, 16)
        desc_font = ImageFont.truetype(font_reg_path, 15)
    else:
        body_font = ImageFont.load_default()
        desc_font = ImageFont.load_default()

    # Draw Main Glassmorphism Container Card
    draw.rounded_rectangle(
        [(60, 40), (1140, 588)],
        radius=16,
        fill=(15, 23, 42, 200),
        outline=(255, 255, 255, 25),
        width=1
    )

    # Render Header Title
    title_lines = wrap_text(title, title_font, 750, draw)
    y_cursor = 70
    for line in title_lines[:2]:
        draw.text((100, y_cursor), line, font=title_font, fill=(255, 255, 255, 255))
        y_cursor += 42

    # Render Header Badge (Right Side)
    badge_label = diag_type.upper()
    bbox = draw.textbbox((0, 0), badge_label, font=subtitle_font)
    badge_w = bbox[2] - bbox[0]
    badge_h = bbox[3] - bbox[1]
    draw.rounded_rectangle(
        [(1100 - badge_w - 30, 70), (1100, 70 + badge_h + 16)],
        radius=8,
        fill=(accent_color[0], accent_color[1], accent_color[2], 120),
        outline=accent_color,
        width=1
    )
    draw.text((1100 - badge_w - 15, 76), badge_label, font=subtitle_font, fill=(255, 255, 255, 255))

    # Render Diagram Content
    content_y = max(y_cursor + 30, 160)
    
    if diag_type == "flowchart":
        steps = metadata.get("steps", [])
        steps_count = len(steps)
        if steps_count > 0:
            total_w = 1000
            # Dynamically size box_w based on steps_count to prevent overlap
            box_w = min(280, int((total_w - 30 * (steps_count - 1)) / steps_count)) if steps_count > 1 else 280
            box_w = max(140, box_w)
            box_h = 240
            spacing = (total_w - (steps_count * box_w)) / (steps_count - 1) if steps_count > 1 else 0
            
            for i, step in enumerate(steps):
                x = 100 + i * (box_w + spacing)
                y = content_y + 20
                
                # Step container box
                draw.rounded_rectangle(
                    [(x, y), (x + box_w, y + box_h)],
                    radius=12,
                    fill=(30, 41, 59, 120),
                    outline=(255, 255, 255, 15),
                    width=1
                )
                
                # Step number bubble
                num_text = step.get("num", str(i + 1))
                num_bbox = draw.textbbox((0, 0), num_text, font=num_font)
                num_w = num_bbox[2] - num_bbox[0]
                num_h = num_bbox[3] - num_bbox[1]
                num_radius = 20
                circle_cx = x + 35
                circle_cy = y + 35
                draw.ellipse(
                    [(circle_cx - num_radius, circle_cy - num_radius), (circle_cx + num_radius, circle_cy + num_radius)],
                    fill=accent_color
                )
                draw.text(
                    (circle_cx - num_w / 2, circle_cy - num_h / 2 - 2),
                    num_text,
                    font=num_font,
                    fill=(255, 255, 255, 255)
                )
                
                # Step title
                step_title = step.get("title", "")
                title_lines = wrap_text(step_title, subtitle_font, box_w - 40, draw)
                ty = y + 75
                for line in title_lines[:2]:
                    draw.text((x + 20, ty), line, font=subtitle_font, fill=(255, 255, 255, 255))
                    ty += 24
                
                # Step desc
                step_desc = step.get("desc", "")
                desc_lines = wrap_text(step_desc, desc_font, box_w - 40, draw)
                dy = ty + 10
                for line in desc_lines[:4]:
                    draw.text((x + 20, dy), line, font=desc_font, fill=(148, 163, 184, 255))
                    dy += 20
                
                # Flow Arrow to next box
                if i < steps_count - 1:
                    ax1 = x + box_w + 5
                    ay = y + box_h / 2
                    ax2 = x + box_w + spacing - 5
                    _draw_arrow(draw, ax1, ay, ax2, ay, (71, 85, 105, 180), width=3)

    elif diag_type == "comparison":
        headers = metadata.get("headers", ["Feature", "Options A", "Options B"])
        rows = metadata.get("rows", [])
        
        col_count = len(headers)
        row_count = len(rows)
        
        table_w = 980
        col_w = table_w / col_count
        row_h = 55
        
        tx = 110
        ty = content_y + 10
        
        # Draw header row
        draw.rounded_rectangle(
            [(tx, ty), (tx + table_w, ty + row_h)],
            radius=6,
            fill=(accent_color[0], accent_color[1], accent_color[2], 120),
            outline=accent_color,
            width=1
        )
        
        # Header text
        for col_idx, header in enumerate(headers):
            cx = tx + col_idx * col_w
            h_bbox = draw.textbbox((0, 0), header, font=subtitle_font)
            hw = h_bbox[2] - h_bbox[0]
            hh = h_bbox[3] - h_bbox[1]
            draw.text(
                (cx + (col_w - hw) / 2, ty + (row_h - hh) / 2 - 2),
                header,
                font=subtitle_font,
                fill=(255, 255, 255, 255)
            )
            
        # Draw table rows
        for r_idx, row in enumerate(rows[:4]):
            row_y = ty + row_h + r_idx * row_h
            bg_opacity = 50 if r_idx % 2 == 0 else 20
            
            draw.rounded_rectangle(
                [(tx, row_y + 2), (tx + table_w, row_y + row_h - 2)],
                radius=4,
                fill=(30, 41, 59, bg_opacity),
                outline=(255, 255, 255, 10),
                width=1
            )
            
            for c_idx, val in enumerate(row[:col_count]):
                cx = tx + c_idx * col_w
                # Make first column bold for criteria
                current_font = body_font if c_idx == 0 else desc_font
                val_color = (255, 255, 255, 255) if c_idx == 0 else (226, 232, 240, 255)
                
                # Check for checkmarks or cross symbols
                if str(val).lower() in ["yes", "true", "enabled", "checked", "pass"]:
                    val_str = "✔ Yes"
                    val_color = (52, 211, 153, 255) # Mint green
                elif str(val).lower() in ["no", "false", "disabled", "cross", "fail"]:
                    val_str = "✘ No"
                    val_color = (239, 68, 68, 255) # Red
                else:
                    val_str = str(val)
                
                v_lines = wrap_text(val_str, current_font, col_w - 20, draw)
                v_h = len(v_lines) * 18
                vy = row_y + (row_h - v_h) / 2
                for line in v_lines[:2]:
                    v_bbox = draw.textbbox((0, 0), line, font=current_font)
                    vw = v_bbox[2] - v_bbox[0]
                    draw.text(
                        (cx + (col_w - vw) / 2, vy),
                        line,
                        font=current_font,
                        fill=val_color
                    )
                    vy += 18

    elif diag_type == "architecture":
        nodes = metadata.get("nodes", [])
        node_count = len(nodes)
        
        if node_count > 0:
            total_w = 980
            content_h = 510 - content_y  # leaves some margin at bottom
            
            # Dynamically determine columns and rows
            if node_count <= 4:
                cols = node_count
                rows = 1
            elif node_count <= 8:
                cols = math.ceil(node_count / 2)
                rows = 2
            else:
                cols = math.ceil(node_count / 3)
                rows = 3
                
            # Dynamically size the boxes to prevent overlap
            box_w = min(200, int((total_w - 40 * (cols - 1)) / cols)) if cols > 1 else 200
            box_w = max(120, box_w)
            box_h = min(100, int((content_h - 30 * (rows - 1)) / rows)) if rows > 1 else 100
            box_h = max(60, box_h)
            
            node_positions = {}
            
            for i, node in enumerate(nodes):
                row = i // cols
                col = i % cols
                
                # Number of nodes in this specific row
                nodes_in_row = min(node_count - row * cols, cols)
                
                # Calculate horizontal spacing and start position for this row to center it
                row_total_w = nodes_in_row * box_w
                row_spacing = (total_w - row_total_w) / (nodes_in_row + 1)
                
                x = 110 + row_spacing + col * (box_w + row_spacing)
                y = content_y + 20 + row * (box_h + 30)
                
                nid = node.get("id", f"node{i}")
                node_positions[nid] = (x, y, x + box_w, y + box_h)
                
                # Draw node box
                border_color = colors[i % len(colors)]
                draw.rounded_rectangle(
                    [(x, y), (x + box_w, y + box_h)],
                    radius=10,
                    fill=(30, 41, 59, 150),
                    outline=border_color,
                    width=2
                )
                
                # Draw node label
                label = node.get("label", nid)
                # Use smaller font if box is small
                l_font = subtitle_font if box_w >= 160 else body_font
                l_lines = wrap_text(label, l_font, box_w - 15, draw)
                lh = len(l_lines) * 20
                ly = y + (box_h - lh) / 2
                for line in l_lines[:2]:
                    l_bbox = draw.textbbox((0, 0), line, font=l_font)
                    lw = l_bbox[2] - l_bbox[0]
                    draw.text(
                        (x + (box_w - lw) / 2, ly),
                        line,
                        font=l_font,
                        fill=(255, 255, 255, 255)
                    )
                    ly += 20

            # Draw Connections
            connections = metadata.get("connections", [])
            for conn in connections:
                if len(conn) >= 2:
                    n_from, n_to = conn[0], conn[1]
                    if n_from in node_positions and n_to in node_positions:
                        p1 = node_positions[n_from]
                        p2 = node_positions[n_to]
                        
                        # Compute center edge connection points
                        # If p1 is to the left of p2
                        if p1[2] < p2[0]:
                            x1, y1 = p1[2], p1[1] + (p1[3] - p1[1]) / 2
                            x2, y2 = p2[0], p2[1] + (p2[3] - p2[1]) / 2
                        # If p1 is above p2
                        elif p1[3] < p2[1]:
                            x1, y1 = p1[0] + (p1[2] - p1[0]) / 2, p1[3]
                            x2, y2 = p2[0] + (p2[2] - p2[0]) / 2, p2[1]
                        else:
                            # Default center-to-center line with margins
                            x1 = p1[0] + (p1[2] - p1[0]) / 2
                            y1 = p1[1] + (p1[3] - p1[1]) / 2
                            x2 = p2[0] + (p2[2] - p2[0]) / 2
                            y2 = p2[1] + (p2[3] - p2[1]) / 2
                            
                        # Draw line with arrow
                        _draw_arrow(draw, x1, y1, x2, y2, (148, 163, 184, 180), width=3)

    # Render Footer Branding
    footer_text = "AUTOMATED PIPELINE  |  DESHRAJ RAMESHKUMAR JOGIYA  |  PORTFOLIO: deshraj-jogiya.github.io"
    draw.line([(100, 525), (1100, 525)], fill=(71, 85, 105, 120), width=1)
    draw.text((100, 542), footer_text, font=footer_font, fill=(148, 163, 184, 255))

    os.makedirs("./data/graphics", exist_ok=True)
    filepath = os.path.abspath(f"./data/graphics/post_image_{os.getpid()}.png")
    
    # Convert RGBA to RGB for saving
    final_image = image.convert("RGB")
    final_image.save(filepath)
    logger.info("Premium technical infographic generated and saved to: %s", filepath)
    return filepath
