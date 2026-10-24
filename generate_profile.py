#!/usr/bin/env python3
"""Generate light and dark static GitHub profile SVGs from a Figma-exported SVG.

The source design is preserved: window chrome, cactus illustration, pot, logo wordmark,
shadows, gradients, and overall geometry stay intact. The left-hand content panel is
replaced with editable SVG text, dotted leaders, and theme-specific colors, and the
cactus block is scaled so it finishes level with the text column instead of hanging
below it. The card itself is sized to the content and the illustration.

Typography is JetBrains Mono for the data and Space Grotesk for the section headings,
embedded as base64 WOFF subsets from ./fonts so it renders the same on every machine.
The Uptime row is computed from UPTIME_EPOCH, so a scheduled run (see
.github/workflows/refresh-profile.yml) keeps it current. The dark theme uses the
classic Monokai palette, the light theme uses Monokai Pro Light (Sun) so the two read
as a pair. A static neon bloom on the frame and values can be switched off with
--no-glow, and the scan band animation with --no-sweep.

Usage:
    python3 generate_profile.py
    python3 generate_profile.py --no-sweep
    python3 generate_profile.py --no-glow
    python3 generate_profile.py "GitHub README Light.svg" --out-dir .

No third-party Python packages are required.
"""
from __future__ import annotations

import argparse
import base64
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
XML_NS = "http://www.w3.org/XML/1998/namespace"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)

ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE = ROOT / "GitHub README Light.svg"
DEFAULT_OUTPUT = ROOT

# Font subsets (ASCII only, OFL) live beside the script. They are inlined as base64
# WOFF so the card keeps its typography in any browser and on GitHub, where external
# font requests are not allowed inside an SVG image. The families are renamed per the
# OFL reserved-name rule; see fonts/README.md for provenance.
FONT_DIR = ROOT / "fonts"
FONT_FILES = {
    ("Profile Mono", "400"): "ProfileMono-Regular.woff",
    ("Profile Mono", "600"): "ProfileMono-SemiBold.woff",
    ("Profile Display", "600"): "ProfileDisplay-SemiBold.woff",
}

# Figma's light artwork uses warm limestone, off-white chrome, botanical green,
# and terracotta. The dark version swaps only the UI surfaces and the cactus wordmark;
# the plant illustration itself is retained exactly as drawn.
PALETTES = {
    # Light is Monokai Pro Light (filter Sun): cream paper, plum text, keyword
    # pink headings, string amber values, comment-grey labels, blue title.
    "light": {
        "background": "#F8EFE7",
        "chrome": "#EEE5DE",
        "header_title": "#2473B6",
        "section": "#CE4770",
        "key": "#756864",
        "value": "#9C5B02",
        "leader": "#CBBDB0",
        "divider": "#D2C3B6",
        "wordmark": "#D4572B",
        "glow": "#E0A800",
        "value_glow": "#D98200",
        # Pale warm gold: a lighter line keeps dark text above 4.5:1, where the
        # saturated frame gold would dip just under on the contact rows.
        "grid": "#F7E3A6",
    },
    # Dark is Monokai, mapped from the Sublime Text package variables:
    # background black3, chrome yellow4, title blue, headings red2 (keywords),
    # keys a legible tint of comment yellow5, values string yellow,
    # rules/leaders comment yellow5, wordmark orange.
    "dark": {
        "background": "#282923",
        "chrome": "#3E3D32",
        "header_title": "#67D8EF",
        "section": "#F92472",
        "key": "#9A9682",
        "value": "#E7DB74",
        "leader": "#5E5A49",
        "divider": "#4E4B3C",
        "wordmark": "#FD9621",
        "glow": "#67D8EF",
        "value_glow": "#F7EC9B",
        "grid": "#67D8EF",
    },
}

# Kept in one place so the content can be edited without touching the SVG-generation logic.
# Uptime is the elapsed time since this "boot" date, rendered as years, months and
# days. It currently reads 21 Years, 2 Months, 22 Days; change this one date if you
# want to count from a different start. The daily workflow regenerates it.
UPTIME_EPOCH = date(2005, 8, 2)
# Deliberately static: a fun offline window rather than a measured value.
DAILY_DOWNTIME = "8-10 Hours"


