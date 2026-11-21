#!/usr/bin/env python3
"""news-image-20261121 -- The World in One Day: Saturday 21 November 2026.

A Python 3.13 standard-library-only program that deterministically renders a
1024x1024 PNG poster summing up the world news of Saturday 21 November 2026:
a giant date masthead, six illustrated panels covering the day's biggest real
stories, and an also-today footer. Writes /output/entry.png (or
$MAKEFUN_OUTPUT_DIR/entry.png). No network, no randomness, no time dependence:
the same bytes come out of every run.
"""

import os
import struct
import zlib

W, H = 1024, 1024

# ---------------------------------------------------------------- palette ---
PAPER = (246, 241, 231)      # newsprint cream
INK = (20, 32, 46)           # dark navy ink
NAVY = (18, 35, 58)          # masthead band
NAVY_DK = (12, 24, 40)
CREAM = (246, 241, 231)
RED = (179, 39, 30)          # accent red
RED_DK = (142, 31, 22)
TEAL = (31, 78, 95)
BLUE = (39, 68, 114)
OCHRE = (107, 78, 30)
SLATE = (46, 64, 87)
WHITE = (255, 255, 255)
GREY = (120, 116, 106)
LIGHT = (232, 226, 212)      # panel art backdrop
GOLD = (212, 160, 32)

# ------------------------------------------------------------- PNG encoder --
# Minimal deterministic PNG writer: 8-bit RGB, one zlib stream, fixed level.
# zlib.compress is deterministic for identical input and level, so two runs
# of this program produce byte-identical files.

