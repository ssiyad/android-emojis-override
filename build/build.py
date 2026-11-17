# pyright: reportAttributeAccessIssue=false
# fontTools tables are dynamic; pyright cannot see their attributes.
"""Make an Android emoji font from the Linux build of apple-emoji-ttf.

Usage: build.py SRC_DIR OUT_FONT

The source font is CBDT (color PNG bitmaps), which Android reads, but it forms
ZWJ sequences, skin tones and flags with the AAT morx table. Android's emoji
fonts use GSUB. The build:
  - shapes every sequence of emoji-test.txt with morx, and writes the result
    as GSUB ccmp ligatures,
  - keeps only the largest bitmap strike (96 ppem), as Android scales one strike,
  - removes the AAT tables,
  - sets the vertical metrics of NotoColorEmojiFlags, so that lines with emoji
    are not taller than with the stock font,
  - maps all tag characters (U+E0020-E007F) to an empty glyph, as Noto does,
  - adds a cmap format 14 subtable with the emoji variation sequences (FE0F).
    Without it, Paint.hasGlyph() is false for text such as U+2764 U+FE0F,
  - replaces the Windows name records.
"""

import sys
from pathlib import Path

from fontTools.otlLib.builder import buildLigatureSubstSubtable, buildLookup
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables as ot
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable

sys.path.insert(0, str(Path(__file__).resolve().parent))  # run with python -I
from emoji import Shaper, emoji_style_bases, sequences

STRIKE_PPEM = 96
# NotoColorEmojiFlags.ttf, which has the same units per em (2048).
ASCENT, DESCENT = 1900, -500
AAT_TABLES = ["morx", "feat", "trak", "bgcl", "meta", "DSIG"]
TAGS = range(0xE0020, 0xE0080)
FAMILY = "Apple Color Emoji"


def main(src_dir: Path, out: Path):
    src = src_dir / "AppleColorEmoji-Linux.ttf"
    font = TTFont(src)
    ligatures = aat_ligatures(src, font, src_dir / "emoji-test.txt")
    keep_strike(font, STRIKE_PPEM)
    for tag in AAT_TABLES:
        if tag in font:
            del font[tag]
    add_gsub(font, ligatures)
    add_tags(font)
    add_variations(font, emoji_style_bases(src_dir / "emoji-variation-sequences.txt"))
    set_metrics(font)
    add_names(font)
    out.parent.mkdir(parents=True, exist_ok=True)
    font.save(out)
    print(f"{out.name}: {len(ligatures)} ligatures, {out.stat().st_size // 2**20} MiB")


def aat_ligatures(src: Path, font: TTFont, emoji_test: Path) -> dict:
    """Map the glyphs of each multi-character sequence to the glyph that morx makes."""
    cmap = font.getBestCmap() or {}
    shaper = Shaper(src)
    ligatures = {}
    for points, _, name in sequences(emoji_test):
        if len(points) < 2:
            continue
        missing = [hex(p) for p in points if p not in cmap]
        target = shaper.emoji(points)
        if missing or target is None:
            sys.exit(f"{name}: morx gives {shaper.glyphs(points)}, unmapped {missing}")
        ligatures[tuple(cmap[p] for p in points)] = target
    return ligatures


def keep_strike(font: TTFont, ppem: int):
    """Remove all bitmap strikes except the one with this ppem."""
    cblc, cbdt = font["CBLC"], font["CBDT"]
    pairs = [
        (strike, data)
        for strike, data in zip(cblc.strikes, cbdt.strikeData)
        if strike.bitmapSizeTable.ppemX == ppem
    ]
    if not pairs:
        sys.exit(f"no {ppem} ppem strike")
    cblc.strikes = [strike for strike, _ in pairs]
    cbdt.strikeData = [data for _, data in pairs]
    size = cblc.strikes[0].bitmapSizeTable
    for line in (size.hori, size.vert):
        line.ascender = round(ppem * ASCENT / font["head"].unitsPerEm)
        line.descender = round(ppem * DESCENT / font["head"].unitsPerEm)


