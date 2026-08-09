"""Объединённый парсер цен MM2 с supremevalues.com.

- Основной путь: curl_cffi (Impersonate Chrome) — обходит Incapsula, быстро, без браузера.
- Запасной путь: undetected_chromedriver (настоящий невидимый Chrome) — если первый сломался.
- Категории объединены из обоих скриптов: все /mm2/<category> страницы сайта.
- Парсит ВСЕ скины, включая со стоимостью 0.
- Untradable предметы записываются со значением "untradable".
- Суффиксы в скобках типа (Knife), (Gun), (Pet) и т.п. вырезаются из названий.

Результат: prices.json  =  {"Название": цена_или_"untradable", ...}
"""
import json
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

try:
    from curl_cffi import requests as cf_requests
    HAS_CURL = True
except ImportError:
    HAS_CURL = False

HERE = Path(__file__).resolve().parent
PRICES_PATH = HERE / "prices.json"
META_PATH = HERE / "meta.json"

BASE_PREFIX = "https://supremevalues.com/mm2/"

# Все категории сайта.
CATEGORIES = [
    "godlies", "ancients", "chromas", "vintages",
    "collectibles", "pets", "legendaries", "rares",
    "uncommons", "commons", "sets", "uniques", "evos",
    "misc", "untradables",
]

# Категории, предметы которых помечаются как untradable.
UNTRADABLE_CATEGORIES = {"untradables"}

MIN_ITEMS_SANITY = 100
MIN_CATEGORIES_SANITY = 5
DELAY_MIN_SECONDS = 3
DELAY_MAX_SECONDS = 6

# Суффиксы в скобках, которые нужно вырезать из названий.
# Регулярка убирает любой текст в круглых скобках в конце названия.
_SUFFIX_RE = re.compile(r'\s*\([^)]*\)\s*$', re.IGNORECASE)


def clean_name(name: str) -> str:
    """Убирает суффиксы в скобках из конца названия: 'Dark Matter (Knife)' -> 'Dark Matter'."""
    return _SUFFIX_RE.sub("", name).strip()


def parse_num(text, default=0):
    """Разбирает число из текста; сохраняет десятичные (напр. 0.002 вместо 0)."""
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


# ---------- Быстрый путь: curl_cffi (обход Incapsula/Cloudflare) ----------

def _parse_col(col, untradable=False):
    name_el = col.select_one(".itemhead")
    name = name_el.get_text(strip=True) if name_el else None
    if not name:
        return None

    name = clean_name(name)

    if untradable:
        return {"name": name, "value": "untradable"}

    # основный источник цены — атрибут data-value (точный, с десятичными)
    value = col.get("data-value")
    value = parse_num(value, default=None) if value is not None else None

    # запасной путь — ищем любой элемент class*="value" рядом с названием
    if value is None:
        parent = name_el.parent
        value_el = parent.select_one('[class*="value"]') if parent else None
        if not value_el and parent and parent.parent:
            value_el = parent.parent.select_one('[class*="value"]')
        value = parse_num(value_el.get_text(strip=True) if value_el else None, default=None)

    # если цена не нашлась вообще — записываем 0
    if value is None:
        value = 0

    return {"name": name, "value": value}


def scrape_fast():
    """curl_cffi: обходит anti-bot по TLS-отпечатку. Возвращает список {name, value}."""
    if not HAS_CURL:
        return []
    items = []
    categories_with_data = 0

    with cf_requests.Session() as session:
        for i, category in enumerate(CATEGORIES):
            if i > 0:
                time.sleep(random.uniform(DELAY_MIN_SECONDS, DELAY_MAX_SECONDS))
            url = f"{BASE_PREFIX}{category}"
            untradable = category in UNTRADABLE_CATEGORIES
            try:
                resp = session.get(url, impersonate="chrome", timeout=30)
                resp.raise_for_status()
            except Exception as exc:
                print(f"[fast] не получилось '{category}': {exc}")
                continue

            soup = BeautifulSoup(resp.text, "lxml")
            count = 0
            for col in soup.select(".itemcolumn"):
                item = _parse_col(col, untradable=untradable)
                if item:
                    items.append(item)
                    count += 1
            if count:
                categories_with_data += 1
            print(f"[fast] {category}: {count}")

    if len(items) < MIN_ITEMS_SANITY or categories_with_data < MIN_CATEGORIES_SANITY:
        print(f"[fast] мало данных: {len(items)} предметов из {categories_with_data} категорий — путь не сработал")
        return []
    return items


# ---------- Запасной путь: undetected_chromedriver (настоящий браузер) ----------
def scrape_browser():
    """Та же идея: невидимый Chrome переживает проверку на бота."""
    try:
        import undetected_chromedriver as uc
    except ImportError:
        print("[browser] undetected_chromedriver не установлен — пропуск")
        return []

    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = None
    items = []
    try:
        driver = uc.Chrome(options=options)
        for category in CATEGORIES:
            url = f"{BASE_PREFIX}{category}"
            untradable = category in UNTRADABLE_CATEGORIES
            print(f"[browser] парсим: {url}")
            driver.get(url)
            time.sleep(5)  # ждём прогрузку и проверку на бота

            soup = BeautifulSoup(driver.page_source, "html.parser")
            for header in soup.find_all(class_="itemhead"):
                name = clean_name(header.get_text(strip=True))
                if not name:
                    continue

                if untradable:
                    items.append({"name": name, "value": "untradable"})
                    continue

                parent = header.parent
                value_el = None
                if parent:
                    value_el = parent.select_one('[class*="value"]')
                    if not value_el and parent.parent:
                        value_el = parent.parent.select_one('[class*="value"]')
                value = parse_num(value_el.get_text() if value_el else None, default=0)
                items.append({"name": name, "value": value})
    except Exception as exc:
        print(f"[browser] ошибка: {exc}")
    finally:
        if driver is not None:
            driver.quit()

    if len(items) < MIN_ITEMS_SANITY:
        print(f"[browser] мало данных: {len(items)} — браузерный путь не сработал")
        return []
    return items


def main():
    prices = {}

    items = scrape_fast() or scrape_browser()
    for item in items:
        prices[item["name"]] = item["value"]

    if not prices:
        print("НЕ УДАЛОСЬ собрать цены. Проверьте доступ к supremevalues.com")
        return

    now = datetime.now(timezone.utc)
    PRICES_PATH.write_text(json.dumps(prices, ensure_ascii=False, indent=4), encoding="utf-8")
    META_PATH.write_text(
        json.dumps({"updatedAt": now.isoformat(), "count": len(prices)}, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )
    print(f"[done] успешно обновлено: {len(prices)} предметов -> {PRICES_PATH}")


if __name__ == "__main__":
    main()
