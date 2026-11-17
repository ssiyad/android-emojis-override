# pyright: reportAttributeAccessIssue=false
# fontTools tables are dynamic; pyright cannot see their attributes.
"""Make an Android emoji font from the Linux build of apple-emoji-ttf.

Usage: build.py SRC_FONT EMOJI_TEST OUT_FONT

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
  - adds Windows name records.
"""

import sys
from pathlib import Path

from fontTools.otlLib.builder import buildLigatureSubstSubtable, buildLookup
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables as ot

sys.path.insert(0, str(Path(__file__).resolve().parent))  # run with python -I
from emoji import Shaper, sequences

STRIKE_PPEM = 96
# NotoColorEmojiFlags.ttf, which has the same units per em (2048).
ASCENT, DESCENT = 1900, -500
AAT_TABLES = ["morx", "feat", "trak", "bgcl", "meta", "DSIG"]
TAGS = range(0xE0020, 0xE0080)
FAMILY = "Apple Color Emoji"


def main(src: Path, emoji_test: Path, out: Path):
    font = TTFont(src)
    ligatures = aat_ligatures(src, font, emoji_test)
    keep_strike(font, STRIKE_PPEM)
    for tag in AAT_TABLES:
        if tag in font:
            del font[tag]
    add_gsub(font, ligatures)
    add_tags(font)
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


def set_metrics(font: TTFont):
    hhea, os2 = font["hhea"], font["OS/2"]
    hhea.ascent, hhea.descent, hhea.lineGap = ASCENT, DESCENT, 0
    os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap = ASCENT, DESCENT, 0
    os2.usWinAscent, os2.usWinDescent = ASCENT, -DESCENT


def add_names(font: TTFont):
    """Add Windows names. The source has Macintosh names only."""
    name = font["name"]
    mac = {record.nameID: str(record) for record in name.names if record.platformID == 1}
    for name_id in (0, 3, 5):
        if name_id in mac:
            name.setName(mac[name_id], name_id, 3, 1, 0x409)
    name.setName(FAMILY, 1, 3, 1, 0x409)
    name.setName("Regular", 2, 3, 1, 0x409)
    name.setName(FAMILY, 4, 3, 1, 0x409)
    name.setName("AppleColorEmoji", 6, 3, 1, 0x409)


if __name__ == "__main__":
    main(*(Path(arg) for arg in sys.argv[1:4]))
