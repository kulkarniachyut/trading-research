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

### Market structure
- Labels: **LTH/ITH/STH** and **LTL/ITL/STL** (long/intermediate/short-term highs & lows).
- **Rule:** "Every time price rebalances an FVG, that swing is an ITH/ITL." An **ITL** typically has a
  **higher STL** on each side (an ITH a lower STH on each side) — i.e. structure is defined by which
  swings get violated, anchored to FVG rebalances. → gives a concrete, causal way to label structure:
  fractal swing points where the middle is the extreme, promoted to ITH/ITL when an FVG is rebalanced.
- **Use MS *within a HTF premise*** (don't read structure in isolation — gate it by the higher-TF bias).
- **Timeframe framing (top-down, 3 TFs):** Day-trades/scalps = **1h long-term, 15m intermediate, 5m
  short-term**. (Position=M/W/D; Swing=D/4h/1h; Short-term=4h/1h/15m.) → our 5m engine should read 15m
  for intermediate structure and 1h for the long-term premise.

### Swing Low and Swing High
- **3-candle pattern**: swing high = candle with a lower high on each side; swing low mirrored.
- **Confirmation:** a swing is confirmed (and a new trend "started") only once price **trades beyond
  the 3rd candle** — for a swing high, once we trade *lower than the 3rd candle*; mirror for a low.
  → this is the causal trigger for "structure formed"; pairs with the daily-bias 3-bar rule in Ep 40.
- After a **daily liquidity sweep** that prints a swing high/low, ICT starts looking to trade *with the
  new trend.*

### Dealing ranges
- "Very powerful, tend to get **respected a lot**." A dealing range = swing-high → swing-low span;
  equilibrium = 50%. (Substance is in Premium/Discount + the linked explainer.) → use the dealing range
  as the premium/discount frame for entries & targets.

### Displacement / MSS
- **Two types of displacement: a *breaker* pattern and a *swing failure*** (both = "Institutional Swing
  Points").
- **MSS definition** (the precise one): the move beyond the old high/low must be **quick**, with
  *displacement* (not a small candle, **not a wick** — confirmed **after a candle close**). Bearish MSS =
  price rallies above an old high, then quickly shifts lower; bullish = decline below an old low then
  shifts higher. The displacement leaves the **FVG** behind. → tightens our `min_disp_strength`: require a
  body-close break + an FVG in the displacement leg, not just a fast move.

### Fair Value Gap
- 3-candle imbalance; **confirmed once the 3rd candle closes** (causal — no FVG until close).
- **Bullish FVG** forms *below* price after a run into **sellside** liquidity (single/multiple lows);
  **bearish FVG** *above* after a run into **buyside** liquidity. → FVG should be preceded by a liquidity
  raid; an FVG without a prior sweep is lower quality.

### Orderblock
- "**A change in the state of delivery.**" (Deck defers detail to ICT Core Content month 4.) Pairs with
  Mean Threshold (50% of OB body) as the invalidation level. → OB = last down-candle before an up-move
  (bullish) / last up-candle before a down-move (bearish); entry on return, invalid on MT body-close.

### Old high + FVG
- **Combine an old high with an FVG → the old high acts as *support*** (invert for old low + FVG = resistance).
  "In other words: a **breaker or mitigation block + an FVG**." → highest-confluence entry: price returns
  to a level that is *both* a swept-then-flipped old high/low *and* an FVG. (Already in Ep 16 notes; this
  is the dedicated deck — promote to a confluence flag.)

### 3 Drives Pattern
- **Three pushes** into a level = "enticing uninformed traders," **building up liquidity** by luring
  buyers (bullish version) / sellers (bearish) before the reversal. → a liquidity-build pattern that
  *precedes* a sweep+reversal; not an entry itself but a context flag that a raid is being set up.

### Super Bullish / Heavy Discount  *(quantifiable conviction gauge — high value)*
Read price's position vs **MNO (Midnight NY Open)** and the **08:30 open** at the start of the session:
- **Super bullish:** expecting an up day and there's **barely any price action below MNO/830** → strong;
  (once already above MNO, use the **830 open** as the reference). Mirror = super bearish.
- **Heavy discount:** expecting an up day but at 08:30 price is **still below both MNO and the 830 open**
  → we're in *heavy discount* = a high-value long location (deep discount before the expansion).
- → **Implementable signal:** `price_vs_mno_830(now)` → {super_bullish, heavy_discount, neutral, …};
  gates/size-up longs in discount, shorts in premium. Directly operationalizes premium/discount with the
  daily anchors instead of a swing-range %.

### Risk Management / Stop Management  *(concrete trailing rule)*
- **Trail rule:** when price reaches **50%** of the expected target range, trail stop to **25%**; at
  **75%** of the range, trail to **breakeven**. → a deterministic, backtestable stop-management policy
  (range-relative, not ATR) for the simulator's trade management.

### Pyramiding
- **Add on continuation with *decreasing* risk:** 1st entry biggest (e.g. 1%), 2nd less (0.5%), 3rd even
  less (0.25%). Risk the most on the **initial** entry. → optional position-scaling layer; out of scope
  until the base single-entry edge is proven, but note for the risk layer.

### Psychology
- Think in **probabilities, not absolutes**; "don't assume you know where price will go." Trade a
  written, mechanical plan even through losing streaks. → reinforces the truth-machine stance: the model
  must be rules-based and evaluated on expectancy, not conviction.

### Model Examples (Buy / Sell)
- **Buy example (concrete):** at **PM-session start**, price sweeps **sellside liquidity** (an old low),
  reverses, and the entry is taken at **"Equilibrium + FVG"** — i.e. the FVG that sits at/below the 50%
  equilibrium of the dealing range (**in discount**). Confirms: entry FVG must be in **discount for buys**
  / premium for sells, *and* the PM session is a valid second setup window (not just the AM).
- Sell example = the +7% MMSM (Market-Maker Sell Model) YouTube breakdown (28 Dec) — external video, no
  static content. (MMSM = the mirror of the buy model: buyside sweep → premium FVG → target discount.)
- `0. Case Studies / Rules.pdf` = the folder index (TOC only).

**✅ Case Studies / Rules folder COMPLETE (26/26).**

---

## Episodes

### Ep 1 — Introduction
- Title slide only (link to video). No content.

### Ep 2 — Elements To A Trade Setup  *(the core mechanical recipe)*
- **Price targets FVGs and liquidity** — those are the only two things price reaches for.
- **Anticipate the Judas / stop-hunt:** when *lower* prices are expected, first expect a raid on **buy
  stops / short-term highs** (fake up); mirror for higher prices. The first move is the trap.
- **TF for imbalances (indices):** 1m/2m/3m are best for finding the FVG; **5m still leaves room** for
  imbalances underneath → drop a TF to find the entry FVG once the 5m shows the setup.
- **Trade mechanics (explicit):** *Enter in the FVG · Stop at the next candle above (below) the FVG ·
  Exit where the liquidity is.* → exact entry/stop/target definition for the simulator.
- **Premium/discount via 50%:** above 50% of the range = **expensive** (look short); below = **cheap**
  (look long). Use the dealing-range fib to decide direction + anticipate the algo's target.
- **08:30–11:00 EST is the sweet spot** ICT focuses on (the AM killzone).

### Ep 3 — Internal Range Liquidity & Market Structure Shifts  *(highest-value gating rule)*
- **★ MSS only when price takes out liquidity.** A *shift* (vs a plain break) requires a **prior liquidity
  sweep** + displacement. → our MSS detector must require a sweep immediately before the displacement leg;
  a break without a sweep is an MSB, not a tradeable MSS.
- **Order block precision:** OB = "a change in the state of delivery" — a *series of candles into* buyside/
  sellside liquidity. **NOT every down-close candle is a bullish OB**, nor every up-close a bearish OB
  (only the one at the liquidity raid that precedes displacement counts).
- **Two-FVG handling:** enter on the **highest** FVG but expect a stab into the lower; *or* wait for the
  lower FVG to be tapped, print a tail, trade back into the higher FVG, then enter.
- **★ Session levels to mark (sweep candidates):** London **02:00–05:00**, NY **07:00–10:00**, Asia
  **19:00–21:00**, plus the intraday high/low **right before 09:30** equities open. Market will likely
  sweep above/below these → BOS/MSS setups. → compute these session extremes as the liquidity pools the
  model hunts.
- **Best window 08:30–11:00**; for the **PM session wait for 13:30**. "Look for the low-hanging fruit."

### Ep 4 — Example of Episode 3
- **At 08:30 look for old highs/lows to be swept, then wait for the model** (sweep → MSS → FVG entry).
- Journaling metrics that matter (good backtest stats to log): time **MSS→FVG fill**, time **entry→target**,
  and **max drawdown** endured per trade. → add these to trade records for the diagnostics.

### Ep 6 — Market Efficiency Paradigm & Institutional Order Flow  *(precise FVG geometry)*
- **Philosophy:** don't trade patterns for their own sake / indicator readings / momentum. **Enter longs
  where retail sells, shorts where retail buys; anticipate price seeking the *opposing* liquidity.**
  **Time of day is vital.**
- **★ Strict 3-candle FVG validity:** bearish FVG — candle-1 low must be **traded below by candle 2**, and
  **candle 3 extends below candle 2** as well; the gap is between **candle-1 high and candle-3 low**.
  Mirror for bullish. → tighter than a naive "gap between c1 and c3"; encodes the displacement requirement.
- **A valid displacement must leave an FVG** between the displacement high and low — no FVG ⇒ not real
  displacement (re-confirms the MSS rule).
- "**Usually the 1st run of the NYSE open is opposite**" (the 09:30 first move is the Judas fake).

### Ep 7 — Daily Bias & Consolidation Hurdles
- **Bias is not an every-day thing**; "embrace imperfection," bias works **around equilibrium**. When
  **uncertain of bias → focus on intraday liquidity pools and get out quick** (scalp, don't hold for the
  daily target). → encode a "bias confidence"; low confidence ⇒ tighter targets / skip.
- **Risk < 1%.** **Counter-trend to your daily target is risky** (don't fade the draw).
- **SMT divergence = the *last* confirmation, not an indicator** (re-confirms Phase-C fix: SMT confirms,
  never triggers). Uses S&P↔Nasdaq (and Dow divergence) as the intermarket pair.

### Ep 9 — Power Of 3 & New York PM Session Opportunities  *(PM session + invalidation rules)*
- **Bullish OB (operational):** consecutive **down-close** candles that create an **FVG on the displacement**
  (mirror for bearish). → ties OB and FVG together into one detectable object.
- **PM session:** after a **large London/overnight run, avoid the 08:30 opening-range low — expect a PM
  discount** instead (the AM already expanded; PM offers the pullback entry). Valid PM window from 13:30.
- For **equities** specifically: a big run up/down is usually followed by **consolidation shortly after**
  (not always). Once price takes liquidity it "likes to take off" and **won't give retail a second chance**
  → real entries are **subtle/sneaky**, small retracements.
- **★ FVG + SSL combo:** an FVG is **even better when it contains SSL** (a swing low tapped into the FVG) —
  use that swing low as both the **stop reference and the entry trigger**. PM example logged **3.5:1 R**
  (stop just under the FVG low, target old-high/BSL).
- **★ FVG invalidation rule:** if the candle **bodies respect the FVG it is NOT invalidated** (a **wick**
  through the gap is fine). → invalidate an FVG only on a **body close** through it, not a wick.

### Ep 8 — Applying Institutional Order Flow To Forex Markets  *(forex — low priority)*
- ICT **dislikes yen pairs**. For a forex pair (e.g. EUR/JPY) use the **futures charts of both
  currencies** to set the longer-term bias. Mostly forex-specific; not directly relevant to our
  equities/futures scope. (Method analog: for a cross, derive bias from each leg's own chart.)

### Ep 11 — PA Review  *(the three AMD session anchors)*
- **★ Three Power-of-3 (AMD) anchors, one per session:**
  - **Entire daily range** AMD anchors at **00:00 MNO**.
  - **AM session** AMD anchors at **08:30**.
  - **PM session** AMD anchors at **13:30**.
  → each session has its own accumulation→manipulation→distribution cycle off its own open price; we
  should compute manipulation relative to the *relevant* session anchor, not just MNO.
- Risk/psychology: **after a big move, don't trade the morning session** (go demo); after a winning day,
  don't rush back — "know when enough is enough." → supports a daily trade-count / post-win cooldown cap.

### Ep 12 — Market Structure For Precision Technicians  *(THE bias + structure engine — highest value)*
- **Don't pick tops/bottoms.** Structure labels: **LTH/ITH/STH**, **LTL/ITL/STL**.
- **★ The first question every day:** *what is the current narrative — is price going up for stops or down
  for stops? higher or lower to rebalance (an FVG)?* Bias = "reach for stops" **or** "reach to rebalance."
- **★ Structure construction rules (codeable):**
  - **LTH/LTL should NOT be broken** (they're tied to the **daily** chart; daily is what banks work off).
  - Every time price **rebalances an FVG**, that swing becomes an **ITH/ITL**. An **ITL has a higher STL on
    each side**; **between two STH sits an ITH** (mirror).
  - A break **above/below an ITH/ITL is a significant MSS**. **ITH/ITL must not be violated** — if it is,
    **stand aside** (you may have the wrong bias).
  - **The high/low that rebalanced an FVG should not get taken out** — if it does, bias is likely wrong.
- **★ Strength gauges (directly implementable):**
  - **If the ITH is *not* higher than the prior 2 STH → market is weak/bearish** (mirror: ITL not lower
    than 2 STL → bullish). A simple, quantifiable trend-strength test.
  - **In bearish conditions every up-close candle should be *respected*** (price shouldn't body-close back
    above it); a violation is only OK if there's a STH above it (then it's a **liquidity grab**). Mirror
    bullish. → candle-by-candle order-flow confirmation of bias.
- **★ Bias *probability* gauge:** clear one-directional read = **high probability**; "could go either way" =
  **low probability, stand down**. → emit a bias-confidence score; only trade high-confidence days (drives
  the "few trades/week, high quality" goal).
- **TF nesting (reaffirmed):** **Daily FVG → 1h structure → 15m entries** (mark only the TF you trade +1/2;
  going too low is overkill). **Bias found off the daily; cap the forecast at a ~5-day horizon.**
- **Fib targeting:** anchor fib **LTL→ITH when bearish** (mirror bullish); **-1.5 = one standard-deviation
  projection** target ("that's where the swing starts"). → target projection method beyond just opposing
  liquidity.

### Ep 13 — Episode 12 In Action  *(high-probability OB checklist)*
- **★ High-probability orderblock = 3 conditions:** (1) a **down/up-closed candle**, (2) it created an
  **FVG** on the displacement, (3) it is **aligned with the daily bias**. → only score an OB as tradeable
  when all three hold (our detector currently checks ~1–2; add the bias-alignment gate).
- Re-confirms Ep 12: in an upmove, **down-closed candles should be respected** (mirror).
- **Engineered EQL/EQH near targets:** when price is close to its objective it often **builds equal
  lows/highs** (a liquidity pool) and runs them *before* reaching the target. → detect equal highs/lows
  as engineered liquidity, especially approaching a target.
- **ITL/ITH should not be breached until the objective is met** — while in a trade, an intact ITL/ITH =
  thesis alive; a breach = exit signal. (Trade-management rule.)
- Psychology/sizing: 20%/month goal, **micro contracts**, grow by **compound + pyramid**; pyramiding
  risks less on each add (re-confirm).

### Ep 14 — Live Trading
- Live-execution video only (screenshot of a +1,626 USD long on MNQ, 12 contracts, TP set). No new
  conceptual content beyond demonstrating the model in real time.

### Ep 15 — Live Trading  *(the 09:30 sweep-into-FVG "2nd chance" model)*
- **★ 09:30 model:** if at the open there's an **FVG with a swing low** beneath it, expect that **low to be
  taken out** (trap early buyers); then **buy in the *original* FVG once price sweeps the low and trades
  back up into it.** Mirror for shorts. → the precise "sweep → reclaim FVG" entry (our sweep+FVG logic
  should re-arm the *original* FVG after the stop-raid rather than abandoning the setup).
- **FOMC:** you *can* trade the **morning**, but **be done early** (flat before the announcement). →
  refines the news rule: FOMC AM is tradeable, just exit before the release window.

### Ep 17 — Forex Application With This Mentorship Model  *(forex, but two reusable rules)*
- Forex-specific (round-number liquidity at 00/20/50/80 levels; mostly EUR/USD demo). Lower priority for
  equities/futures, but two rules generalize:
- **★ 08:30 fallback for the session anchor:** in **bearish** conditions, *if the 08:30 open is **lower**
  than the MNO*, use the **08:30** open (not MNO) as the NY-session reference. → our anchor isn't always
  MNO; pick the **more conservative of {MNO, 08:30}** in the bias direction (bearish→use the lower; the
  mirror for bullish→use the higher). Ties into Ep 19's "is MNO a factor or not" decision.
- He prefers to anchor OBs on the **body** (not wick) — consistent with Mean-Threshold = 50% of OB *body*.
- Exit a **few pips before** the exact target level (front-run the liquidity). → small target-haircut in fills.
- FX news at 10:00 extends the NY killzone to 11:00–11:30 (FX-specific; our window logic already time-boxed).

### Ep 18 — Step By Step Approach To Using This Model In Forex  *(the model's canonical workflow)*
- **★ Top-down workflow (the model in one line):** **always start bias on the Daily** → drop to **1h** for
  structure → **15m is the most important** intraday TF (it's what makes him *trust* the intraday bias) →
  combine **15m + 5m FVGs** for entry. He literally splits TradingView into 3 panes: Daily / 1h / 15m.
- **★ Commit to ONE direction:** only trade the **daily bias** — no counter-trend intraday. "Stick to trading
  1 direction." → a hard gate: intraday signals must agree with the daily-bias sign or they're skipped.
- **★ OB validity = it must create an imbalance after it** ("an OB is a change of the state of delivery; what
  makes it valid? it has to have an imbalance after it"). Restates the Ep 13 checklist — **no FVG after the
  candle ⇒ not a valid OB.** This is the cleanest one-line test to encode.
- **★ Stop placement on large imbalances:** when there's a **large imbalance**, put the stop at the **top of
  that imbalance**, *not* the candle before it. → stop = far edge of the displacement FVG, not last swing.
- "Know what you're looking for ahead of time"; "bias won't be perfect." Gold = event-driven & very manipulated.
- Confirms: **if he could pick only one model, it's the 2022 model** (the one we're building).

### Ep 19 — A Long Rich Lecture  *(densest single deck — bias, Power-of-3, purge&revert)*
- **★ OBs are "bookmarks for the algo"** — price wants to *return* to them later. Mental model for why
  unmitigated OBs/FVGs are draw targets (the algo revisits its own bookmarks).
- **★ "If you can't determine an HTF bias, you're gambling."** Knowing **when *not* to trade** is core; you
  don't trade every day. → an explicit **"no-confident-bias ⇒ no trade"** gate (stand-aside is a first-class
  output of the bias engine, not a fallback).
- **★ Purge & revert (a concrete daily-bias mechanic):** take the **daily SSL (purge)** → then **revert to the
  high of the past 3 days** (the *purge day counts as day 1*). → a measurable bias/target rule: after a sweep
  of daily sell-side, the draw is the prior-3-day high. Testable directly.
- **★ Dealing-range EQ reaction:** if the **daily dealing range touches its EQ (50%)**, expect the **next day**
  to push higher and give a reaction off it. Dealing range = **most energetic & most recent low↔high**.
- **★ 08:30 = "the news embargo"** and the **last-ditch anchor for Power-of-3.** Decision tree for which open
  matters (mirrors Ep 17): **(1)** if (bullish) the **MNO is *lower* than price around/after 08:30**, MNO
  likely *isn't a factor* → use **08:30**; **(2)** if it's a bullish day and we're **already below MNO and
  *still* below it after 08:30**, we're in a **heavy discount** (prime long location). → formalize as:
  `anchor = MNO if MNO still "in play" vs price@830 else 0830; if price below both ⇒ heavy-discount long`.
- **★ The 08:30 read:** "at 08:30 look left at the **swing lows** on a bullish day — we want to **absorb sell
  stops**, pair that with our bias, and look to trade into a **FVG (+ possibly an OB)**." → the canonical
  long trigger: 08:30 sweeps SSL → enter FVG/OB in the bias direction.
- **★ "There's a setup every week."** Calibrates expected **frequency ≈ 1 quality setup / instrument / week**
  → reinforces that **frequency comes from breadth** (our Phase-B reframe), not from loosening filters.
- Playbook restated: mark **MNO + 08:30** opens → look for **Judas swing → FVG → OB** → "make trading boring."
- Mindset: don't rush, don't trade sloppy PA, algo won't change, focus on the logic. (Bias takes time to learn.)

### Ep 20 — London Open  *(forex session; two structural rules)*
- Forex London-open killzone demo (EUR/USD, use **DXY** for EUR/USD & GBP/USD bias). Session itself is FX-only,
  but two structural definitions reinforce the core engine:
- **★ "The market does not like to leave relative equal highs/lows — it runs through them later."** → **EQH/EQL
  are draw targets** (engineered liquidity); a confirmed bias should *prefer* targets that sit just beyond
  rel-equal levels. (Same as Ep 13's engineered-liquidity point, stated as a market law.)
- **★ Displacement (clean definition):** "an **energy move away from the FVG and the high/low it took out**."
  → displacement is measured *relative to the swept level + the resulting FVG*, which is exactly what
  `min_disp_strength` should quantify (range of the displacement leg vs. recent ATR).

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

### Ep 22 — Tape Reading  *(ES/NQ SMT + premium/discount precisions)*
- **★ FVG body-respect = high probability:** "if the **bodies** of the candles respect the FVG, that says a
  lot — high probability." → strengthens the FVG-quality score: a gap whose subsequent candle *bodies* hold
  the edge (not just wicks) ranks higher. Pairs with the Ep 9 invalidation rule (body-close-through kills it).
- **★ Short-term premium/discount arrays:** "anytime price trades **above an old high**, that's a **short-term
  premium array**; **below an old low** = short-term **discount** array." But — **price doesn't have to pull
  back**; it can stay overbought and keep going. Must **align with the narrative** (structure only *frames* an
  idea, it doesn't force the trade). → premium/discount is a *contextual gate*, not a mechanical reversal trigger.
- "**ITH leaves behind imbalance**" (restates Ep 12: each rebalance promotes a swing → ITH/ITL).
- **★ ES↔NQ SMT for confirmation:** "if we're bearish & **NQ makes a bigger buy-stop run** in the morning than
  ES, and **ES is really weak**, that stop-run is **confirmation** we head lower." → SMT = *relative* strength
  read (which index runs liquidity harder), used as bias confirmation, not a standalone signal (consistent w/ Ep 7).
- **★ Targeting precision:** when ES enters a sell program, it likely **reprices to the low where something was
  *respected*, NOT the low where an SSL purge already occurred.** → target *unmitigated* draws; skip levels whose
  liquidity was already taken. Encodable as "prefer un-swept reference lows as targets."

### Ep 23 — FOMC Study  *(the news-catalyst mechanics — high value for our news-as-catalyst thesis)*
- Scope: **FOMC & NFP mostly.** Explicitly **"not an invitation to trade FOMC"** — study material; news is a
  catalyst you read, not a reflex to fade.
- **★ News-day leg sequence:** **Initial leg → another leg → fake-out leg → real setup.** → on high-impact days,
  expect multiple Judas-style protractions *before* the real move; don't take the first displacement — wait for
  the fake-out leg to complete. (Refines our news-day entry timing: arm later on event days.)
- **★ Sweep vs. run distinction:** **running *through* liquidity = continuation**; a **sweep = take the liquidity
  and *reverse*.** → the binary our MSS gate needs: did price *close through* (run/continuation) or *wick-take &
  reject* (sweep/reversal)? Only the **sweep** sets up the counter move.
- **★ Fib anchoring by volatility:** **low volatility expected ⇒ draw the fib/measurements on candle *bodies***;
  **heavy news ⇒ draw on the *wicks*.** → our OTE/target fib should switch its anchor (body vs wick) based on an
  expected-volatility flag (e.g. news day / VIX) — wicks dominate when news whips.
- Dealing ranges + "8 possible trades" — multiple valid entries can stack within one FOMC range (breadth intraday).

### Ep 24 — Model Diagrams & Psychology  *(mostly mindset; one structural rule)*
- Largely a psychology/responsibility rant (start-with-why, critical thinking, "not trading advice").
- **★ Where setups form (the model's validity test):** a setup needs a **CATALYST that sets the run** (15m), then
  **displacement + pattern** (5m). **No displacement ⇒ no pattern ⇒ no trade.** And: **"setup not forming =
  missed move, *not* a broken model."** → encodes the stand-aside discipline: absence of displacement is a valid
  "no-trade," and we must **not** loosen the displacement requirement to manufacture trades (anti-overfit guardrail).
- Diagrams reiterate the two canonical draws: **old high / relative-equal-highs** and **old FVG** as objectives.

### Ep 25 — Daily Rebalance Theory  *(the cleanest daily-bias/target algorithm in the decks — very high value)*
- **★ Daily Rebalance Theory (core bias engine):** when a **major high/low is taken on the weekly/daily**, study
  the **last 3 days** and ask: **is there a FVG?** → if yes, the draw is to **rebalance that FVG**; **if no FVG,
  use PDH/PDL** and rebalance the **previous day's down/up move.** → a fully-specified, testable daily-draw rule
  (this is the "where does price reach for" engine our bias layer is missing).
- **★ Sequence-of-liquidity validation:** "it's important **which liquidity is taken first**. If we're bearish we
  must see **BSL taken first** — otherwise it **invalidates** the idea and we could be bullish." → a hard bias
  gate: confirm the *manipulation* leg swept the *opposite* side first (buy-side before a sell program), else
  stand aside. Directly implementable from MNO/0830 + session highs/lows.
- **★ Purge & revert (restated, precise):** take a major SSL/BSL (**purge**) → **revert to the high/low of the
  past 3 days** (purge day = day 1). Same mechanic as Ep 19; now tied to the FVG-or-PDH/PDL branch above.
- **★ 24-hour cycle starts at Midnight NY** (confirms MNO as the daily anchor). Power-of-3 on 15m → 5m: mark
  **08:30 / 09:30, Judas swing, displacement, equilibrium**, then drop to 4m/3m to find a **FVG in premium**
  (sells) / discount (buys).
- **★ Breakeven rule:** "once price **really swing-mitigates** your entry, *then* go BE." → don't trail to BE on
  the first touch; wait for a confirmed swing past the entry (refines the Risk-deck trail rule).
- **Seasonal tendency:** May is a declining month for stocks/indexes (seasonal context, lower priority for code).
- Don't try to pick exact tops/bottoms ("loses the most money"); trade the rebalance *into* the draw. Asia → AUD/NZD/JPY.

### Ep 26 — Tape Reading  *(counter-trend OB stacking; mostly an execution walk-through)*
- Live tape-reading exercise using **counter-trend bias** to illustrate Institutional Order Flow / liquidity.
- Mechanics: annotate **1st bullish OB → future move → 2nd bullish OB**, pyramid (add contracts), trail SL to
  BE near the "bull's-eye" target, partial out at market. → reinforces the **OB-stacking + pyramiding** flow
  already captured (Risk/Pyramiding decks). No new *rule*, but confirms multiple OBs in one leg are tradeable.
- "Going against traders trying to sell short" = the counter-trend entry is *with* the algo's draw, against the
  crowd. (Same draw-on-liquidity logic; lower marginal value for code.)

### Ep 27 — Counter Trend Ideas  *(lunch-consolidation break model)*
- **★ Counter-trend / lunch model:** if bullish, **mark the lunch-consolidation low(s)** and **wait for the
  break** of them to get long (mirror for shorts). → a concrete PM-session entry: the 12:00–13:00 consolidation
  range becomes a liquidity reference; the *break* of it (after the sweep) re-arms the bias-direction entry.
  Complements the Ep 5 no-trade-lunch rule — *don't trade during* lunch, but *use* its range afterward.
- "Use FVGs **with bias**" (recurring: FVG entries only count in the daily-bias direction). Backtesting/self-talk tips.

### Ep 28 — Silent Presentation  *(execution video only — no new content)*
- Wordless execution recording (ES, "now bought from a buyside imbalance"). Nothing to encode.

### Ep 29 — Trading Bullish Narrow-Range Days w/ SMT  *(quantified SMT-entry rules — high value)*
- **★ Narrow-range-day tell:** "**the day before Fed Chair Powell speaks is usually a small-range day.**" →
  a forward-safe (schedule-known) regime flag: **pre-FOMC-speak day ⇒ expect compression** → favor the
  narrow-range/SMT model, smaller targets. (Schedule is public ⇒ no look-ahead, per our news-causality rule.)
- **★ FVG-above-50%-of-displacement filter (quantified quality gate):** "the **FVG has to be above 50% of the
  displacement leg.**" → a concrete, codeable FVG filter: only take the gap if it sits in the **upper half (buys)
  / lower half (sells)** of the displacement leg that created it. This is the sharpest numeric FVG rule in the decks.
- **★ SMT picks the stronger instrument:** "ICT longed **ES because it was stronger** using the SMT div" — when
  ES↔NQ diverge, **buy the one that refused to make the lower low** (relative strength). → SMT isn't just a yes/no
  confirmation; it **selects which symbol to trade** (the non-confirming/stronger leg). Useful for our multi-symbol `ref()`.
- **★ Close-proximity / 2nd-entry rule:** if you **miss the entry**, you may get in **near it, or at the next
  BOS + FVG**, *as long as it's still worth it* (R-multiple intact). → formalizes a re-entry: missed first FVG ⇒
  wait for the next break-of-structure + fresh FVG, gated by a minimum-R check. (Pairs with Ep 15's 2nd-chance model.)

### Ep 30 — PM Session Trading w/ Fed Chair Volatility Injection  *(brief — one PM rule)*
- **★ PM-session sweep rule:** "when we get a **PM move, the lows/highs of *lunchtime* get swept most likely**."
  → the PM-session draw targets the **12:00–13:00 lunch range extremes**; on Fed-volatility days the PM injection
  is what runs them. Combines with Ep 27 (trade the *break* of the lunch range) and Ep 5 (afternoon follows trend).

### Ep 31 — E-Mini Example  *(brief execution clip)*
- **★ "A swing high formed in a 5m FVG and he entered straight away."** → confirms the LTF trigger: once a
  **swing point forms *inside* a 5m FVG** (in the bias direction), enter immediately — no extra confirmation.
  Pairs with Ep 9's FVG+SSL combo (the swing inside the gap is both trigger and stop reference).

### Ep 32 — Consolidation Day Explained & Market-On-Close Profile  *(regime/day-type detection — high value)*
- **★ Day-type sequence:** **after an OUTSIDE day → expect a range/choppy (consolidation) day.** A **50/50 day**
  (no clear direction) **plays around the EQ → trade the *edges* of the daily range** (fade extremes back to EQ).
  → a regime classifier: prior-day = outside-bar ⇒ next day is mean-reverting, not expansion; switch model
  (fade edges, don't chase displacement). Anti-overfit: don't run the breakout model on consolidation days.
- **★ Consolidation-day timing:** market builds an **initial range early then stays in it until ~15:00–16:00 NY**.
  **Market-On-Close orders cluster ~15:00**: smart money closes positions above/below a high/low, and **after
  they've closed it drops/rallies fast.** → expect a **15:00 MOC volatility burst**; the range holds until then.
- → wire as: `if prev_day_outside or range_compression: regime=consolidation → fade EQ edges, expect 15:00 MOC move`.

### Ep 33 — ES Review & More Insights On FVG & Intraday Market Structure
- **★ Run-vs-sweep continuation:** "**running *through* a low/high *with* an FVG** means it will likely **keep
  running until the final target.**" → restates Ep 23's run/sweep binary from the FVG side: a *displacement run*
  that leaves an FVG = continuation to the draw (don't fade it); a *sweep+reject* = reversal. The **presence of
  an FVG on the break** is the tell for continuation.
- **★ Setup template:** look for a **FVG after a run *below* an old low** (mirror above old high) — the canonical
  "sweep the old level → FVG → enter toward the draw."
- **★ "Unwillingness to trade before 10:00"** — be cautious entering before 10:00 NY (let the 09:30 protraction /
  AM manipulation resolve first). Refines the entry-window: prefer post-10:00 confirmation on ambiguous mornings.

### Ep 34 — PA Review  *(Sunday-gap S/R)*
- **★ Sunday opening gap = support/resistance,** *especially in consolidation weeks like FOMC week*. → for
  futures (continuous), the **Sunday 18:00 open / weekend gap** is a reference level; reactions off it are higher
  in compressed (FOMC) weeks. (Futures-specific; an extra PD-array level alongside MNO/0830.)
- Wednesday gap + co-dependency + "measuring the dealing range the right way" (most-recent energetic low↔high).

### Ep 35 — PA Review  *(SMT timing + OB mechanics — high value)*
- **★ SMT divergences form at *specific session times*: 02:00, 08:30, 09:30, 10:00, 13:30 — and are "only useful
  if you have a bias."** → a concrete **time-gate for SMT checks**: only evaluate ES↔NQ / SPY↔QQQ divergence at
  these macro times, and only act on it in the daily-bias direction. (Explains our Phase-C null: we checked SMT
  continuously instead of at these anchored times.) Note these are the **ICT macro times**.
- **★ OB reference = the candle's *open* and its *50% (mean threshold)*** for a bearish OB (mirror bullish). "**If
  the mean threshold doesn't hold, expect the OB to fail.**" → restates the MT-50%-of-OB-body invalidation as a
  hard rule; uses the **daily OB** as the worked example (HTF OB > LTF OB).
- **★ Multi-stage delivery:** "when a leg has **2 stages to the delivery, use the PD on the *most recent* one.**"
  → when price delivers in two pushes, anchor premium/discount on the **latest** sub-leg, not the whole move.
- "Not likely to run through **high resistance**; high resistance = the **OBs/orderflow that is holding**." →
  unmitigated HTF OBs are real barriers; targets should sit *before* opposing HTF OBs.

### Ep 36 — PA Review  *(NFP-week discipline + sweep recognition)*
- **★ Big-run-no-entry = sweep:** "study when price makes a **big run and doesn't provide an entry — it's likely
  just sweeping.**" → if a move runs without leaving a tradeable FVG/OB pullback, treat it as a **liquidity sweep,
  stand aside** (don't chase). Complements Ep 33 (run *with* FVG = continuation; run *without* = sweep).
- **★ NFP-week rule:** **first week of the month = NFP**, so ICT likes to be **done by the Wednesday NY session**
  (rules of engagement / discipline for week 1). → forward-safe calendar gate: in NFP week, concentrate trading
  Mon–Wed AM, stand down later. (Schedule known ahead ⇒ no look-ahead.)
- ES hourly **oversold-in-discount** + 08:30 news + 09:30 rush-lower context (AM manipulation).

### Ep 37 — PA Review  *(NFP-week stop + draw logic)*
- **★ "Stop trading by Wednesday 08:30 on NFP weeks"** — sharpens Ep 36 to a precise cutoff (Wed 08:30 in NFP week).
- **★ Draw inference:** "if the market **takes out a daily low and creates a swing low**, it's easy to assume it
  **wants to take the recent high.**" → after a sweep of the daily low + LTF swing-low confirmation, the **draw =
  the recent high** (and mirror). A simple, testable draw-on-liquidity rule for the bias layer.
- Bias / breaker / "risky NFP = study opportunity"; higher TFs for context; FVG-above-price; afternoon session.

### Ep 38 — PA Review  *(the canonical day template + reversal trigger — very high value)*
- **★ Bullish-day template (intraday AMD):** **AM rally → lunch consolidation → PM SSL sweep → rally.** If there's
  **no consolidation into lunch and price sweeps SSL going into lunch**, that signals they'll **work *through*
  lunch** (deviation from template). → encode the expected intraday shape; deviations re-route the PM plan.
- **★ PM reversal trigger:** "if price **fails the objective** and gives a **15m MSS with FVG** and **that FVG gets
  respected**, that's enough to look for **opposite trades during PM.**" → a concrete reversal gate: objective-fail
  + 15m MSS + FVG-respect ⇒ flip bias for the PM session.
- **★ Below-MNO re-engage:** "expect a bullish day but drop below MNO ⇒ **wait for a 5m/15m MSS and take it
  instantly**; we want to be **buying close to or below MNO.**" → the heavy-discount long (Ep 19) needs an LTF MSS
  to *trigger*; entry location = at/below MNO.
- "**15m is our bellwether chart**" (confirms Ep 18: 15m is the decision TF). "Orderflow = the FVGs and OBs that hold."

### Ep 39 — Algo Talk  *(THE core thesis — time × price — highest conceptual value)*
- **★★ "Algorithmic theory is based on TIME and PRICE. Price levels are useless until time is considered; time is
  useless unless price is at a key PD array. Blending the two yields astonishing precision."** → the single most
  important design principle: **a setup fires only when a PD array (FVG/OB/old level) is reached AT a key macro
  time.** Our mechanical model checked *price arrays continuously* (no time gate) — this is *why* it was noise.
  The redesign must **gate every entry on the macro-time windows** (00:00 MNO, 08:30, 09:30, 10:00, 13:30, etc.).
- **★ Nested time hierarchy:** **time of day → day of week → week of month → month of year → seasonal tendency.**
  → a layered time-context filter (each level narrows when to expect expansion); not just "killzone yes/no."
- **★ Narrative is prerequisite:** "without a narrative you have **aimless speculation** and **won't recognize a
  stop raid**." If shorting, you should be **above/near the 08:30 open**. → entry *location* is defined relative to
  the 08:30 open; no narrative ⇒ no trade (restates Ep 19's "can't determine bias ⇒ gambling").
- **★ Liquidity alternation:** "after constantly seeking **sellside**, eventually the algo seeks **buyside**." →
  liquidity raids alternate; a series of SSL purges sets up a BSL draw (and mirror) — useful for target sequencing.
- Thesis restated: "**price is delivered by an algo; there is no buying/selling pressure**"; daily-range model =
  **buy below/close-to MNO** (bearish mirror). "The algo doesn't know how much volume sits above/below a level."

### Ep 41 — Final  *(risk/confluence recap)*
- **★ The confluence stack (Tier-3 definition):** "**FVG + OB + OTE after a short-term MSS is golden.**" → the
  highest-quality setup = a short-term **MSS** followed by an entry where **FVG, OB, and the OTE (0.62–0.79) zone
  overlap.** This is exactly the confluence layer our redesign's Tier 3 should score.
- **★ Stop-trail rule (reconfirms Risk deck):** at **50% of the expected target range → trim stop to 25%**; at
  **75% → move to breakeven.** (Matches Ep 25's "BE only after swing-mitigation" — trail in stages, BE late.)
- Mindset: "losses are taxes for success," manage risk, don't touch capital when emotional, "give it 6 months."

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
