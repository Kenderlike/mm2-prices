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
from decimal import Decimal, InvalidOperation
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
    """Разбирает цену, сохраняя дробную часть и разделители."""
    if text is None:
        return default
    raw = re.sub(r"[^\d,.+\-]", "", str(text).strip())
    if not raw or raw in ("+", "-", ".", ","):
        return default
    if "," in raw and "." not in raw:
        raw = raw.replace(",", ".")
    elif "," in raw and "." in raw:
        raw = raw.replace(",", "")
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return default
    return int(value) if value == value.to_integral_value() else float(value)


def is_untradable(col):
    text = (col.get_text(" ", strip=True) + " " + " ".join(map(str, col.attrs.values()))).lower()
    return bool(re.search(r"\buntrad(?:eable|able)\b|\bnot\s+trad(?:eable|able)\b", text))


def extract_price(col):
    for attr in ("data-value", "data-price", "data-rap"):
        if col.get(attr) is not None:
            value = parse_num(col[attr], default=None)
            if value is not None:
                return value
    for element in col.select('[class*="value"], [class*="price"], [data-value], [data-price]'):
        value = parse_num(element.get("data-value") or element.get("data-price") or element.get_text(" ", strip=True), default=None)
        if value is not None:
            return value
    return 0


# ---------- Быстрый путь: curl_cffi (обход Incapsula/Cloudflare) ----------

def _parse_col(col, untradable=False):
    name_el = col.select_one(".itemhead")
    name = name_el.get_text(" ", strip=True) if name_el else None
    if not name:
        return None
    name = clean_name(name)
    if is_untradable(col):
        return {"name": name, "value": "untradable"}
    return {"name": name, "value": extract_price(col)}


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
            for col in soup.select(".itemcolumn"):
                item = _parse_col(col, untradable=untradable)
                if item:
                    items.append(item)
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