def encode_png(rgb, width, height):
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)  # filter: none
        raw += rgb[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(kind, data):
        out = struct.pack(">I", len(data)) + kind + data
        out += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", comp) + chunk(b"IEND", b""))


# ------------------------------------------------------------------ canvas --
class Canvas:
    def __init__(self, width, height, bg):
        self.w = width
        self.h = height
        self.px = bytearray(bg) * (width * height)

    def set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i:i + 3] = bytes(color)

    def rect(self, x, y, w, h, color):
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.px[i:(i + (x1 - x0) * 3)] = bytes(color) * (x1 - x0)

    def hline(self, x, y, w, color, t=1):
        self.rect(x, y, w, t, color)

    def vline(self, x, y, h, color, t=1):
        self.rect(x, y, t, h, color)

    def line(self, x0, y0, x1, y1, color, t=1):
        """Bresenham line with square thickness t."""
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.rect(x0 - t // 2, y0 - t // 2, t, t, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def circle(self, cx, cy, r, color, fill=True):
        for yy in range(cy - r, cy + r + 1):
            for xx in range(cx - r, cx + r + 1):
                d = (xx - cx) ** 2 + (yy - cy) ** 2
                if fill:
                    if d <= r * r:
                        self.set(xx, yy, color)
                else:
                    if r * r - 2 * r <= d <= r * r:
                        self.set(xx, yy, color)

    def triangle(self, p1, p2, p3, color):
        """Filled triangle via scanline fill."""
        pts = sorted([p1, p2, p3], key=lambda p: p[1])
        (x0, y0), (x1, y1), (x2, y2) = pts
        if y0 == y2:
            return
        for y in range(y0, y2 + 1):
            xs = []
            for (ax, ay), (bx, by) in (((x0, y0), (x1, y1)),
                                       ((x1, y1), (x2, y2)),
                                       ((x0, y0), (x2, y2))):
                if ay == by:
                    continue
                if min(ay, by) <= y <= max(ay, by):
                    xs.append(ax + (bx - ax) * (y - ay) / (by - ay))
            if len(xs) >= 2:
                xa, xb = int(min(xs)), int(max(xs))
                self.rect(xa, y, xb - xa + 1, 1, color)

    def poly(self, points, color):
        """Filled polygon via scanline fill."""
        ys = [p[1] for p in points]
        for y in range(min(ys), max(ys) + 1):
            xs = []
            n = len(points)
            for i in range(n):
                ax, ay = points[i]
                bx, by = points[(i + 1) % n]
                if ay == by:
                    continue
                if min(ay, by) <= y < max(ay, by) or y == max(ys):
                    xs.append(ax + (bx - ax) * (y - ay) / (by - ay))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                xa, xb = int(xs[i]), int(xs[i + 1])
                self.rect(xa, y, xb - xa + 1, 1, color)


# ------------------------------------------------------------ 5x7 bitmap font
# Each glyph is 7 rows of 5 bits, written as strings. Uppercase only; the
# poster renders all text in capitals. Unknown characters become a blank.
FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ",": ("00000", "00000", "00000", "00000", "01100", "00100", "01000"),
    ";": ("00000", "01100", "00000", "01100", "01100", "00100", "01000"),
    ":": ("00000", "01100", "00000", "01100", "00000", "01100", "00000"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    "?": ("01110", "10001", "00001", "00110", "00100", "00000", "00100"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    '"': ("01010", "01010", "01010", "00000", "00000", "00000", "00000"),
    "-": ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    "(": ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "%": ("11001", "11010", "00010", "00100", "01000", "01011", "10011"),
    "&": ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    "+": ("00000", "00100", "00100", "01110", "00100", "00100", "00000"),
    "=": ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    "$": ("00100", "01111", "10100", "01110", "00101", "11110", "00100"),
    "*": ("00000", "10101", "01110", "10101", "00000", "00000", "00000"),
    "#": ("01010", "01010", "11111", "01010", "11111", "01010", "01010"),
    "@": ("01110", "10001", "10111", "10101", "10110", "10000", "01110"),
    "~": ("00000", "00000", "01001", "10110", "00000", "00000", "00000"),
    "^": ("00100", "01010", "10001", "00000", "00000", "00000", "00000"),
    "_": ("00000", "00000", "00000", "00000", "00000", "00000", "11111"),
    "[": ("01110", "01000", "01000", "01000", "01000", "01000", "01110"),
    "]": ("01110", "00010", "00010", "00010", "00010", "00010", "01110"),
    "<": ("00010", "00100", "01000", "10000", "01000", "00100", "00010"),
    ">": ("01000", "00100", "00010", "00001", "00010", "00100", "01000"),
    "•": ("00000", "00000", "01100", "01100", "01100", "00000", "00000"),
    "°": ("01100", "10010", "10010", "01100", "00000", "00000", "00000"),
    "×": ("00000", "10001", "01010", "00100", "01010", "10001", "00000"),
    "→": ("00000", "00100", "00010", "11111", "00010", "00100", "00000"),
}
BLANK = ("00000", "00000", "00000", "00000", "00000", "00000", "00000")

NORMALIZE = {
    "’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-",
    "·": "•", "−": "-", "…": "...", "é": "E", "í": "I", "ó": "O",
    "á": "A", "ú": "U", "ñ": "N",
}


def glyph_width(scale):
    return 5 * scale + scale  # 5 columns + 1 column gap


def text_width(text, scale):
    text = "".join(NORMALIZE.get(c, c) for c in text).upper()
    return len(text) * glyph_width(scale) - scale if text else 0


def draw_text(cv, x, y, text, scale, color):
    """Draw one line of text; returns the x just past the last glyph."""
    text = "".join(NORMALIZE.get(c, c) for c in text).upper()
    cx = x
    for ch in text:
        rows = FONT.get(ch, BLANK)
        for r in range(7):
            row = rows[r]
            for c in range(5):
                if row[c] == "1":
                    cv.rect(cx + c * scale, y + r * scale, scale, scale, color)
        cx += glyph_width(scale)
    return cx


def wrap_text(text, scale, max_width):
    """Greedy word wrap; returns a list of lines."""
    text = "".join(NORMALIZE.get(c, c) for c in text).upper()
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if text_width(trial, scale) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_lines(cv, x, y, lines, scale, color, leading=None):
    """Draw wrapped lines; returns y just past the last line."""
    lh = 7 * scale + (leading if leading is not None else scale)
    for ln in lines:
        draw_text(cv, x, y, ln, scale, color)
        y += lh
    return y

# ------------------------------------------------------- panel illustrations --
# Each scene is drawn inside the art area (x, y, w, h) of its panel with
# simple flat vector shapes on a light backdrop, so every story is clear
# from its picture even at small size.

def scene_missile(cv, x, y, w, h):
    """Night sky, a missile streaking down, burst over a map of Poland."""
    cv.rect(x, y, w, h, (16, 28, 48))
    # stars
    for sx, sy in ((18, 12), (52, 30), (96, 10), (140, 26), (188, 14),
                   (232, 34), (278, 12), (322, 28), (366, 16), (410, 30),
                   (70, 52), (250, 56), (330, 52)):
        cv.rect(x + sx, y + sy, 3, 3, (200, 205, 215))
    # dashed flight path
    for i in range(9):
        cv.rect(x + 250 - i * 16, y + 8 + i * 7, 10, 3, (240, 200, 120))
    # missile body, nose down-left
    cv.poly([(x + 268, y + 6), (x + 284, y + 22), (x + 276, y + 30),
             (x + 260, y + 14)], (220, 225, 235))
    cv.poly([(x + 284, y + 22), (x + 292, y + 30), (x + 284, y + 34),
             (x + 276, y + 30)], (179, 39, 30))
    # flame
    cv.triangle((x + 288, y + 28), (x + 306, y + 40), (x + 292, y + 44),
                (240, 140, 40))
    # explosion burst at the impact point, south-east of the map
    bx, by = x + 150, y + h - 30
    for ang in range(0, 360, 30):
        import math
        r1, r2 = 10, 26
        a = math.radians(ang)
        cv.line(bx, by, bx + int(r2 * math.cos(a)), by + int(r2 * math.sin(a)),
                (240, 140, 40), 3)
    cv.circle(bx, by, 14, (240, 140, 40))
    cv.circle(bx, by, 8, (250, 210, 90))
    # rough outline of Poland with a red impact dot
    cv.poly([(x + 96, y + h - 58), (x + 150, y + h - 62), (x + 168, y + h - 44),
             (x + 158, y + h - 26), (x + 122, y + h - 20), (x + 100, y + h - 36)],
            (110, 140, 170))
    cv.circle(bx, by, 5, RED)
    cv.rect(x + 300, y + h - 30, 150, 18, (16, 28, 48))
    draw_text(cv, x + 306, y + h - 27, "NO INJURIES", 1, (240, 200, 120))


def scene_markets(cv, x, y, w, h):
    """Falling red chart on the left, the day's drops as big figures right."""
    cv.rect(x, y, w, h, LIGHT)
    # bars, descending, left half
    bars = [58, 52, 46, 38, 30, 22, 14]
    bw = 22
    for i, bh in enumerate(bars):
        bx = x + 22 + i * (bw + 10)
        cv.rect(bx, y + h - 12 - bh, bw, bh, (196, 120, 110))
    # falling line over the bars
    pts = [(x + 33 + i * 32, y + h - 18 - b) for i, b in enumerate(bars)]
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        cv.line(ax, ay, bx, by, RED, 4)
    for px, py in pts:
        cv.circle(px, py, 4, RED_DK)
    # big red figures, right half
    draw_text(cv, x + 252, y + 14, "S&P -3.7%", 2, RED)
    draw_text(cv, x + 252, y + 40, "NASDAQ -5.3%", 2, RED_DK)
    draw_text(cv, x + 252, y + 66, "NVIDIA -13.8%", 2, INK)


def scene_justice(cv, x, y, w, h):
    """Scales of justice in front of a courthouse colonnade."""
    cv.rect(x, y, w, h, (214, 226, 232))
    # courthouse columns
    for i in range(5):
        cx = x + 28 + i * 88
        cv.rect(cx, y + 8, 16, h - 16, (160, 172, 186))
        cv.rect(cx - 4, y + 4, 24, 8, (140, 152, 168))
    cv.rect(x, y + h - 12, w, 12, (140, 152, 168))
    # scales, centred
    cx, top = x + w // 2, y + 18
    cv.vline(cx, top, 62, INK, 4)
    cv.hline(cx - 52, top + 6, 104, INK, 4)
    cv.circle(cx, top + 2, 6, GOLD)
    for side in (-1, 1):
        px = cx + side * 52
        cv.line(px, top + 8, px, top + 34, INK, 2)
        cv.triangle((px - 24, top + 34), (px + 24, top + 34),
                    (px, top + 52), GOLD)
    cv.rect(cx - 26, top + 62, 52, 6, INK)
    # vote badge, bottom-left, on a cream card so it reads over the columns
    cv.rect(x + 12, y + h - 38, 116, 30, (250, 246, 238))
    draw_text(cv, x + 20, y + h - 30, "9 - 6", 3, RED_DK)


def scene_quake(cv, x, y, w, h):
    """Andes peaks, a seismograph zigzag and cracked ground."""
    cv.rect(x, y, w, h, (238, 228, 205))
    # mountains
    cv.triangle((x + 10, y + h - 30), (x + 130, y + 12), (x + 250, y + h - 30),
                (120, 110, 88))
    cv.triangle((x + 180, y + h - 30), (x + 300, y + 26), (x + 420, y + h - 30),
                (96, 88, 70))
    cv.triangle((x + 104, y + 28), (x + 130, y + 12), (x + 156, y + 28),
                (250, 246, 238))
    cv.triangle((x + 276, y + 40), (x + 300, y + 26), (x + 324, y + 40),
                (250, 246, 238))
    # seismograph trace
    trace = [(0, 52), (40, 52), (52, 30), (66, 74), (80, 40), (94, 66),
             (110, 18), (128, 84), (146, 34), (162, 70), (178, 44),
             (196, 58), (220, 52), (260, 52), (300, 52), (340, 52),
             (380, 52), (420, 52)]
    for (ax, ay), (bx, by) in zip(trace, trace[1:]):
        cv.line(x + 20 + ax, y + ay, x + 20 + bx, y + by, RED, 3)
    # cracked ground
    cv.line(x + 30, y + h - 8, x + 90, y + h - 22, INK, 2)
    cv.line(x + 90, y + h - 22, x + 150, y + h - 10, INK, 2)
    cv.line(x + 320, y + h - 8, x + 380, y + h - 24, INK, 2)
    draw_text(cv, x + w - 118, y + 8, "M 6.8", 3, RED_DK)


def scene_rikers(cv, x, y, w, h):
    """Prison bars, one gate swung open onto a skyline and a closing date."""
    cv.rect(x, y, w, h, (210, 216, 224))
    # skyline behind the bars
    for bx, bh in ((30, 46), (78, 64), (126, 40), (330, 58), (378, 44)):
        cv.rect(x + bx, y + h - 18 - bh, 34, bh, (150, 160, 172))
    # bars, with the middle pair open
    for i in range(9):
        bx = x + 14 + i * 48
        if i in (4, 5):
            continue
        cv.rect(bx, y + 6, 10, h - 12, INK)
    cv.rect(x + 14, y + 2, w - 28, 6, INK)
    cv.rect(x + 14, y + h - 8, w - 28, 6, INK)
    # open gate swung out (diagonal bars)
    cv.line(x + 218, y + 10, x + 262, y + h - 12, INK, 8)
    cv.line(x + 238, y + 10, x + 282, y + h - 12, INK, 8)
    # closing-date badge, centred on a cream card so it reads over the bars
    cv.rect(x + w // 2 - 84, y + h - 46, 168, 32, (250, 246, 238))
    draw_text(cv, x + w // 2 - 66, y + h - 38, "BY 2032", 3, RED_DK)


def scene_flags(cv, x, y, w, h):
    """Union Jack and EU flag facing each other, joined by an arrow."""
    cv.rect(x, y, w, h, LIGHT)
    # Union Jack, simplified: blue field, white and red crosses
    fx, fy, fw, fh = x + 22, y + 8, 150, 62
    cv.rect(fx, fy, fw, fh, (0, 36, 125))
    cv.rect(fx, fy + fh // 2 - 11, fw, 22, WHITE)
    cv.rect(fx + fw // 2 - 11, fy, 22, fh, WHITE)
    cv.rect(fx, fy + fh // 2 - 7, fw, 14, (200, 16, 46))
    cv.rect(fx + fw // 2 - 7, fy, 14, fh, (200, 16, 46))
    cv.line(fx, fy, fx + fw, fy + fh, WHITE, 5)
    cv.line(fx + fw, fy, fx, fy + fh, WHITE, 5)
    # EU flag: blue field, ring of gold stars
    ex, ey, ew, eh = x + w - 172, y + 8, 150, 62
    cv.rect(ex, ey, ew, eh, (0, 51, 153))
    import math
    for k in range(12):
        a = math.radians(k * 30 - 90)
        sx = ex + ew // 2 + int(30 * math.cos(a))
        sy = ey + eh // 2 + int(24 * math.sin(a))
        cv.circle(sx, sy, 4, GOLD)
    # joining arrow
    cv.line(x + 190, y + 39, x + w - 190, y + 39, INK, 5)
    cv.triangle((x + w - 190, y + 27), (x + w - 190, y + 51),
                (x + w - 168, y + 39), INK)
    draw_text(cv, x + 30, y + h - 20, "UK  +  EU", 2, INK)
    draw_text(cv, x + w - 218, y + h - 20, "FROM 2028", 2, BLUE)


# ------------------------------------------------------------------- panels --
PANELS = [
    {
        "kicker": "CONFLICT · POLAND",
        "color": RED_DK,
        "scene": scene_missile,
        "headline": "RUSSIAN MISSILE CRASHES IN POLAND",
        "body": ("A Kh-101 cruise missile came down in south-east Poland during "
                 "a huge Russian air attack on Ukraine. No one was hurt. NATO "
                 "jets scrambled; Warsaw calls it a deliberate provocation."),
    },
    {
        "kicker": "MARKETS · WALL STREET",
        "color": (122, 31, 31),
        "scene": scene_markets,
        "headline": "WALL STREET SLIDES INTO CORRECTION",
        "body": ("The S&P 500 fell 3.7% and the Nasdaq 5.3% in an AI-led "
                 "sell-off. The SEC is examining Nvidia accounting; its "
                 "shares fell 13.8%."),
    },
    {
        "kicker": "JUSTICE · THE HAGUE",
        "color": TEAL,
        "scene": scene_justice,
        "headline": "WORLD COURT: MYANMAR COMMITTED GENOCIDE",
        "body": ("The ICJ ruled 9-6 that Myanmar's forces committed genocide "
                 "against the Rohingya in 2017. It ordered an investigation "
                 "and compensation. Myanmar called the ruling unfair."),
    },
    {
        "kicker": "DISASTER · PERU",
        "color": OCHRE,
        "scene": scene_quake,
        "headline": "MAGNITUDE 6.8 QUAKE SHAKES PERU",
        "body": ("A 6.8 quake struck the Junin region at 00:09 UTC, deep "
                 "below the Andes. Tremors were felt in Lima, 320 km away. "
                 "No immediate reports of casualties or major damage."),
    },
    {
        "kicker": "NEW YORK · JUSTICE",
        "color": SLATE,
        "scene": scene_rikers,
        "headline": "RIKERS ISLAND TO CLOSE BY 2032",
        "body": ("Mayor Mamdani unveiled a plan to shut the notorious jail "
                 "complex by 2032 and replace it with four smaller borough "
                 "jails, cutting the jail population to 4,100."),
    },
    {
        "kicker": "DIPLOMACY · BRUSSELS",
        "color": BLUE,
        "scene": scene_flags,
        "headline": "UK AND EU SEAL POST-BREXIT RESET",
        "body": ("Deals signed in Brussels scrap most food and farm checks "
                 "from March 2028, link carbon markets from January 2028, "
                 "and open youth mobility for up to 100,000 people."),
    },
]

ALSO_TODAY = (
    "COP31 talks in Antalya run into overtime as the draft drops every mention "
    "of fossil fuels • Trump threatens to bar US firms from building AI data "
    "centres abroad • KL Rahul becomes the first Indian opener with Test "
    "hundreds in all SENA countries • A Los Angeles jury convicts the man who "
    "started the deadly Palisades Fire"
)


def draw_panel(cv, px, py, pw, ph, panel):
    cv.rect(px, py, pw, ph, WHITE)
    cv.rect(px, py, pw, 2, panel["color"])
    cv.rect(px, py + ph - 2, pw, 2, panel["color"])
    cv.rect(px, py, 2, ph, panel["color"])
    cv.rect(px + pw - 2, py, 2, ph, panel["color"])
    # kicker strip
    cv.rect(px + 2, py + 2, pw - 4, 30, panel["color"])
    draw_text(cv, px + 14, py + 11, panel["kicker"], 1, WHITE)
    # illustration
    ax, ay, aw, ah = px + 12, py + 42, pw - 24, 96
    panel["scene"](cv, ax, ay, aw, ah)
    # headline, up to 2 lines
    hl = wrap_text(panel["headline"], 2, pw - 28)
    draw_lines(cv, px + 14, py + 150, hl[:2], 2, INK, leading=4)
    # body, up to 3 lines
    bl = wrap_text(panel["body"], 1, pw - 28)
    draw_lines(cv, px + 14, py + 150 + 2 * (14 + 4) + 8, bl[:3], 1, INK,
               leading=3)

# ------------------------------------------------------------ masthead/footer --

def draw_masthead(cv):
    cv.rect(0, 0, W, 172, NAVY)
    cv.rect(0, 172, W, 4, RED)
    # small globe mark, top-left corner (clear of the centred date)
    cv.circle(34, 32, 13, (70, 110, 160), fill=False)
    cv.hline(21, 32, 26, (70, 110, 160), 2)
    cv.vline(34, 19, 26, (70, 110, 160), 2)
    title = "THE WORLD IN ONE DAY"
    tw = text_width(title, 2)
    draw_text(cv, (W - tw) // 2, 26, title, 2, (200, 205, 215))
    # giant date
    date = "SATURDAY 21 NOVEMBER 2026"
    dw = text_width(date, 6)
    draw_text(cv, (W - dw) // 2, 58, date, 6, CREAM)
    sub = ("SIX STORIES THAT DEFINED THE DAY - WARSAW - NEW YORK - LIMA - "
           "THE HAGUE - BRUSSELS - ANTALYA")
    sw = text_width(sub, 1)
    draw_text(cv, (W - sw) // 2, 128, sub, 1, (200, 205, 215))
    cv.hline((W - 120) // 2, 148, 120, RED, 3)


def draw_footer(cv):
    fy = 944
    cv.rect(0, fy, W, 80, NAVY_DK)
    draw_text(cv, 16, fy + 12, "ALSO TODAY", 2, (240, 200, 120))
    lines = wrap_text(ALSO_TODAY, 1, W - 32)
    draw_lines(cv, 16, fy + 36, lines[:2], 1, CREAM, leading=4)
    credit = "ALL STORIES REPORTED ON SATURDAY 21 NOVEMBER 2026 - POSTER EDITION"
    cw = text_width(credit, 1)
    draw_text(cv, (W - cw) // 2, fy + 66, credit, 1, GREY)


# ---------------------------------------------------------------------- main --

def render():
    cv = Canvas(W, H, PAPER)
    draw_masthead(cv)
    # 2 columns x 3 rows of panels
    pw, ph, gap = 488, 238, 16
    for i, panel in enumerate(PANELS):
        px = 16 + (i % 2) * (pw + gap)
        py = 188 + (i // 2) * (ph + gap)
        draw_panel(cv, px, py, pw, ph, panel)
    draw_footer(cv)
    return encode_png(bytes(cv.px), W, H)


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(out_dir, exist_ok=True)
    data = render()
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(data)
    print(f"wrote {path}: {len(data)} bytes, {W}x{H}")


if __name__ == "__main__":
    main()
