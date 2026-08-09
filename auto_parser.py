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
    """Разбирает значение цены из строки value на сайте:
    - Если текст является числом — округляет до ближайшего целого.
    - Если текст — каша вроде 'x2 T1 Rares' — возвращает 1.
    - Если текст пустой или None — возвращает None (поле не найдено).
    """
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None

    # Текст является чистым числом (цифры, пробелы, точки, запятые)
    if re.fullmatch(r'[\d\s.,]+', text):
        try:
            return round(float(re.sub(r'[^\d.]', '', text)))
        except ValueError:
            pass

    # Любой другой нечисловой текст (x2 T1 Rares, etc.) → цена 1
    return 1


def _extract_value_from_col(col):
    """Ищет значение цены внутри карточки .itemcolumn.

    Логика:
    - Если найден элемент с классом *value* или атрибут data-value — парсим цену.
    - Если поле value отсутствует ВООБЩЕ — предмет untradable.
    """
    # Атрибут data-value
    raw = col.get("data-value")
    if raw is not None:
        val = parse_value(raw)
        if val is not None:
            return val

    # Элемент с классом *value*
    value_el = col.select_one('[class*="value"]')
    if value_el:
        val = parse_value(value_el.get_text(strip=True))
        if val is not None:
            return val

    # Поля value нет вообще — предмет untradable
    return "untradable"


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


def debug_html():
    """Сохраняет сырой HTML первых 5 карточек из godlies для отладки."""
    if not HAS_CURL:
        print("[debug] curl_cffi не установлен")
        return
    with cf_requests.Session() as session:
        resp = session.get(f"{BASE_PREFIX}godlies", impersonate="chrome", timeout=30)
        soup = BeautifulSoup(resp.text, "lxml")
        cols = soup.select(".itemcolumn")
        print(f"[debug] найдено .itemcolumn: {len(cols)}")
        debug_path = HERE / "debug_cards.html"
        with open(debug_path, "w", encoding="utf-8") as f:
            for i, col in enumerate(cols[:5]):
                f.write(f"\n\n<!-- === CARD {i} === -->\n")
                f.write(str(col.prettify()))
        print(f"[debug] первые 5 карточек сохранены в {debug_path}")


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
    debug_html()  # временно: смотрим структуру HTML
    # main()