def add_months(start: date, months: int) -> date:
    """Move a date by whole months, clamping the day to the target month's length."""
    year, month = divmod(start.month - 1 + months, 12)
    year += start.year
    month += 1
    next_month = date(year + (month == 12), month % 12 + 1, 1)
    last_day = (next_month - timedelta(days=1)).day
    return date(year, month, min(start.day, last_day))


def counted(value: int, unit: str) -> str:
    return f"{value} {unit}" + ("" if value == 1 else "s")


def elapsed_label(epoch: date, today: date | None = None) -> str:
    """Return the completed years, months and days between two dates."""
    today = today or datetime.now(timezone.utc).date()
    if today <= epoch:
        return "0 Days"
    # Count whole months first, then the leftover days. This keeps month-end dates
    # correct: 31 Jan + 1 month is 28/29 Feb, not 3 March.
    months = (today.year - epoch.year) * 12 + (today.month - epoch.month)
    if add_months(epoch, months) > today:
        months -= 1
    anchor = add_months(epoch, months)
    years, months = divmod(months, 12)
    days = (today - anchor).days
    return (f"{counted(years, 'Year')}, {counted(months, 'Month')}, "
            f"{counted(days, 'Day')}")


PERSONAL_ROWS = [
    ("Name:", "Anuj Kumar Sah"),
    ("Uptime:", elapsed_label(UPTIME_EPOCH)),
    ("Daily Downtime:", DAILY_DOWNTIME),
    ("Education:", "CSE, Undergraduate"),
    ("Languages:", "C++, Python, Go, JavaScript"),
    ("Focus:", "Developer Tools, Backend Systems"),
    ("Projects:", "Polyvia, ChefMate"),
]
CODING_ROWS = [
    ("LeetCode:", "Anuj_72"),
    ("Codeforces:", "BlackAugust"),
    ("CodeChef:", "anuj_7225"),
    ("GitHub:", "Anuj-72"),
]
CONTACT_ROWS = [
    ("Email:", "anujsah282005@gmail.com"),
    ("LinkedIn:", "in/anuj-kumar-sah72"),
]

# ---------------------------------------------------------------------------
# Card geometry
# ---------------------------------------------------------------------------
# The card is sized around two blocks: the text column on the left and the cactus
# artwork on the right. The artwork is scaled so its top and bottom sit level with
# the first heading and the last row. The canvas starts at -22,-22 to leave a
# transparent gutter for the drop shadow and the neon halo, so neither is clipped
# by the viewport edge. The Figma source keeps its original canvas.
CANVAS_X = -12.0
CANVAS_Y = -12.0
CANVAS_WIDTH = 1206.0
CANVAS_HEIGHT = 578.0
CARD_LEFT = 10.0
CARD_TOP = 8.0
CARD_RIGHT = 1172.0
CARD_BOTTOM = 542.0
CARD_RADIUS = 18.0
CHROME_HEIGHT = 50.0
CHROME_TITLE_CENTER = 610.0  # the exported title path is centred on the original card
DIVIDER_X = 653.5
DIVIDER_TOP = 77.0
DIVIDER_BOTTOM = 521.0
PANE_BOTTOM = 525.0
PANE_CLIP_WIDTH = 558.0  # a little wider than the text so value glow is not cut off

# ---------------------------------------------------------------------------
# Text column
# ---------------------------------------------------------------------------
# Text is native SVG text for crisp rendering at any scale. Coordinates follow the
# original Figma left pane, whose content runs from x=46 to x=585.
PANE_LEFT = 46.0
PANE_RIGHT = 585.0
MONO_FONT = "Profile Mono, SFMono-Regular, Menlo, Consolas, monospace"
HEADING_FONT = "Profile Display, Segoe UI, Helvetica Neue, Arial, sans-serif"
LABEL_FONT_SIZE = 13.8
VALUE_FONT_SIZE = 15.2
HEADING_FONT_SIZE = 19.5
LABEL_FONT_WEIGHT = "400"
VALUE_FONT_WEIGHT = "600"
HEADING_FONT_WEIGHT = "600"
MONO_ADVANCE = 0.6  # JetBrains Mono advance width, in ems

# Measured from the embedded Space Grotesk SemiBold at 19.5px, used to start each
# section rule just after its heading. Unknown headings fall back to a factor.
HEADING_WIDTH_FACTOR = 10.0
HEADING_WIDTHS = {
    "Personal": 81.2,
    "Coding Profiles": 143.1,
    "Contact": 77.0,
}

