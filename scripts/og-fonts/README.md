Fonts bundled for `scripts/og.mjs` (inlined as data: URLs, so OG rendering needs no network or system fonts).

- `Inter-subset.ttf`: Inter variable font (opsz, wght), subset to Latin, Latin Extended, punctuation, arrows, math and the ✓ ⚠ symbols. Copyright 2016 The Inter Project Authors. SIL Open Font License 1.1: see `OFL-Inter.txt`.
- `NotoColorEmoji-subset.ttf`: Noto Color Emoji, subset to the category icons (📈 ⚡ 🪙 🧾 💳 🏦 🔎 🧪 🌍). Copyright 2013 Google LLC. SIL Open Font License 1.1: see `OFL-NotoColorEmoji.txt`.

The cards are English-only. If a new category icon or a non-Latin tool name is added, re-subset with fontTools `pyftsubset` and add the new codepoints. Until then, Chrome falls back to system fonts for any glyph that's missing.

Both subsets were made with `pyftsubset … --name-IDs='*' --name-languages='*'`, so the copyright, licence description and licence URL (name IDs 0, 13 and 14) are kept in the font files. Neither font declares a Reserved Font Name.
