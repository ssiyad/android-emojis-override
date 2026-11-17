#!/usr/bin/env bash
# Download the sources into build/cache and check their hashes.
#   - The Linux build of Apple Color Emoji (CBDT) from samuelngs/apple-emoji-ttf.
#   - emoji-test.txt of Unicode 17.0: the sequences to make ligatures for.
#   - emoji-variation-sequences.txt of Unicode 17.0: the characters that take
#     U+FE0F (emoji style).
#   - The stock emoji fonts of LineageOS 23.2, from the commit that it builds.
#     verify.py checks that the new font covers all of their characters. They
#     do not go into the module.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
cache=$here/cache
src=$cache/src
apple_tag=macos-26-20260722-484daf4e
unicode_ver=17.0.0
noto=https://android.googlesource.com/platform/external/noto-fonts/+/149d2ec6b8077497bcc3affa8c90112bada8baae/emoji-compat/font

main() {
	mkdir -p "$cache/dl" "$src"
	fetch "https://github.com/samuelngs/apple-emoji-ttf/releases/download/$apple_tag/AppleColorEmoji-Linux.ttf" \
		AppleColorEmoji-Linux.ttf e37c7af6265ac4a0af6d57bc65e86109a776d9966e8343334557f63da482516f
	fetch "https://www.unicode.org/Public/$unicode_ver/emoji/emoji-test.txt" \
		emoji-test.txt 1d8a944f88d7952f7ef7c5167fef3c67995bcae24543949710231b03a201acda
	fetch "https://www.unicode.org/Public/$unicode_ver/ucd/emoji/emoji-variation-sequences.txt" \
		emoji-variation-sequences.txt bb3d09ef03f206012c7532dd52dc0a21c9efddba0135ea4cf0d9201b8b9bba7e
	# Gitiles serves raw files as base64.
	fetch "$noto/2.047/Noto-COLRv1-noflags.ttf?format=TEXT" \
		NotoColorEmoji.ttf 292f799100f358811337bc3c68da31e6b0c422e9ce8db27d6d52b6acbc5633f3 base64
	fetch "$noto/2.048/NotoColorEmoji-flagsonly.ttf?format=TEXT" \
		NotoColorEmojiFlags.ttf 509d49e189802591da8db061038409c91811916198ba6b4ba7ef360ccb166f99 base64
	for name in AppleColorEmoji-Linux.ttf emoji-test.txt emoji-variation-sequences.txt \
		NotoColorEmoji.ttf NotoColorEmojiFlags.ttf; do
		cp "$cache/dl/$name" "$src/$name"
	done
}

# fetch URL NAME SHA256 [base64]: download once, then always check the hash.
fetch() {
	local out="$cache/dl/$2"
	if [ ! -f "$out" ]; then
		curl -sSLf --retry 3 -o "$out.part" "$1"
		if [ "${4:-}" = base64 ]; then
			base64 -d "$out.part" >"$out.dec"
			mv "$out.dec" "$out.part"
		fi
		mv "$out.part" "$out"
	fi
	echo "$3  $out" | sha256sum -c --quiet
}

main "$@"
