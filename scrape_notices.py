"""
Scrape Lost Ark KR notice board for patch/maintenance notices.
Extracts date, title, notice ID, and URL for relevant notices.
"""

import requests
import re
import csv
import time

BASE_URL = "https://m-lostark.game.onstove.com/News/Notice/List"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

# Keywords for patch/maintenance notices
KEYWORDS = re.compile(r"점검|업데이트|패치|수정|변경")

# Regex to extract notice entries from HTML
# Matches both /NoticeViews/{id} (pinned) and /Views/{id} (regular)
NOTICE_RE = re.compile(
    r'<a\s+href="/News/Notice/(?:Notice)?Views/(\d+)[^"]*"[^>]*>'  # notice ID
    r'.*?icon--(\w+)"[^>]*>([^<]+)</span>'                          # icon class + badge text
    r'.*?list__title">([^<]+)</span>'                                # title
    r'.*?list__date"[^>]*>(\d{4}\.\d{2}\.\d{2})</div>',             # date
    re.DOTALL,
)


def fetch_page(page: int) -> list[dict]:
    """Fetch a single page of notices and parse entries."""
    params = {
        "page": page,
        "searchtype": 0,
        "searchtext": "",
        "noticetype": "all",
    }
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    html = resp.text

    notices = []
    for m in NOTICE_RE.finditer(html):
        nid, icon_type, badge, title, date = m.groups()
        notices.append({
            "id": int(nid),
            "badge": badge.strip(),
            "title": title.strip(),
            "date": date.strip(),
        })
    return notices


def is_relevant(notice: dict) -> bool:
    """Check if a notice is patch/maintenance related."""
    badge = notice.get("badge", "")
    title = notice.get("title", "")
    if badge == "점검":
        return True
    if KEYWORDS.search(title):
        return True
    return False


def main():
    all_notices = []
    seen_ids = set()
    cutoff_date = "2024.05.01"

    print("Scraping Lost Ark KR notice board...")

    for page in range(1, 60):
        print(f"  Page {page}...", end=" ", flush=True)
        try:
            notices = fetch_page(page)
        except Exception as e:
            print(f"Error: {e}")
            break

        if not notices:
            print("No notices found, stopping.")
            break

        page_relevant = 0
        oldest_date = None

        for n in notices:
            nid = n["id"]
            if nid in seen_ids:
                continue
            seen_ids.add(nid)

            date = n["date"]
            oldest_date = date

            if date < "2024":
                continue

            if is_relevant(n):
                all_notices.append(n)
                page_relevant += 1

        print(f"{page_relevant} relevant, oldest: {oldest_date}")

        if oldest_date and oldest_date < cutoff_date:
            print("Reached cutoff date, stopping.")
            break

        time.sleep(0.5)

    # Sort by date
    all_notices.sort(key=lambda x: x["date"])

    # Save CSV
    output = "lostark_patch_notices.csv"
    with open(output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "badge", "title", "notice_id", "url"])
        for n in all_notices:
            writer.writerow([
                n["date"],
                n["badge"],
                n["title"],
                n["id"],
                f"https://m-lostark.game.onstove.com/News/Notice/Views/{n['id']}",
            ])

    print(f"\nSaved {len(all_notices)} notices → {output}")

    print("\n=== Summary ===")
    for n in all_notices:
        print(f"  {n['date']}  [{n['badge']}]  {n['title']}")


if __name__ == "__main__":
    main()
