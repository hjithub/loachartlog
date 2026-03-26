import json
import os
import sys
import time
import datetime
import urllib.request

API_KEY = os.environ.get('LOSTARK_API_KEY', '')
if not API_KEY:
    print('Error: LOSTARK_API_KEY not set')
    sys.exit(1)

CATEGORIES = [90200, 90300, 90400, 90700, 60200, 60300, 60400, 60500]
WANTED_IDS = {
    6882701, 6882704, 6885705, 6885709,
    6882101, 6882104, 6882107,
    6882301, 6882304, 6884307, 6884308,
    6882401, 6882404, 6884407,
    101063, 101291, 101151, 101221, 101191, 101938,
    6861012, 6861013,
}

EXTRA_SEARCHES = [
    {"CategoryCode": 50010, "ItemName": "융화"},
]

def fetch_items(body):
    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(
        'https://developer-lostark.game.onstove.com/markets/items',
        data=data,
        headers={
            'accept': 'application/json',
            'authorization': f'bearer {API_KEY}',
            'content-type': 'application/json',
        },
        method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode('utf-8'))
    return result.get('Items', [])

all_items = []

for cat in CATEGORIES:
    items = fetch_items({"CategoryCode": cat})
    all_items.extend(items)
    print(f'Category {cat}: {len(items)} items')
    time.sleep(0.5)

for search in EXTRA_SEARCHES:
    items = fetch_items(search)
    all_items.extend(items)
    print(f'Search {search}: {len(items)} items')
    time.sleep(0.5)

prices = {}
for item in all_items:
    if item['Id'] in WANTED_IDS:
        prices[item['Name']] = {
            'id': item['Id'],
            'currentMinPrice': item['CurrentMinPrice'],
            'yDayAvgPrice': item['YDayAvgPrice'],
            'recentPrice': item['RecentPrice'],
            'bundleCount': item['BundleCount'],
            'icon': item['Icon'],
        }

output = {
    'updated_at': datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
    'prices': prices,
}

os.makedirs('docs', exist_ok=True)
with open('docs/prices.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f'Wrote {len(prices)} items to docs/prices.json')
for name, info in sorted(prices.items()):
    print(f'  {name}: {info["currentMinPrice"]}g')

if len(prices) < 15:
    print(f'Warning: only {len(prices)} items found, expected 22')
    sys.exit(1)
