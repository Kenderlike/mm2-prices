import json
import random
import re
import time
from pathlib import Path
from bs4 import BeautifulSoup
from curl_cffi import requests as cf_requests

HERE = Path(__file__).resolve().parent
PRICES_PATH = HERE / "prices.json"

BASE_URL = "https://supremevalues.com/mm2"
IMPERSONATE = "chrome"

CATEGORIES = [
    "sets", "uniques", "evos", "ancients", "vintages", "chromas",
    "godlies", "legendaries", "rares", "uncommons", "commons",
    "pets", "misc", "untradables",
]

# Сюда вписываем только то, чего 100% нет ни в одной категории на сайте
CUSTOM_ITEMS = {
    "Default Knife": 0,
    "Default Gun": 0
}

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
    # Новый парсер друга ищет точную цифру в дата-атрибуте
    value = _parse_num(col.get("data-value"), default=None)
    if value is None:
        return None
    return {"name": name, "value": value}

def main():
    all_prices = {}
    categories = list(CATEGORIES)
    random.shuffle(categories)

    print("Запускаем парсер через curl_cffi...")
    with cf_requests.Session() as session:
        for i, category in enumerate(categories):
            if i > 0:
                time.sleep(random.uniform(DELAY_MIN_SECONDS, DELAY_MAX_SECONDS))
                
            url = f"{BASE_URL}/{category}"
            try:
                resp = session.get(url, impersonate=IMPERSONATE, timeout=30)
                resp.raise_for_status()
            except Exception as exc:
                print(f"Ошибка загрузки '{category}': {exc}")
                continue

            soup = BeautifulSoup(resp.text, "lxml")
            count = 0
            for col in soup.select(".itemcolumn"):
                item = _parse_item(col)
                if item:
                    all_prices[item["name"]] = item["value"]
                    count += 1
            print(f"Категория {category}: найдено {count} предметов")

    if all_prices:
        # Приклеиваем наши кастомные/дефолтные предметы
        all_prices.update(CUSTOM_ITEMS)
        
        with open(PRICES_PATH, "w", encoding="utf-8") as f:
            json.dump(all_prices, f, ensure_ascii=False, indent=4)
        print(f"Успех! База обновлена. Всего предметов: {len(all_prices)}")
    else:
        print("Ошибка: не удалось собрать цены.")

if __name__ == "__main__":
    main()
