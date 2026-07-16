"""
One-off exploration: probe candidate top-level market CategoryCode values
to see which ones are valid and what items they contain. Not part of the
regular pipeline — used to answer "what other categories exist besides the
8 we track" and then deleted.

Usage:
  LOSTARK_API_KEY=... python3 scripts/discover_categories.py
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

SEARCH_API_URL = 'https://developer-lostark.game.onstove.com/markets/items'

# Guessing at the top-level code grid (multiples of 10000) since the 8
# categories we already use (90200-90700, 60200-60500) and the known
# accessory codes (200010/200020/200030) suggest a NN0000 + subcategory
# pattern. Probing broadly to see what's actually valid.
CANDIDATE_CATEGORIES = list(range(10000, 250000, 10000))

MAX_RETRIES = 3
RETRY_DELAY = 2


def search_raw(body, api_key):
    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(
        SEARCH_API_URL,
        data=data,
        headers={
            'accept': 'application/json',
            'authorization': f'bearer {api_key}',
            'content-type': 'application/json',
        },
        method='POST',
    )
    delay = RETRY_DELAY
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 400:
                return None  # invalid category code
            if attempt < MAX_RETRIES - 1:
                time.sleep(delay)
                delay *= 2
            else:
                raise
        except urllib.error.URLError as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(delay)
                delay *= 2
            else:
                raise


def main():
    api_key = os.environ.get('LOSTARK_API_KEY', '')
    if not api_key:
        print('Error: LOSTARK_API_KEY not set')
        sys.exit(1)

    print('=== CATEGORY DISCOVERY ===')
    for cat in CANDIDATE_CATEGORIES:
        try:
            result = search_raw({"CategoryCode": cat}, api_key)
        except Exception as e:
            print(f'Category {cat}: ERROR {e}')
            continue

        if result is None:
            print(f'Category {cat}: invalid/rejected')
            time.sleep(0.3)
            continue

        items = result.get('Items') or []
        total = result.get('TotalCount', len(items))
        names = [i.get('Name', '?') for i in items[:8]]
        print(f'Category {cat}: TotalCount={total}, page has {len(items)} items, sample: {names}')
        time.sleep(0.3)


if __name__ == '__main__':
    main()
