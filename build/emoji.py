# pyright: reportAttributeAccessIssue=false
# uharfbuzz is a compiled module without type stubs.
"""Emoji sequences from the Unicode data files, and HarfBuzz shaping of them."""

from pathlib import Path

import uharfbuzz as hb


def sequences(path: Path) -> list:
    """Return (code points, status, name) for each line of emoji-test.txt."""
    found = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or ";" not in line:
            continue
        points, rest = line.split(";", 1)
        status, _, name = rest.partition("#")
        found.append((tuple(int(p, 16) for p in points.split()), status.strip(), name.strip()))
    return found


def emoji_style_bases(path: Path) -> set:
    """Return the base characters of the emoji style sequences (base + FE0F)."""
    bases = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or ";" not in line:
            continue
        base, selector = line.split(";", 1)[0].split()
        if selector == "FE0F":
            bases.add(int(base, 16))
    return bases


class Shaper:
    """Shapes code points with one font. HarfBuzz applies GSUB, or morx if the font has no GSUB."""

    def __init__(self, path: Path):
        self.font = hb.Font(hb.Face(path.read_bytes()))

    def glyphs(self, points: tuple) -> list:
        """Return (glyph name, x advance) for each glyph."""
        buf = hb.Buffer()
        buf.add_codepoints(list(points))
        buf.guess_segment_properties()
        hb.shape(self.font, buf)
        return [
            (self.font.glyph_to_string(i.codepoint), p.x_advance)
            for i, p in zip(buf.glyph_infos, buf.glyph_positions)
        ]

    def emoji(self, points: tuple) -> str | None:
        """Return the one visible glyph of the sequence, or None."""
        run = self.glyphs(points)
        visible = [name for name, advance in run if advance > 0]
        if len(visible) != 1 or any(name in (".notdef", "gid0") for name, _ in run):
            return None
        return visible[0]
