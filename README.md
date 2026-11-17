# Apple Emoji

A KernelSU module for the Nothing Phone (4a) on LineageOS 23.2. It replaces the
system emoji font (`NotoColorEmoji.ttf`) with Apple Color Emoji from macOS 26
(Unicode 17.0).

Apple Color Emoji belongs to Apple Inc. and has no license for use outside
Apple products. Build the module for your own phone, and do not publish the zip.

## Install

1. Build the zip (see Build).
2. Disable other emoji modules.
3. Install the zip in the KernelSU manager and reboot.

Apps that unmount modules do not get the font. In the KernelSU manager, turn
off "Umount modules by default" in Settings, and turn on "Umount modules" only
in the App Profile of apps that must not see root. Then force-stop the apps
that are open. The log is `/data/local/tmp/apple-emoji.log`.

## How it works

- `post-fs-data.sh` bind-mounts `AppleColorEmoji.ttf` over each target in
  `emoji.list`. The font XMLs do not change.
- `NotoColorEmojiFlags.ttf` stays. For valid flags, the Apple font wins,
  because it comes first in the fallback order. Pairs of regional indicators
  that are not a flag still show the Noto "unknown flag" glyph.
- If a boot does not complete, the next boot mounts nothing and the module
  disables itself. `service.sh` clears the guard after the boot completes. To
  use the module again, enable it in the KernelSU manager.

## The font

The source is the Linux build of
[apple-emoji-ttf](https://github.com/samuelngs/apple-emoji-ttf): PNG bitmaps in
CBDT, which Android reads. That font makes ZWJ sequences, skin tones and flags
with the AAT `morx` table. `build/build.py` changes it for Android:

- It shapes each sequence of Unicode's `emoji-test.txt` with `morx` (HarfBuzz),
  and writes the results as GSUB `ccmp` ligatures, as Noto Color Emoji does.
- It keeps only the 96 ppem strike, the largest one. Android scales it.
- It removes the AAT tables (`morx`, `feat`, `trak`, ...).
- It adds the emoji variation sequences (U+FE0F) in a cmap format 14
  subtable, as Noto has them. `Paint.hasGlyph()` needs them, for example for
  U+2764 U+FE0F.
- It sets the ascent and descent of `NotoColorEmojiFlags.ttf`, so that lines
  with emoji are not taller than before.

`build/verify.py` checks the font with the OpenType Sanitizer, checks that each
sequence of `emoji-test.txt` gives the same glyph as `morx`, and checks that
each character, sequence and variation sequence of the stock emoji fonts is
in the new font.

## Known limits

- Apps that draw emoji from their own font or images do not change. Examples
  are WhatsApp, Telegram (unless "Use system emoji" is on), Facebook,
  Messenger, and apps that bundle the `emoji2-bundled` font.
- On a ROM with Google Play services, an updated emoji font in `/data/fonts`
  replaces the system font, and so hides the mount. LineageOS without GApps
  does not have one.
- Apple emoji are 1 em wide; Noto emoji are 1.25 em wide. Text with emoji is a
  little narrower.
- The largest bitmap is 96 px. Very large emoji are a little soft.

## Build

Needs `uv` and `curl`.

```sh
./build.sh
```

This writes `../zips/apple-emoji-<version>.zip` (set `OUT` for another
directory). The download is about 110 MiB, and the zip about 36 MiB.
