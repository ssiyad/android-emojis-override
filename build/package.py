"""Make the KernelSU module zip.

Usage: package.py MODULE_DIR FONT OUT_ZIP

Takes the scripts from MODULE_DIR and the font, which goes to the root of the
module as AppleColorEmoji.ttf.
"""

import sys
import zipfile
from pathlib import Path

NOTICE = """\
Apple Color Emoji: Copyright Apple Inc. Apple does not license this font for
use outside its products. Use the module for personal use only, and do not
redistribute it.
Converted from the Linux build of https://github.com/samuelngs/apple-emoji-ttf.
"""


def main(module: Path, font: Path, out: Path):
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(p for p in module.rglob("*") if p.is_file()):
            zf.write(path, path.relative_to(module).as_posix())
        # The PNGs in the font do not compress further.
        zf.write(font, "AppleColorEmoji.ttf", compress_type=zipfile.ZIP_STORED)
        zf.writestr("NOTICE.txt", NOTICE)
    print(f"{out}: {out.stat().st_size // 2**20} MiB")


if __name__ == "__main__":
    main(*(Path(arg) for arg in sys.argv[1:4]))
