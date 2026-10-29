Fonts bundled for `scripts/og.mjs` (inlined as data: URLs, so OG rendering needs no network or system fonts).

- `Inter-subset.ttf`: Inter variable font (opsz, wght), subset to Latin, Latin Extended, punctuation, arrows, math and the ✓ ⚠ symbols. Inter © The Inter Project Authors, SIL Open Font License 1.1.
- `NotoColorEmoji-subset.ttf`: Noto Color Emoji, subset to the category icons (📈 ⚡ 🪙 🧾 💳 🏦 🔎 🧪 🌍). © Google, SIL Open Font License 1.1.

The cards are English-only. If a new category icon or a non-Latin tool name is added, re-subset with fontTools `pyftsubset` and add the new codepoints. Until then, Chrome falls back to system fonts for any glyph that's missing.
