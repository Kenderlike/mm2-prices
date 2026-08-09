"""Объединённый парсер цен MM2 с supremevalues.com.

- Основной путь: curl_cffi (Impersonate Chrome) — обходит Incapsula, быстро, без браузера.
- Запасной путь: undetected_chromedriver (настоящий невидимый Chrome) — если первый сломался.
- Категории объединены из обоих скриптов: все /mm2/<category> страницы сайта.
- Парсит ВСЕ скины, включая со стоимостью 0.
- Untradable определяется по тексту на карточке скина, а не по категории.
- Суффиксы в скобках типа (Knife), (Gun), (Pet) и т.п. вырезаются из названий.
- Цена: если число — округляется, если текст (напр. "x2 T1 Rares") — сохраняется как есть.

Результат: prices.json  =  {"Название": число_или_строка, ...}
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

CATEGORIES = [
    "godlies", "ancients", "chromas", "vintages",
    "collectibles", "pets", "legendaries", "rares",
    "uncommons", "commons", "sets", "uniques", "evos",
    "misc", "untradables",
]

MIN_ITEMS_SANITY = 100
MIN_CATEGORIES_SANITY = 5
DELAY_MIN_SECONDS = 3
DELAY_MAX_SECONDS = 6

# Убирает суффиксы в скобках в конце названия: 'Dark Matter (Knife)' -> 'Dark Matter'
_SUFFIX_RE = re.compile(r'\s*\([^)]*\)\s*$', re.IGNORECASE)


def clean_name(name: str) -> str:
    return _SUFFIX_RE.sub("", name).strip()


def parse_value(text):
    """Разбирает значение цены:
    - Если текст содержит 'untradable' — возвращает строку 'untradable'.
    - Если текст является числом — округляет по правилам математики и возвращает int.
    - Иначе — возвращает сырой текст как есть (напр. 'x2 T1 Rares').
    - Если текст пустой или None — возвращает 0.
    """
    if text is None:
        return 0
    text = text.strip()
    if not text:
        return 0

    # Проверяем untradable прямо в тексте
    if "untradable" in text.lower():
        return "untradable"

    # Пробуем распарсить как число (убираем всё кроме цифр, точки, минуса)
    cleaned = re.sub(r"[^\d.\-]", "", text)
    if cleaned and cleaned not in (".", "-"):
        try:
            num = float(cleaned)
            return round(int(num) if num == int(num) else num)
        except ValueError:
            pass

    # Иначе возвращаем сырой текст
    return text


def _extract_value_from_col(col):
    """Ищет значение цены внутри карточки .itemcolumn.

    Приоритеты:
    1. Атрибут data-value на самой карточке.
    2. Элемент с классом содержащим 'value' внутри карточки.
    3. Плашка untradable (зелёный бейдж с текстом 'untradable').
    """
    # Сначала проверяем наличие untradable-бейджа в карточке
    # Сайт использует разные варианты: класс, текст внутри span/div
    for el in col.find_all(True):
        el_text = el.get_text(strip=True).lower()
        el_classes = " ".join(el.get("class", []))
        if "untradable" in el_text or "untradable" in el_classes.lower():
            return "untradable"

    # Атрибут data-value
    raw = col.get("data-value")
    if raw is not None:
        return parse_value(raw)

    # Элемент с классом *value*
    value_el = col.select_one('[class*="value"]')
    if value_el:
        return parse_value(value_el.get_text(strip=True))

    return 0


def _parse_col(col):
    name_el = col.select_one(".itemhead")
    name = name_el.get_text(strip=True) if name_el else None
    if not name:
        return None

    name = clean_name(name)
    value = _extract_value_from_col(col)
    return {"name": name, "value": value}


# ---------- Быстрый путь: curl_cffi ----------

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
            try:
                resp = session.get(url, impersonate="chrome", timeout=30)
                resp.raise_for_status()
            except Exception as exc:
                print(f"[fast] не получилось '{category}': {exc}")
                continue

            soup = BeautifulSoup(resp.text, "lxml")
            count = 0
            for col in soup.select(".itemcolumn"):
                item = _parse_col(col)
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


# ---------- Запасной путь: undetected_chromedriver ----------

def scrape_browser():
    """Невидимый Chrome переживает проверку на бота."""
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
            print(f"[browser] парсим: {url}")
            driver.get(url)
            time.sleep(5)

            soup = BeautifulSoup(driver.page_source, "html.parser")
            for col in soup.select(".itemcolumn"):
                item = _parse_col(col)
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