PERSONAL_HEADING = 120.0
PERSONAL_ROW_START = 148.0
PERSONAL_ROW_STEP = 20.5

CODING_HEADING = 314.0
CODING_ROW_START = 341.0
CODING_ROW_STEP = 21.0

CONTACT_HEADING = 444.0
CONTACT_ROW_START = 471.0
CONTACT_ROW_STEP = 21.0

# ---------------------------------------------------------------------------
# Cactus illustration
# ---------------------------------------------------------------------------
# Bounding box of the exported cactus block (plant, pot, and "CATCUS" wordmark).
ART_SOURCE_X = 710.0
ART_SOURCE_Y = 101.0
ART_SOURCE_W = 465.0
ART_SOURCE_H = 465.0
ART_SCALE = 0.84          # small enough for the artwork to end level with the text
ART_LEFT = 717.5          # 64px of breathing room from the divider
ART_TOP = 105.0           # aligns with the cap height of the first heading

# Neon bloom: one blur for the card frame, one for the values. The filters are static;
# only the scan band below them moves, so the halo is never re-blurred per frame.
BORDER_GLOW_STD = 4.0
VALUE_GLOW_STD = 1.6

# Scan band: a soft gradient that crosses the card from the top-left corner toward
# the bottom-right, pauses off-screen, then repeats. Travel is 70% of the cycle, so
# the card is still for the remaining ~2.2s. Both cards also get a faint CRT grid,
# tinted per theme.
SWEEP_ANGLE = -45.0        # band runs perpendicular to the diagonal travel direction
SWEEP_HEIGHT = 78.0
SWEEP_BAND_WIDTH = 1500.0  # covers the card diagonal (1279) with room for the falloff
SWEEP_TRAVEL = 1300.0
SWEEP_DURATION = 7.4
SWEEP_OPACITY = {"light": 0.20, "dark": 0.24}  # multiplied by the gradient's peak
SWEEP_GRID_SIZE = 22.0
# The grid is not painted all over: a soft mask reveals it only in a halo around the
# moving band, so the lines light up as the sweep passes and fade behind it. The mask
# uses the same keyframes as the visible band, so the glow stays centred on it.
SWEEP_GLOW_HEIGHT = 300.0
# The light grid uses a pale gold feather so its hairlines read as warm paper while
# keeping text contrast at or above 4.5:1; the saturated frame gold would drop just
# below that on the contact rows. Dark can use the glow cyan at a much lower alpha
# because it reads strongly against near-black.
SWEEP_GRID_OPACITY = {"light": 0.55, "dark": 0.16}


def qn(local: str) -> str:
    return f"{{{SVG_NS}}}{local}"


