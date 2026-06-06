# ict_2022 — research breadcrumbs

Study notes for redesigning `ict_2022` from the **2022 ICT Mentorship** (the user's purchased decks).
We deliberately read **all 68 decks** before redesigning the strategy (no half-implementation). ✅ Read-through complete.

| File | What it is |
|---|---|
| `ICT_2022_MENTAL_MAP.html` | The synthesized model: 4 nested layers (time → narrative → setup → arrays), our-code-vs-real-model gap, and the Tier 1→3 idea backlog. Open in a browser. |
| `DECK_NOTES.md` | Per-deck engineering notes (concepts/methods). Append as decks are read. |
| `LEARNING_TRACKER.md` | Checklist of all 68 decks (**68/68 read ✅**) + the 12 highest-value codeable rules extracted across them. |

**Source decks** (read-only, not committed): `~/Desktop/ict-2022/2022 ICT Mentorship @arjoio/`

## Where we are
- `ict_2022` A–D scaffolding is complete (futures cost, breadth/portfolio runner, crypto 24/7, SMT,
  events/regime — all toggles); **edge sits at breakeven**. Diagnosis from the decks: we built the LTF
  **trigger** (sweep→MSS→FVG) but skipped the **daily narrative** (MNO anchor, draw-on-liquidity bias,
  premium/discount, news-as-catalyst) that is supposed to gate it.
- **✅ All 68 decks read** (notes in `DECK_NOTES.md`, tracker ticked). The decks converge on one thesis and
  ~12 precise, codeable rules — see the shortlist at the bottom of `LEARNING_TRACKER.md`.
- **The single biggest finding (Ep 39):** the edge is **TIME × PRICE** — a PD array (FVG/OB/old level) only
  matters when reached **at a key macro time** (00:00 MNO, 08:30, 09:30, 10:00, 13:30). Our mechanical model
  checked price arrays *continuously with no time gate* — that is why it was noise.
- **The missing bias engine (Ep 25 Daily Rebalance Theory):** on a major daily/weekly high/low taken, look at
  the **last 3 days** — FVG present ⇒ draw rebalances it; none ⇒ use PDH/PDL — plus purge-&-revert and
  liquidity-sequence validation. This is the draw-on-liquidity layer we never built.
- **Next:** deepen `ICT_2022_MENTAL_MAP.html` with these rules → redesign (Tier 1: news-catalyst +
  premium/discount + draw-based bias + macro-time gate; Tier 2: MNO/Power-of-3 narrative engine; Tier 3:
  FVG+OB+OTE confluence) → then the definitive Phase E validation on the reserved 2025/26 holdout.
- Highest-confidence lead (decks **and** our own backtest agree): **news is a catalyst, not a filter.**