def add_gsub(font: TTFont, ligatures: dict):
    """Add the ligatures as one ccmp lookup, for the DFLT and latn scripts."""
    subtable = buildLigatureSubstSubtable(ligatures)
    lookup = buildLookup([subtable])

    gsub = ot.GSUB()
    gsub.Version = 0x00010000
    gsub.LookupList = ot.LookupList()
    gsub.LookupList.Lookup = [lookup]
    gsub.LookupList.LookupCount = 1
    feature = ot.Feature()
    feature.FeatureParams = None
    feature.LookupListIndex = [0]
    feature.LookupCount = 1
    record = ot.FeatureRecord()
    record.FeatureTag = "ccmp"
    record.Feature = feature
    gsub.FeatureList = ot.FeatureList()
    gsub.FeatureList.FeatureRecord = [record]
    gsub.FeatureList.FeatureCount = 1
    gsub.ScriptList = ot.ScriptList()
    gsub.ScriptList.ScriptRecord = [_script_record(tag) for tag in ("DFLT", "latn")]
    gsub.ScriptList.ScriptCount = 2
    table = newTable("GSUB")
    table.table = gsub
    font["GSUB"] = table


def _script_record(tag: str) -> ot.ScriptRecord:
    langsys = ot.LangSys()
    langsys.LookupOrder = None
    langsys.ReqFeatureIndex = 0xFFFF
    langsys.FeatureIndex = [0]
    langsys.FeatureCount = 1
    script = ot.Script()
    script.DefaultLangSys = langsys
    script.LangSysRecord = []
    script.LangSysCount = 0
    record = ot.ScriptRecord()
    record.ScriptTag = tag
    record.Script = script
    return record


def add_tags(font: TTFont):
    """Map the tag characters that the font does not have to the glyph of TAG LATIN SMALL G.

    The glyph is empty. With all tags in the cmap, Android keeps a tag sequence
    in this font, also for subdivision flags that have no glyph.
    """
    cmap = font.getBestCmap() or {}
    empty = cmap[0xE0067]
    for table in font["cmap"].tables:
        if table.format == 12:
            for point in TAGS:
                table.cmap.setdefault(point, empty)


def add_variations(font: TTFont, bases: set):
    """Add base + FE0F as default variation sequences: the base glyph is the emoji."""
    cmap = font.getBestCmap() or {}
    missing = sorted(hex(b) for b in bases - set(cmap))
    if missing:
        sys.exit(f"emoji variation bases without a glyph: {missing}")
    table = CmapSubtable.newSubtable(14)
    table.platformID, table.platEncID, table.language = 0, 5, 0xFF
    table.cmap = {}
    table.uvsDict = {0xFE0F: [(base, None) for base in sorted(bases)]}
    font["cmap"].tables.append(table)


def set_metrics(font: TTFont):
    hhea, os2 = font["hhea"], font["OS/2"]
    hhea.ascent, hhea.descent, hhea.lineGap = ASCENT, DESCENT, 0
    os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap = ASCENT, DESCENT, 0
    os2.usWinAscent, os2.usWinDescent = ASCENT, -DESCENT


def add_names(font: TTFont):
    """Replace the Windows names with English ones. The source has only localized style names."""
    name = font["name"]
    name.names = [record for record in name.names if record.platformID != 3]
    mac = {record.nameID: str(record) for record in name.names if record.platformID == 1}
    for name_id in (0, 3, 5):
        if name_id in mac:
            name.setName(mac[name_id], name_id, 3, 1, 0x409)
    name.setName(FAMILY, 1, 3, 1, 0x409)
    name.setName("Regular", 2, 3, 1, 0x409)
    name.setName(FAMILY, 4, 3, 1, 0x409)
    name.setName("AppleColorEmoji", 6, 3, 1, 0x409)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
