# ICT 2022 — Per-deck study notes

Concise engineering notes (concepts/methods) from each deck of the 2022 ICT Mentorship, captured so
we can resume without re-reading. Source = the user's purchased material; these are summaries for
implementation, not reproductions. Status of all 68 decks: see `LEARNING_TRACKER.md`. Synthesis:
`ICT_2022_MENTAL_MAP.html`.

---

## Case Studies / Rules

### Entry Model
The model in 5 steps (same for buy/sell, mirrored):
1. **Time of day** (killzone) → 2. **Narrative set** (HTF bias/draw) → 3. **Liquidity swept** (sellside
for buys / buyside for sells) → 4. **Displacement / MSS** (energetic move leaving an FVG) →
5. **Entry in the FVG, in discount (buys) / premium (sells)**.
*We have all five mechanically, but under-implement #2 (narrative) and #5 (premium/discount).*

### Low Probability Conditions (when NOT to trade)
- **NFP week:** Wednesday NY, Thursday, Friday are low probability.
- **After an FOMC whipsaw:** London and the AM session are low probability.
- **Trading against the daily trend** is low probability.
*→ counter-trend filter; NFP-week + post-FOMC day filters. (Distinct from "news as catalyst": you
WANT news days, but avoid the chop-after days.)*

### Power Of 3 / AMD
Daily candle = **Accumulation → Manipulation → Distribution**. Anchored to the **Midnight NY Open
(MNO)**. Manipulation (Judas) ≈ around 08:30; Distribution ≈ NY session (~13:30). Premium array above
MNO, discount below. Sessions map onto it (London open / NY open / London close). Fractal across TFs.

### Premium / Discount
"Smart money buys in discount, sells in premium; retail does the opposite." Use on the **dealing range**
(swing high→low, equilibrium 50%), on market structure, and on 1m MSS. **Entries:** discount for buys,
premium for sells. **Targets:** opposite side — sell premium → target FVG/liquidity/OB in discount, and
vice-versa. Entry after a **1m MSS** (confirmation).

### Mean Threshold
= **50% of an order-block body**. If price **body-closes through** the mean threshold, the OB is failing
(higher chance the whole OB fails). "Holds" if it never body-closes beyond MT. → entry filter /
invalidation level for OB-based trades.

### Judas Swing / Protraction Phases
The **Judas swing** = the fake move (protraction) before the real move; the manipulation that grabs
liquidity. **Fractal** — every session, daily/weekly/monthly candles, and the 09:30 equities open.
Also happens at news. **Normal vs Delayed protraction** = the manipulation comes at the expected time
or later (London Normal vs London Delayed).

### SMT
"Use SMT with a **correlated pair**; it is to **confirm** an idea, **not a standalone indicator**." SMT
between **ES and NQ**: compare swing **lows** when bullish, swing **highs** when bearish.
*→ our Phase-C SMT was wrong twice: standalone + stock↔own-index. Fix to ES↔NQ / SPY↔QQQ confirmation.*

### News Catalyst
"**News will be used as an alibi for manipulation.**" The manipulation (Judas) happens around the news
time (e.g. 08:30); use it like a Judas swing. → news days are *setup* days, not avoid days.

---

## Episodes

### Ep 5 — Intraday Order Flow & Understanding The Daily Range
- **12:00–13:00 NY = no-trade** (lunch). Afternoon usually follows the trend; "19:30 starts algo."
- **Displacement is the key concept:** when price trades above an old high, look for an *obvious*
  displacement, then go find the FVG.
- **3-drives pattern** for liquidity raids (doesn't need to take out a high/low to look for entries).
- Swing high = a candle with a lower high on each side (3-candle pattern); swing low mirrored.
- Continuation → measured move; consolidation → slow & steady.

### Ep 10 — Implementing Economic Calendar Events With The Open
- **Power of 3 / Opening range:** Accumulation = opening range; Manipulation = first move above/below
  opening price (Judas); Distribution = from the day's low/high to the close.
- **Opening range** (open → manipulation extreme, mirrored to the other side) = best place for entries.
- **Close-proximity entry** = enter near the daily open price.
- **Multi-TF FVG drill:** if there's an FVG on the 3m, don't drop to 2m/1m; only drop down if the
  higher TF has none. (Use the highest-TF FVG present.)
- **Two FVGs?** take the lower one when bearish, but the stop must account for the higher FVG.
- **Breaker + FVG = big confluence** (price taps both and takes off); ideal in major/intermediate trends.

### Ep 16 — Multiple Setups Inside Trading Session  (frequency model)
- **Morning session = 08:30 to noon.** Index futures opening price = **midnight** AND the **08:30** candle.
- If bearish, you want price running **above** the opening price as manipulation (Judas above MNO/830).
- **Max ~4 trades/day: 2 AM, 2 PM.** End of week likely a retracement (Fri PM aims for BSL/premium).
- **Old highs flip to a discount array** once traded through → can act as **support**; swept SSL → clear
  BSL target → old highs act as support; especially good combined with an FVG.
- PM session has its own buyside liquidity pool. Fib targeting only valid with the full narrative.

### Ep 21 — Intermarket Relationships & Intermarket Analysis
- **DXY on 1H = bias tool.** When every market declines, DXY (safe haven) rises = **risk-off**. DXY and
  ES are correlated (inversely for risk). → DXY direction = risk-on/off + bias.
- Power-of-3 / MNO / 08:30: if bearish and price does **not** fake-rally above MNO/830, we're strongly
  bearish → look at the draw and get involved ("sneaky little entries").
- Uses NY Midnight + 08:30 opening prices; drills 15m → 4m → 3m → 2m → 1m for entries.

### Ep 40 — Keys To Daily Bias
- **Daily bias method:** "every-day bias is unrealistic." Determine the likely **weekly expansion** (where
  the weekly will *reach for*, not where it closes) → that's the strongest bias. Look for obvious
  liquidity in that direction; identify imbalances top-down; focus on **high/medium calendar dates**;
  look for directional price runs in killzones intraday.
- **Sweep of a daily high + 3-bar pattern → expect lower** (confirmed when the 4th candle trades lower);
  mirror for sweeping a low.
- **10:00–11:00 = London Close** (reversal toward the opposite end of the daily range); **10:00–12:00**
  on a news day. **ICT trades only high/medium impact days.** Ignore the 2 big news wicks.
- Likes to use **FVGs fully in premium/discount**. Risk-on: USD up + others up; risk-off: USD up + others
  down. Uses **CAD news for SP500**. Watches **SMT between correlated pairs** at news time → take the
  stronger (non-confirming) pair.

---

## Consolidated notes PDF
`ICT 2022 Mentorship Notes.pdf` = just a Notion index/TOC (episodes 1–41 + topical study + case
studies). No extra content; the substance is in the individual decks above.
