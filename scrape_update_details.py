"""
Fetch actual update contents from Lost Ark KR '업데이트 내역 안내' notices.
Extracts the patch note body text for each update notice.
"""

import requests
import re
import csv
import time
import json
from html.parser import HTMLParser


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


class ContentExtractor(HTMLParser):
    """Extract text content from the notice detail article body."""

    def __init__(self):
        super().__init__()
        self.in_content = False
        self.depth = 0
        self.parts = []
        self._skip_tags = {"script", "style"}
        self._skip = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        cls = attrs_dict.get("class", "")

        if "article-body" in cls or "fr-view" in cls or "news-con" in cls:
            self.in_content = True
            self.depth = 0

        if self.in_content:
            self.depth += 1
            if tag in self._skip_tags:
                self._skip = True
            if tag == "br":
                self.parts.append("\n")
            if tag in ("p", "div", "h1", "h2", "h3", "h4", "li", "tr"):
                self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.in_content:
            self.depth -= 1
            if tag in self._skip_tags:
                self._skip = False
            if self.depth <= 0:
                self.in_content = False

    def handle_data(self, data):
        if self.in_content and not self._skip:
            text = data.strip()
            if text:
                self.parts.append(text)

    def get_text(self):
        raw = " ".join(self.parts)
        # Clean up whitespace
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n[ \t]+", "\n", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def fetch_notice_content(notice_id: int) -> str:
    """Fetch and extract text content from a notice detail page."""
    url = f"https://m-lostark.game.onstove.com/News/Notice/Views/{notice_id}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    parser = ContentExtractor()
    parser.feed(resp.text)
    text = parser.get_text()

    if not text:
        # Fallback: try regex extraction
        m = re.search(
            r'class="[^"]*(?:article-body|fr-view|news-con)[^"]*"[^>]*>(.*?)</(?:div|section)>',
            resp.text, re.DOTALL
        )
        if m:
            text = re.sub(r"<[^>]+>", "\n", m.group(1))
            text = re.sub(r"\n{3,}", "\n\n", text)
            text = text.strip()

    return text


def main():
    # Load update notices from CSV
    with open("lostark_patch_notices.csv", "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        updates = [r for r in reader if "업데이트 내역" in r["title"]]

    print(f"Fetching content for {len(updates)} update notices...")

    results = []
    for i, notice in enumerate(updates):
        nid = int(notice["notice_id"])
        date = notice["date"]
        title = notice["title"]
        print(f"  [{i+1}/{len(updates)}] {date} - {title} (ID:{nid})...", end=" ", flush=True)

        try:
            content = fetch_notice_content(nid)
            print(f"{len(content)} chars")
        except Exception as e:
            print(f"Error: {e}")
            content = f"[ERROR: {e}]"

        results.append({
            "date": date,
            "title": title,
            "notice_id": nid,
            "url": f"https://m-lostark.game.onstove.com/News/Notice/Views/{nid}",
            "content": content,
        })

        time.sleep(0.5)

    # Save as JSON (better for multi-line content)
    with open("lostark_update_details.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(results)} update details → lostark_update_details.json")

    # Also save a flat CSV with content
    with open("lostark_update_details.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "title", "notice_id", "url", "content"])
        for r in results:
            writer.writerow([r["date"], r["title"], r["notice_id"], r["url"], r["content"]])
    print(f"Saved {len(results)} update details → lostark_update_details.csv")


if __name__ == "__main__":
    main()
