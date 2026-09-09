# UI themes

Two complete chrome sets (badges + paper + 令牌 tablets):

| Theme | Path | Look |
|---|---|---|
| **silver** (default) | `silver/` | Greyscale silver badges + white/silver paper + **silver-metal 令牌** with coloured ribbons |
| **bronze** | `bronze/` | Aged bronze badges + golden paper + **ebony-wood 令牌** with coloured ribbons (original tablets) |

令牌 files per theme:

- `handi-lingpai.png` — crimson ribbon, 漢地十八省 (**style + glyph-scale reference**, 575×1510 silver)
- `zhongguo-lingpai.png` — yellow ribbon, 中國 (same canvas width + same glyph scale; shorter height)

**Generating / regenerating tablets:** follow [`.cursor/rules/lingpai-tablets.mdc`](../../.cursor/rules/lingpai-tablets.mdc). Critical: UI sizes by width, so both PNGs must be **575px wide** with characters ~**330–350px** wide — never enlarge glyphs to fill a shorter tablet.

Ebony originals are also archived as `public/intro/handi-lingpai-ebony.png` and `zhongguo-lingpai-ebony.png`.

Switch theme in [`src/config.ts`](../../src/config.ts) (`UI_THEME`). No end-user toggle.
