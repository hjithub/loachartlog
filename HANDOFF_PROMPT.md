# Lost Ark KR Gold Exchange Price Analysis — Handoff Prompt

Copy everything below this line and paste it as your opening message in a new conversation.

---

I'm analyzing Lost Ark KR gold exchange price data to correlate game updates with price movements and build a price prediction model. All data files are in this repo.

## Data Files

### Price Data
- **`아비도스_융화_재료.csv`** — 175,641 rows of 5-minute interval price data for 아비도스 융화재료 (Abydos Fusion Material, a proxy for gold exchange rate)
  - Columns: `datetime` (YYYY-MM-DD HH:MM:SS), `price` (integer, -1 = maintenance window)
  - Range: 2024-07-10 ~ 2026-03-23
  - 299 maintenance windows (price = -1)

### Patch Data
- **`lostark_update_details.json`** — Full text of 90 "업데이트 내역 안내" (update detail) notices from the official Lost Ark KR notice board
  - Each entry: `date`, `title`, `notice_id`, `url`, `content` (full Korean patch notes)
  - Range: 2024.04.17 ~ 2026.03.18
  - Content sizes range from ~2K to 102K chars — larger = bigger structural changes
- **`lostark_patch_notices.csv`** — Index of all 372 patch/maintenance notices (including 점검 maintenance, 패치 client patches, etc.)
  - Columns: `date`, `badge`, `title`, `notice_id`, `url`

## Known Price Events to Investigate

| Period | Price Movement | Hypothesis |
|--------|---------------|------------|
| 2024-07 | Crash 178 → 76 | Season 3 / T4 launch (Jul 10, 95K char patch). New tier flooded market with gold sinks and new materials |
| 2024-08~09 | Stabilize ~76 | Post-launch settling, multiple emergency patches fixing T4 issues |
| 2025-01 | Volatile | 카제로스 레이드 3막 launch (Jan 22, 23K). 5 emergency maintenances in 5 days |
| 2025-03 | Rise to ~80s | Check Feb 26 (42K) patch for economy changes |
| 2025-06 | Jump to ~90s | Jun 25 (86K) massive content update |
| 2025-10 | ? | Oct 22 (60K) large update |
| 2025-12 | ? | Dec 10 (102K) biggest single patch in dataset |
| 2026-01 | Dip | Jan 7 (25K) update, plus 니나브 server instability |
| 2026-02~03 | Surge to 100+ | Feb 11 (77K) major update |

## What I Need

1. **Correlation Analysis**: For each major patch, identify economy-relevant changes by searching the patch content for keywords: 골드, 크리스탈, 거래소, 재련, 보상, 교환, 골드 획득, 골드 소모, 경매, 시세, 수수료, 귀속, 거래 가능, 거래 불가, 재화, 실링, 보석, 각인서. Map these to the corresponding price movements.

2. **Feature Engineering**: Build features from the patch data that could predict price direction:
   - Patch size (chars) as proxy for update magnitude
   - Days since last major patch
   - Category of changes (economy/content/balance/QoL)
   - Maintenance frequency (emergency patches = instability = volatility)
   - Whether new gold sinks or gold sources were introduced

3. **Price Prediction Model**: Using the combined price + patch data, build a model (start simple — regression or decision tree) that predicts price direction after patches. Consider:
   - Pre/post patch price deltas at various windows (1h, 1d, 1w, 1m)
   - Seasonal patterns (weekly maintenance cycle, major content cadence)
   - Maintenance window clustering as a volatility signal
   - The -1 values in price data mark exact maintenance windows — useful for alignment

4. **Output**: A summary of which types of changes move the price and in which direction, plus a forward-looking prediction framework.

Start by loading both datasets, then do the correlation analysis between patch content and price movements for the key events listed above. Use `loachart.py` if you need to fetch additional item price data from the loachart.com API.
