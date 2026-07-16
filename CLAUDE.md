# loachartlog

A single static page (https://hjithub.github.io/loachartlog/) the owner opens to
decide what to buy or sell on the Lost Ark KR market right now. No login, no
stored inventory. Every signal must be computable per-item from public market
data alone.

## Operating rules — read first, violating these derails everything

1. **A question is a question.** Answer it in prose. Do NOT write code, open
   PRs, or build anything in response to a question. Only implement on an
   explicit imperative from the user ("add X", "fix Y", "change Z").
2. If an imperative is ambiguous, ask what it *means* before coding. Do NOT ask
   about implementation logistics (storage, build order, sequencing) for
   something that was never requested to be built.
3. Do not invent requirements. Documented failure: a model assumed a persistent
   inventory system was needed when at most an ephemeral quantity input box was
   implied.
4. Verify live after every pipeline change: dispatch `fetch-movers.yml`, read
   the job logs, inspect the committed `docs/movers.json`. Past silent bugs
   caught only this way: wrong API response shape (twice), today-vs-yesterday
   trade count, pagination truncation.
5. When the user names items to remove by number, they mean **rank positions on
   the live page at that moment**. Resolve them to item IDs from the current
   `docs/movers.json`, state the resolved names back, then edit.
6. Process: work on branch `claude/price-increase-trade-volume-ic1p7p`, reset it
   onto latest `origin/main` before each change (squash merges + hourly bot
   commits make stale branches conflict), one PR per change. **Standing
   permission to merge your own PRs**, then verify. No `gh` CLI in this
   environment — use the GitHub MCP tools. `workflow_dispatch` only sees
   workflow files already present on `main`.

## How the pipeline works today (live, verified — do not break)

- `scripts/fetch_movers.py` runs hourly via `.github/workflows/fetch-movers.yml`
  (cron `0 * * * *`) and on manual dispatch.
- Stage 1: POST `/markets/items` per category in `CATEGORIES`, paginating with
  `PageNo` until `TotalCount` is reached (the API silently returns ~10 items
  per page otherwise), plus one name search for `융화`. Computes `pctChange`
  from `YDayAvgPrice` to `CurrentMinPrice`.
- Stage 2: for the top 60 by % change (both directions — decliners backfill so
  the table stays full), GET `/markets/items/{id}` and take `TradeCount` from
  the **most recent fully completed day** in `Stats`. Never use today's bucket:
  it is partial and resets to ~0 at the day boundary.
- Writes `docs/movers.json`; the page renders one table sorted by tradeCount
  descending, % colored green/red/gray. Also writes `docs/prices.json` so the
  legacy `docs/craft.html` (unlinked but kept) keeps working.
- Categories: 90200/90300/90400/90700 (life materials), 60200–60500 (battle
  items), 230000 (gems), 50000 (honing materials). 100000 was added and then
  removed on request — do not re-add. 60000 duplicates 60200–60500 — do not add.
- Noise controls: skip items with `YDayAvgPrice < 1`;
  `EXCLUDED_NAME_SUBSTRINGS = ['오레하']`;
  `EXCLUDED_ITEM_IDS = {66130133, 66110223, 66110204, 66112523}`.
  Rationale: items with a ~1–2g yesterday price turn tiny absolute moves into
  absurd +100–8000% readings. Append here when the user flags more noise.

## API facts (learned by probing, not from docs)

- Rate limit: 100 requests/minute. A run currently makes ~75–90 calls over
  ~90 seconds — close to the ceiling. Re-measure before adding categories or
  per-item fetches.
- `GET /markets/items/{id}` returns a **JSON list wrapping one object**; that
  object holds `Stats: [{Date, AvgPrice, TradeCount}, ...]` covering ~14 recent
  days. Two wrong shape guesses shipped before this was confirmed from real
  logs — always verify response shapes from actual output.
- `TradeCount` = completed sales (판매 건수), not active listings.

## Roadmap — direction is set; each item still needs the user's explicit "go"

Do not start any of these unless the user says so. Build strictly one at a
time, verifying live before moving on. Recommended order and rationale:

1. **Persist per-item daily history** (prerequisite for everything below).
   Stage 2 already receives ~14 days of `{Date, AvgPrice, TradeCount}` per
   fetched item and throws it away. Merge it into a committed rolling file
   (e.g. `docs/history.json`, keyed by item id, capped at ~90 days). Zero
   extra API calls. Because each fetch backfills 14 days, items that drift in
   and out of the top-60 still accumulate continuous history. Invisible
   infrastructure — no UI change.
2. **Price vs. recent range.** From that history: label each row
   "near 30-day high / near 30-day low / mid-range". Trivial math once
   history exists, highest insight-per-effort of the visible features.
3. **Trend direction.** 3–5 day slope on daily `AvgPrice` → up/down/flat arrow
   per row. Hour-over-hour detection is optional later (requires persisting
   hourly snapshots, which nothing does yet).
4. **Stack ÷ volume note.** Frontend-only: an unsaved quantity input that shows
   "≈N days of normal volume" using the already-displayed tradeCount. Tiny;
   can slot in anytime. **No stored inventory — ever.**
5. **Patch/season risk badge.** Independent track: revive the notice-scraping +
   keyword-tagging logic (`scrape_notices.py`, `analyze.py` keyword sets)
   against *recent* notices, flag hits in the last ~14 days as a plain warning
   badge. Never a computed number. Verify the notice source still works before
   building on it.
6. **Weekly cycle position.** Needs ≥6 weeks of accumulated daily history to
   say anything honest — starting item 1 now is what makes this possible
   later. Must show "no reliable pattern" when confidence is low; never
   fabricate a cycle from noise.
7. **"Act on this first" section — last.** One more section where the topmost
   row is the most important thing for the user to act on (that is what the
   user's phrase "not too friendly, best case topmost" means). Only meaningful
   once items 2–3 are live and trusted. Deliberately open, to be decided with
   the user when the time comes:
   - Ranking metric: undecided. `pctChange × tradeCount` was floated (caveats:
     mixed units; either a thin-volume % spike or a huge-volume flat price can
     dominate). `absoluteGoldDelta × tradeCount` is closer to a real money-flow
     quantity. Once item 1 has accumulated history, candidate metrics can be
     backtested against it cheaply before shipping anything.
   - Shape: one combined BUY/SELL-labeled ranking vs. two separate lists —
     undecided.
   - Prefer transparent rules (e.g. near-low + rising + liquid = BUY candidate)
     over a single opaque multiplied score; the user consistently wants to see
     *why* a row ranks where it does.
