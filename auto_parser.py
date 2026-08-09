import json
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup
from curl_cffi import requests as cf_requests

HERE = Path(__file__).resolve().parent
PRICES_PATH = HERE / "prices.json"
META_PATH = HERE / "meta.json"

BASE_URL = "https://supremevalues.com/mm2"
IMPERSONATE = "chrome"

CATEGORIES = [
    "sets", "uniques", "evos", "ancients", "vintages", "chromas",
    "godlies", "legendaries", "rares", "uncommons", "commons",
    "pets", "misc", "untradables",
]

# Мусор, которого физически нет на сайте ни в каком виде
CUSTOM_ITEMS = {
    "Default Knife": 0,
    "Default Gun": 0
}

MIN_ITEMS_SANITY = 100
MIN_CATEGORIES_SANITY = 10
DELAY_MIN_SECONDS = 3
DELAY_MAX_SECONDS = 6


def _parse_num(text, default=0):
    if text is None:
        return default
    cleaned = re.sub(r"[^\d+\-.]", "", str(text))
    if not cleaned or cleaned in ("+", "-", "."):
        return default
    try:
        num = float(cleaned)
    except ValueError:
        return default
    return int(num) if num == int(num) else num


def _parse_item(col):
    name_el = col.select_one(".itemhead")
    name = name_el.get_text(strip=True) if name_el else None
    if not name:
        return None

    # НАША ПРАВКА: Отрезаем приписки Knife и Gun, чтобы совпадало с игрой
    name = re.sub(r'(?i)\s+(Knife|Gun)$', '', name).strip()

    value = _parse_num(col.get("data-value"), default=None)
    if value is None:
        return None

    return {"name": name, "value": value}


def scrape_all():
    items = []
    categories_with_data = 0

    categories = list(CATEGORIES)
    random.shuffle(categories)

    with cf_requests.Session() as session:
        for i, category in enumerate(categories):
            if i > 0:
                time.sleep(random.uniform(DELAY_MIN_SECONDS, DELAY_MAX_SECONDS))

            url = f"{BASE_URL}/{category}"
            try:
                resp = session.get(url, impersonate=IMPERSONATE, timeout=30)
                resp.raise_for_status()
            except Exception as exc:
                print(f"[scrape] failed to fetch '{category}': {exc}")
                continue

            soup = BeautifulSoup(resp.text, "lxml")
            count = 0
            for col in soup.select(".itemcolumn"):
                item = _parse_item(col)
                if item:
                    items.append(item)
                    count += 1
            if count:
                categories_with_data += 1
            print(f"[scrape] {category}: {count} items")

    if len(items) < MIN_ITEMS_SANITY or categories_with_data < MIN_CATEGORIES_SANITY:
        raise RuntimeError(
            f"Sanity check failed: only {len(items)} items across "
            f"{categories_with_data} categories parsed. Site HTML likely changed."
        )
    return items


def main():
    items = scrape_all()

    prices = {item["name"]: item["value"] for item in items}
    
    # Приклеиваем дефолтные предметы к общей массе
    prices.update(CUSTOM_ITEMS)

    now = datetime.now(timezone.utc)
    PRICES_PATH.write_text(
        json.dumps(prices, ensure_ascii=False, indent=4), encoding="utf-8"
    )
    META_PATH.write_text(
        json.dumps(
            {"updatedAt": now.isoformat(), "count": len(prices)},
            ensure_ascii=False,
            indent=4,
        ),
        encoding="utf-8",
    )
    print(f"[done] {len(prices)} items -> {PRICES_PATH}")


if __name__ == "__main__":
    main()
