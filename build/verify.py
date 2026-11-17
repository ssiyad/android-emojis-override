# pyright: reportAttributeAccessIssue=false
# fontTools tables are dynamic; pyright cannot see their attributes.
"""Check the built font: OpenType Sanitizer, tables, coverage, and HarfBuzz shaping.

Usage: verify.py SRC_DIR FONT

Every sequence of emoji-test.txt must shape to one glyph with GSUB, the same
glyph that morx gives in the source font. Every character of the stock emoji
fonts must be in the new font, so that no emoji that showed before becomes a
box.
"""

import sys
from pathlib import Path

import ots
from fontTools.ttLib import TTFont

sys.path.insert(0, str(Path(__file__).resolve().parent))  # run with python -I
from build import ASCENT, DESCENT, STRIKE_PPEM
from emoji import Shaper, sequences

# Text with emoji between other characters: ZWJ, skin tone, flag, keycap, VS16.
SAMPLES = {
    "❤️": "u2764",
    "\U0001f44d\U0001f3fd": None,
    "\U0001f1ee\U0001f1f3": "u1F1EE_u1F1F3",
    "#️⃣": None,
    "\U0001f3f4\U000e0067\U000e0062\U000e0073\U000e0063\U000e0074\U000e007f": None,
}


PRIVATE_USE = set(range(0xE000, 0xF900)) | set(range(0xF0000, 0x110000))


def main(src: Path, font_path: Path):
    checks = Checks(src, font_path)
    checks.sanitize()
    checks.tables()
    checks.sequences()
    checks.coverage()
    checks.samples()
    if checks.failures:
        print("\n".join(checks.failures))
        sys.exit(1)
    print(f"verify: {checks.count} checks passed")


class Checks:
    def __init__(self, src: Path, font_path: Path):
        self.src, self.path = src, font_path
        self.font = TTFont(font_path)
        self.failures, self.count = [], 0

    def sanitize(self):
        result = ots.sanitize(str(self.path), "/dev/null", capture_output=True)
        stderr = (result.stderr or b"").decode(errors="replace").strip()
        self.expect(result.returncode == 0, f"OTS rejects {self.path.name}: {stderr}")

    def tables(self):
        font = self.font
        self.expect("morx" not in font and "GSUB" in font, "the font must have GSUB and no morx")
        ppems = [s.bitmapSizeTable.ppemX for s in font["CBLC"].strikes]
        self.expect(ppems == [STRIKE_PPEM], f"strikes: {ppems}")
        hhea = font["hhea"]
        self.expect((hhea.ascent, hhea.descent) == (ASCENT, DESCENT), f"hhea: {hhea.ascent} {hhea.descent}")

    def sequences(self):
        """GSUB in the new font gives the glyph that morx gives in the source font."""
        source, built = Shaper(self.src / "AppleColorEmoji-Linux.ttf"), Shaper(self.path)
        wrong = []
        for points, _, name in sequences(self.src / "emoji-test.txt"):
            want = source.emoji(points)
            if want is None or built.emoji(points) != want:
                wrong.append(f"{name}: {built.glyphs(points)}, want {want}")
        self.expect(not wrong, f"{len(wrong)} sequences shape wrong, e.g.\n  " + "\n  ".join(wrong[:10]))

    def coverage(self):
        """All characters and sequences of the stock fonts show as one emoji.

        Private-use characters do not count: Noto maps old Google codes for
        carrier emoji there.
        """
        cmap = set(self.font.getBestCmap() or {}) | PRIVATE_USE
        built = Shaper(self.path)
        for name in ("NotoColorEmoji.ttf", "NotoColorEmojiFlags.ttf"):
            stock_path = self.src / name
            stock = set(TTFont(stock_path).getBestCmap() or {})
            missing = sorted(hex(c) for c in stock - cmap)
            self.expect(not missing, f"{name}: {len(missing)} characters missing: {missing[:20]}")
            shaper = Shaper(stock_path)
            lost = [
                n
                for points, _, n in sequences(self.src / "emoji-test.txt")
                if shaper.emoji(points) and not built.emoji(points)
            ]
            self.expect(not lost, f"{name}: {len(lost)} emoji lost: {lost[:10]}")

    def samples(self):
        built = Shaper(self.path)
        for text, glyph in SAMPLES.items():
            got = built.emoji(tuple(map(ord, text)))
            ok = got is not None and glyph in (None, got)
            self.expect(ok, f"{text!r}: {built.glyphs(tuple(map(ord, text)))}")

    def expect(self, ok: bool, message: str):
        self.count += 1
        if not ok:
            self.failures.append("FAIL " + message)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