def fmt(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def set_svg_text(parent: ET.Element, x: float, y: float, content: str,
                 fill: str, size: float, *, weight: str = "400",
                 family: str = MONO_FONT, anchor: str = "start") -> ET.Element:
    elem = ET.SubElement(parent, qn("text"), {
        "x": fmt(x),
        "y": fmt(y),
        "fill": fill,
        "font-family": family,
        "font-size": f"{fmt(size)}px",
        "font-weight": weight,
        "text-anchor": anchor,
        f"{{{XML_NS}}}space": "preserve",
    })
    elem.text = content
    return elem


def rounded_rect_path(left: float, top: float, right: float, bottom: float,
                      radius: float) -> str:
    r = radius
    return (
        f"M {fmt(left + r)} {fmt(top)} H {fmt(right - r)} "
        f"A {fmt(r)} {fmt(r)} 0 0 1 {fmt(right)} {fmt(top + r)} "
        f"V {fmt(bottom - r)} A {fmt(r)} {fmt(r)} 0 0 1 {fmt(right - r)} {fmt(bottom)} "
        f"H {fmt(left + r)} A {fmt(r)} {fmt(r)} 0 0 1 {fmt(left)} {fmt(bottom - r)} "
        f"V {fmt(top + r)} A {fmt(r)} {fmt(r)} 0 0 1 {fmt(left + r)} {fmt(top)} Z"
    )


def add_section(parent: ET.Element, title: str, baseline: float,
                color: str, rule_color: str) -> None:
    set_svg_text(parent, PANE_LEFT, baseline, title, color, HEADING_FONT_SIZE,
                 weight=HEADING_FONT_WEIGHT, family=HEADING_FONT)
    # Start the rule just after the heading, then run it to the pane edge.
    heading_width = HEADING_WIDTHS.get(title, len(title) * HEADING_WIDTH_FACTOR)
    line_start = PANE_LEFT + heading_width + 13
    line_y = baseline - 6.0
    if line_start < PANE_RIGHT - 6:
        ET.SubElement(parent, qn("path"), {
            "d": f"M {line_start:.2f} {line_y:.2f} H {PANE_RIGHT:.2f}",
            "fill": "none",
            "stroke": rule_color,
            "stroke-width": "1.25",
            "stroke-linecap": "round",
        })


def add_row(parent: ET.Element, key: str, value: str, baseline: float,
            palette: dict[str, str], glow: bool = False) -> None:
    label_width = len(key) * MONO_ADVANCE * LABEL_FONT_SIZE
    value_width = len(value) * MONO_ADVANCE * VALUE_FONT_SIZE
    leader_start = PANE_LEFT + label_width + 8.0
    leader_end = PANE_RIGHT - value_width - 8.0

    # Dotted leaders sit between label and value, and never run underneath text.
    if leader_end > leader_start + 8:
        ET.SubElement(parent, qn("path"), {
            "d": f"M {leader_start:.2f} {baseline - 4.2:.2f} H {leader_end:.2f}",
            "fill": "none",
            "stroke": palette["leader"],
            "stroke-width": "1.25",
            "stroke-dasharray": "1 3.3",
            "stroke-linecap": "round",
        })

    set_svg_text(parent, PANE_LEFT, baseline, key, palette["key"],
                 LABEL_FONT_SIZE, weight=LABEL_FONT_WEIGHT)
    value_text = set_svg_text(parent, PANE_RIGHT, baseline, value, palette["value"],
                              VALUE_FONT_SIZE, weight=VALUE_FONT_WEIGHT, anchor="end")
    if glow:
        value_text.set("filter", "url(#neon-value-glow)")


def add_rows(parent: ET.Element, rows: list[tuple[str, str]], start: float,
             step: float, palette: dict[str, str], glow: bool = False) -> float:
    baseline = start
    for key, value in rows:
        add_row(parent, key, value, baseline, palette, glow)
        baseline += step
    return baseline


def build_information_group(palette: dict[str, str], glow: bool = False) -> ET.Element:
    group = ET.Element(qn("g"), {
        "id": "profile-information",
        # Re-use the exact clipping area from the original Figma export.
        "clip-path": "url(#clip1_2_34)",
    })

    add_section(group, "Personal", PERSONAL_HEADING,
                palette["section"], palette["divider"])
    add_rows(group, PERSONAL_ROWS, PERSONAL_ROW_START, PERSONAL_ROW_STEP,
             palette, glow)

    add_section(group, "Coding Profiles", CODING_HEADING,
                palette["section"], palette["divider"])
    add_rows(group, CODING_ROWS, CODING_ROW_START, CODING_ROW_STEP, palette, glow)

    add_section(group, "Contact", CONTACT_HEADING,
                palette["section"], palette["divider"])
    add_rows(group, CONTACT_ROWS, CONTACT_ROW_START, CONTACT_ROW_STEP,
             palette, glow)

    return group


def font_style_element() -> ET.Element | None:
    """Inline the WOFF subsets so the SVG does not depend on installed fonts."""
    rules: list[str] = []
    for (family, weight), filename in FONT_FILES.items():
        path = FONT_DIR / filename
        if not path.is_file():
            print(f"warning: missing {path}; falling back to system fonts",
                  file=sys.stderr)
            return None
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        rules.append(
            f"@font-face{{font-family:'{family}';font-style:normal;"
            f"font-weight:{weight};"
            f"src:url(data:font/woff;base64,{encoded})format('woff');}}"
        )
    style = ET.Element(qn("style"))
    style.text = "".join(rules)
    return style


def find_information_group(root: ET.Element) -> ET.Element:
    for element in root.iter(qn("g")):
        if element.get("clip-path") == "url(#clip1_2_34)":
            return element
    raise ValueError(
        "Could not find the Figma left information group (clip1_2_34). "
        "Use the original 'GitHub README Light.svg' export as the source."
    )


def find_child_by_attr(parent: ET.Element, tag: str, **attrs: str) -> ET.Element:
    for child in parent:
        if child.tag != qn(tag):
            continue
        if all(child.get(key) == value for key, value in attrs.items()):
            return child
    raise ValueError(f"Expected <{tag}> with {attrs} in the source SVG.")


def resize_card(root: ET.Element, clip0_group: ET.Element) -> None:
    """Resize the exported card, chrome, divider, and artwork to the new layout.

    Runs before any theme recoloring, because the elements are still located by
    their original Figma fills and strokes.
    """
    width, height = CANVAS_WIDTH, CANVAS_HEIGHT
    root.set("width", fmt(width))
    root.set("height", fmt(height))
    root.set("viewBox", f"{fmt(CANVAS_X)} {fmt(CANVAS_Y)} {fmt(width)} {fmt(height)}")

    card_path_d = rounded_rect_path(CARD_LEFT, CARD_TOP, CARD_RIGHT, CARD_BOTTOM,
                                    CARD_RADIUS)

    # Outer drop shadow filter: keep its region aligned with the canvas.
    shadow = root.find(f".//{qn('filter')}[@id='filter0_d_2_34']")
    if shadow is not None:
        shadow.set("x", fmt(CANVAS_X))
        shadow.set("y", fmt(CANVAS_Y))
        shadow.set("width", fmt(width))
        shadow.set("height", fmt(height))

    clip0_path = root.find(f".//{qn('clipPath')}[@id='clip0_2_34']/{qn('path')}")
    if clip0_path is None:
        raise ValueError("Could not find the card clip path (clip0_2_34).")
    clip0_path.set("d", card_path_d)

    # The card body itself is the first path inside the clipped group.
    card_body = find_child_by_attr(clip0_group, "path", fill="#DFDBC3")
    card_body.set("d", card_path_d)

    chrome_group = clip0_group.find(f"./{qn('g')}[@filter='url(#filter1_d_2_34)']")
    if chrome_group is None:
        raise ValueError("Could not find the window chrome group.")
    chrome_rect = find_child_by_attr(chrome_group, "rect", transform="translate(10 8)")
    chrome_rect.set("width", fmt(CARD_RIGHT - CARD_LEFT))
    chrome_rect.set("height", fmt(CHROME_HEIGHT))
    chrome_filter = root.find(f".//{qn('filter')}[@id='filter1_d_2_34']")
    if chrome_filter is not None:
        chrome_filter.set("width", fmt(CARD_RIGHT - CARD_LEFT))

    # Body fill behind the content, from below the chrome to the card bottom.
    body_rect = find_child_by_attr(clip0_group, "rect", transform="translate(10 59)")
    body_rect.set("width", fmt(CARD_RIGHT - CARD_LEFT))
    body_rect.set("height", fmt(CARD_BOTTOM - 59))

    # Window title (converted to outlines in the export) stays centred on the card.
    title = find_child_by_attr(chrome_group, "path", fill="#595959")
    title_center = CARD_LEFT + (CARD_RIGHT - CARD_LEFT) / 2
    title.set("transform", f"translate({fmt(title_center - CHROME_TITLE_CENTER)} 0)")

    # Vertical separator between the text column and the illustration.
    separator = next(
        child for child in clip0_group
        if child.tag == qn("path") and child.get("stroke", "").lower() == "black"
    )
    separator.set("d", f"M {fmt(DIVIDER_X - 1)} {fmt(DIVIDER_TOP)} "
                       f"L {fmt(DIVIDER_X + 1)} {fmt(DIVIDER_BOTTOM)}")

    # Left information pane clip (wide enough for the value glow).
    for clip_rect in root.iter(qn("rect")):
        if clip_rect.get("transform") == "translate(46 101)":
            clip_rect.set("width", fmt(PANE_CLIP_WIDTH))
            clip_rect.set("height", fmt(PANE_BOTTOM - 101))


def add_glow_filters(root: ET.Element, palette: dict[str, str]) -> None:
    """Add two static filters: a wide bloom for the frame, a tight one for values.

    The glow is colored with feFlood from the text/stroke alpha, so the crisp
    SourceGraphic stays on top and only the halo picks up the neon color.
    """
    defs = root.find(qn("defs"))
    if defs is None:
        defs = ET.SubElement(root, qn("defs"))

    def bloom(filter_id: str, sigma: float, color: str, alpha: float,
              region: dict[str, str], double: bool) -> None:
        filt = ET.SubElement(defs, qn("filter"), {
            "id": filter_id,
            "color-interpolation-filters": "sRGB",
            **region,
        })
        ET.SubElement(filt, qn("feGaussianBlur"), {
            "in": "SourceAlpha",
            "stdDeviation": fmt(sigma),
            "result": "blur",
        })
        ET.SubElement(filt, qn("feFlood"), {
            "flood-color": color,
            "result": "color",
        })
        ET.SubElement(filt, qn("feComposite"), {
            "in": "color",
            "in2": "blur",
            "operator": "in",
            "result": "glow",
        })
        fade = ET.SubElement(filt, qn("feComponentTransfer"), {
            "in": "glow",
            "result": "faded",
        })
        ET.SubElement(fade, qn("feFuncA"), {"type": "linear", "slope": fmt(alpha)})
        merge = ET.SubElement(filt, qn("feMerge"))
        passes = ["faded", "faded", "SourceGraphic"] if double else ["faded", "SourceGraphic"]
        for source in passes:
            ET.SubElement(merge, qn("feMergeNode"), {"in": source})

    bloom("neon-frame-glow", BORDER_GLOW_STD, palette["glow"], 0.85,
          {"x": "-3%", "y": "-9%", "width": "106%", "height": "118%"}, True)
    bloom("neon-value-glow", VALUE_GLOW_STD, palette["value_glow"], 0.55,
          {"x": "-40%", "y": "-140%", "width": "180%", "height": "380%"}, False)


def add_sweep(root: ET.Element, palette: dict[str, str], mode: str) -> None:
    """Add a CRT-style scan band clipped to the card.

    The band is a transparent-edged gradient, so it enters and leaves softly. It sits
    above the content but is clipped to the rounded card, and it rests off-screen
    between passes instead of sweeping continuously. The band is rotated so its long
    axis is perpendicular to the top-left to bottom-right travel direction.

    The CRT grid underneath is static artwork revealed by a soft mask that travels with
    the band, so the lines light up around the sweep instead of sitting on the card all
    the time.
    """
    defs = root.find(qn("defs"))
    if defs is None:
        defs = ET.SubElement(root, qn("defs"))

    clip = ET.SubElement(defs, qn("clipPath"), {"id": "neon-card-clip"})
    ET.SubElement(clip, qn("path"), {
        "d": rounded_rect_path(CARD_LEFT, CARD_TOP, CARD_RIGHT, CARD_BOTTOM,
                               CARD_RADIUS),
    })

    gradient = ET.SubElement(defs, qn("linearGradient"), {
        "id": "neon-sweep-gradient",
        "x1": "0", "y1": "0", "x2": "0", "y2": "1",
    })
    for offset, stop_opacity in (("0", "0"), ("0.5", "0.55"), ("1", "0")):
        ET.SubElement(gradient, qn("stop"), {
            "offset": offset,
            "stop-color": palette["glow"],
            "stop-opacity": stop_opacity,
        })

    # The band is laid out flat in a rotated frame: local +Y points down-right.
    band_top = -(SWEEP_TRAVEL / 2 + SWEEP_HEIGHT / 2 + 12)
    center_x = (CARD_LEFT + CARD_RIGHT) / 2
    center_y = (CARD_TOP + CARD_BOTTOM) / 2
    frame = f"translate({fmt(center_x)} {fmt(center_y)}) rotate({fmt(SWEEP_ANGLE)})"

    # A CRT grid gives the moving band a screen to cross. The grid is painted across
    # the card, but a soft mask (which uses the band's own keyframes) reveals it only
    # in a halo around the sweep.
    grid_opacity = SWEEP_GRID_OPACITY[mode]
    if grid_opacity:
        size = fmt(SWEEP_GRID_SIZE)
        pattern = ET.SubElement(defs, qn("pattern"), {
            "id": "neon-crt-grid",
            "width": size,
            "height": size,
            "patternUnits": "userSpaceOnUse",
        })
        ET.SubElement(pattern, qn("path"), {
            "d": f"M {size} 0 H 0 V {size}",
            "fill": "none",
            "stroke": palette["grid"],
            "stroke-width": "1",
        })

        glow_gradient = ET.SubElement(defs, qn("linearGradient"), {
            "id": "neon-grid-glow",
            "x1": "0", "y1": "0", "x2": "0", "y2": "1",
        })
        for offset, stop_opacity in (("0", "0"), ("0.3", "0.55"),
                                     ("0.5", "1"), ("0.7", "0.55"), ("1", "0")):
            ET.SubElement(glow_gradient, qn("stop"), {
                "offset": offset,
                "stop-color": "#FFFFFF",
                "stop-opacity": stop_opacity,
            })

        mask = ET.SubElement(defs, qn("mask"), {
            "id": "neon-grid-mask",
            "maskUnits": "userSpaceOnUse",
            "x": fmt(CARD_LEFT),
            "y": fmt(CARD_TOP),
            "width": fmt(CARD_RIGHT - CARD_LEFT),
            "height": fmt(CARD_BOTTOM - CARD_TOP),
        })
        mask_group = ET.SubElement(mask, qn("g"), {"transform": frame})
        ET.SubElement(mask_group, qn("rect"), {
            "class": "neon-sweep-band",
            "x": fmt(-SWEEP_BAND_WIDTH / 2),
            "y": fmt(band_top - (SWEEP_GLOW_HEIGHT - SWEEP_HEIGHT) / 2),
            "width": fmt(SWEEP_BAND_WIDTH),
            "height": fmt(SWEEP_GLOW_HEIGHT),
            "fill": "url(#neon-grid-glow)",
        })

        grid = ET.Element(qn("g"), {
            "class": "neon-grid",
            "clip-path": "url(#neon-card-clip)",
            "mask": "url(#neon-grid-mask)",
            "opacity": fmt(grid_opacity),
        })
        ET.SubElement(grid, qn("rect"), {
            "x": fmt(CARD_LEFT),
            "y": fmt(CARD_TOP),
            "width": fmt(CARD_RIGHT - CARD_LEFT),
            "height": fmt(CARD_BOTTOM - CARD_TOP),
            "fill": "url(#neon-crt-grid)",
        })
        root.insert(list(root).index(defs), grid)

    group = ET.Element(qn("g"), {
        "class": "neon-sweep",
        "clip-path": "url(#neon-card-clip)",
        "opacity": fmt(SWEEP_OPACITY[mode]),
    })
    rotated = ET.SubElement(group, qn("g"), {"transform": frame})
    ET.SubElement(rotated, qn("rect"), {
        "class": "neon-sweep-band",
        "x": fmt(-SWEEP_BAND_WIDTH / 2),
        "y": fmt(band_top),
        "width": fmt(SWEEP_BAND_WIDTH),
        "height": fmt(SWEEP_HEIGHT),
        "fill": "url(#neon-sweep-gradient)",
    })

    # Keep the frame stroke on top of the moving band.
    root.insert(list(root).index(defs), group)

    style = ET.Element(qn("style"))
    style.text = (
        ".neon-sweep-band{animation:neon-sweep "
        + fmt(SWEEP_DURATION)
        + "s linear infinite;}"
        "@keyframes neon-sweep{0%{transform:translateY(0)}"
        "70%,100%{transform:translateY("
        + fmt(SWEEP_TRAVEL)
        + "px)}}"
        "@media (prefers-reduced-motion:reduce){.neon-sweep,.neon-grid{display:none}}"
    )
    root.insert(1 if len(root) > 1 else 0, style)


def add_neon_frame(root: ET.Element, palette: dict[str, str]) -> None:
    """Draw a glowing stroke over the card edge, outside the card clip."""
    frame = ET.Element(qn("path"), {
        "id": "neon-frame",
        "d": rounded_rect_path(CARD_LEFT, CARD_TOP, CARD_RIGHT, CARD_BOTTOM,
                               CARD_RADIUS),
        "fill": "none",
        "stroke": palette["glow"],
        "stroke-width": "1.6",
        "opacity": "0.9",
        "filter": "url(#neon-frame-glow)",
    })
    defs = root.find(qn("defs"))
    if defs is not None:
        root.insert(list(root).index(defs), frame)
    else:
        root.append(frame)


def extract_cactus_group(clip0_group: ET.Element, info_group: ET.Element,
                         transform: str) -> ET.Element:
    """Wrap the exported cactus paths in a group so the whole block can be scaled."""
    children = list(clip0_group)
    info_index = children.index(info_group)

    art_start = None
    for index, child in enumerate(children[:info_index]):
        if (child.tag == qn("path")
                and child.get("fill") == "url(#paint0_linear_2_34)"):
            art_start = index
            break
    if art_start is None:
        raise ValueError("Could not locate the cactus illustration in the source SVG.")

    art_paths = children[art_start:info_index]
    for path in art_paths:
        clip0_group.remove(path)

    group = ET.Element(qn("g"), {"id": "cactus-art", "transform": transform})
    group.extend(art_paths)
    clip0_group.insert(art_start, group)
    return group


def apply_theme(root: ET.Element, mode: str, glow: bool = True,
                sweep: bool = True) -> None:
    palette = PALETTES[mode]

    style = font_style_element()
    if style is not None:
        root.insert(0, style)

    info_group = find_information_group(root)
    parent_map = {child: parent for parent in root.iter() for child in parent}
    parent = parent_map[info_group]
    insert_index = list(parent).index(info_group)

    scale = ART_SCALE
    tx = ART_LEFT - ART_SOURCE_X * scale
    ty = ART_TOP - ART_SOURCE_Y * scale
    transform = f"translate({fmt(tx)} {fmt(ty)}) scale({fmt(scale)})"

    art_right = ART_LEFT + ART_SOURCE_W * scale
    art_bottom = ART_TOP + ART_SOURCE_H * scale
    if art_right > CARD_RIGHT - 8 or art_bottom > CARD_BOTTOM - 8:
        raise ValueError(
            "The scaled cactus artwork no longer fits inside the card; "
            "lower ART_SCALE or raise CARD_RIGHT / CARD_BOTTOM."
        )

    art_group = extract_cactus_group(parent, info_group, transform)
    parent.remove(info_group)
    # Geometry is edited while the original Figma fills are still in place.
    resize_card(root, parent)

    # Both themes replace the exported surfaces, not just the dark one: the light
    # theme is Monokai Sun, so its cream and chrome differ from the Figma limestone.
    for element in root.iter():
        fill = element.get("fill", "").lower()
        if fill == "#dfdbc3":
            element.set("fill", palette["background"])
        elif fill == "#f5f5f5":
            element.set("fill", palette["chrome"])
        elif fill == "#595959":
            # The wordmark in the window header.
            element.set("fill", palette["header_title"])
        if element.get("stroke", "").lower() == "black":
            element.set("stroke", palette["divider"])

    # In the export the final six #102B2A paths of the artwork spell "CATCUS";
    # the two earlier ones are the eyes, which stay dark in both themes.
    wordmark_paths = [
        child for child in art_group
        if child.tag == qn("path") and child.get("fill", "").lower() == "#102b2a"
    ][-6:]
    for element in wordmark_paths:
        element.set("fill", palette["wordmark"])

    if glow:
        add_glow_filters(root, palette)
        if sweep:
            add_sweep(root, palette, mode)
        add_neon_frame(root, palette)

    parent.insert(insert_index, build_information_group(palette, glow))

    # Set a clear accessible description for each theme without altering the art.
    desc = root.find(qn("desc"))
    if desc is not None:
        desc.text = (
            "Anuj-72 GitHub profile dashboard with cactus artwork and completed "
            f"Personal, Coding Profiles, and Contact information ({mode} theme)."
        )


def generate(source: Path, out_dir: Path, glow: bool = True,
             sweep: bool = True) -> list[Path]:
    if not source.is_file():
        raise FileNotFoundError(f"Source SVG not found: {source}")
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []

    for mode in ("light", "dark"):
        tree = ET.parse(source)
        root = tree.getroot()
        if root.tag != qn("svg"):
            raise ValueError("Source file is not an SVG document.")
        apply_theme(root, mode, glow, sweep)
        out_path = out_dir / f"profile-{mode}.svg"
        tree.write(out_path, encoding="utf-8", xml_declaration=True)
        # Parse again to catch malformed output before reporting success.
        ET.parse(out_path)
        outputs.append(out_path)
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source", nargs="?", type=Path, default=DEFAULT_SOURCE,
        help="original Figma-exported light SVG (default: %(default)s)",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=DEFAULT_OUTPUT,
        help="directory for profile-light.svg and profile-dark.svg (default: script directory)",
    )
    parser.add_argument(
        "--no-glow", action="store_true",
        help="omit the neon frame and value bloom for a flat card",
    )
    parser.add_argument(
        "--no-sweep", action="store_true",
        help="keep the neon bloom but omit the scan band and CRT grid",
    )
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    out_dir = args.out_dir.expanduser().resolve()
    try:
        outputs = generate(source, out_dir, glow=not args.no_glow,
                           sweep=not args.no_sweep)
    except (OSError, ET.ParseError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    for path in outputs:
        print(f"Generated and validated: {path}")
    print("The original Figma SVG was not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
