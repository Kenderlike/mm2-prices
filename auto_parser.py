
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
ALIASES_PATH = HERE / "aliases.txt"

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

# Встроенные исключения на случай, если aliases.txt отсутствует.
# Ключ всегда приводится к нижнему регистру и лишним пробелам.
DEFAULT_ALIASES = {
    "bioblade": "Bio Blade",
}

DEFAULT_ALIASES_FILE = """# Список исключений названий.
# Формат: Сайтовое имя = Игровое имя
# Также поддерживается вариант: Сайтовое имя -> Игровое имя
# Строки, начинающиеся с #, игнорируются.
# Можно писать комментарии после #.

Bioblade = Bio Blade
"""

# Регулярки для очистки названий.
PAREN_SUFFIX_RE = re.compile(r"\s*\([^)]*\)\s*$")
PAREN_WEAPON_RE = re.compile(r"\s*\(\s*(?:gun|knife)\s*\)\s*", re.IGNORECASE)
TRAILING_WEAPON_RE = re.compile(r"[\s\-]*\b(gun|knife)\b\s*$", re.IGNORECASE)

# Регулярки для определения типа оружия.
PAREN_KNIFE_RE = re.compile(r"\(\s*knife\s*\)", re.IGNORECASE)
PAREN_GUN_RE = re.compile(r"\(\s*gun\s*\)", re.IGNORECASE)
END_KNIFE_RE = re.compile(r"\bknife\b\s*$", re.IGNORECASE)
END_GUN_RE = re.compile(r"\bgun\b\s*$", re.IGNORECASE)

KNIFE_ANY_RE = re.compile(r"\bknife\b", re.IGNORECASE)
GUN_ANY_RE = re.compile(r"\bgun\b", re.IGNORECASE)

UNTRADABLE_RE = re.compile(
    r"\buntrad(?:eable|able)\b|\bnot\s+trad(?:eable|able)\b",
    re.IGNORECASE,
)

MULTISPACE_RE = re.compile(r"\s{2,}")


def make_soup(markup):
    """BeautifulSoup с fallback, если lxml не установлен."""
    try:
        return BeautifulSoup(markup, "lxml")
    except Exception:
        return BeautifulSoup(markup, "html.parser")


def norm_key(text):
    """Нормализация ключа для aliases: нижний регистр + один пробел."""
    return " ".join(str(text).lower().split())


def load_aliases():
    """Загружает словарь исключений из aliases.txt."""
    aliases = dict(DEFAULT_ALIASES)

    if not ALIASES_PATH.exists():
        try:
            ALIASES_PATH.write_text(DEFAULT_ALIASES_FILE, encoding="utf-8")
        except Exception:
            pass

    try:
        if ALIASES_PATH.exists():
            try:
                text = ALIASES_PATH.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                text = ALIASES_PATH.read_text(encoding="cp1251")

            for line in text.splitlines():
                if "#" in line:
                    line = line.split("#", 1)[0].strip()

                line = line.strip()
                if not line:
                    continue

                if "=" in line:
                    site_name, game_name = line.split("=", 1)
                elif "->" in line:
                    site_name, game_name = line.split("->", 1)
                else:
                    continue

                site_name = site_name.strip()
                game_name = game_name.strip()

                if site_name and game_name:
                    aliases[norm_key(site_name)] = game_name

    except Exception as exc:
        print(f"[aliases] не удалось прочитать aliases.txt: {exc}")

    return aliases


ALIASES = load_aliases()


def remove_paren_suffixes(name):
    """Убирает хвостовые скобки и отдельно (Gun)/(Knife)."""
    if not name:
        return ""

    result = name.strip()
    prev = None

    # Dark Matter (Knife) -> Dark Matter
    while prev != result:
        prev = result
        result = PAREN_SUFFIX_RE.sub("", result).strip()

    # Если где-то осталось (Gun) или (Knife), тоже вырезаем.
    result = PAREN_WEAPON_RE.sub(" ", result)
    result = MULTISPACE_RE.sub(" ", result).strip()

    return result


def remove_trailing_weapon_words(name):
    """Удаляет конечные Gun/Knife: Palms Knife -> Palms."""
    if not name:
        return ""

    result = TRAILING_WEAPON_RE.sub("", name).strip()
    result = MULTISPACE_RE.sub(" ", result).strip()

    # Если после очистки осталось пусто, возвращаем исходный вариант.
    return result or name.strip()


def detect_weapon_from_text(text):
    """Определяет knife/gun по скобкам или слову в конце названия."""
    if not text:
        return None

    if PAREN_KNIFE_RE.search(text):
        return "knife"

    if PAREN_GUN_RE.search(text):
        return "gun"

    if END_KNIFE_RE.search(text):
        return "knife"

    if END_GUN_RE.search(text):
        return "gun"

    return None


def flatten_attrs(col):
    """Собирает значения атрибутов BeautifulSoup-тега в строку."""
    parts = []

    for value in col.attrs.values():
        if isinstance(value, (list, tuple, set)):
            parts.extend(str(x) for x in value)
        else:
            parts.append(str(value))

    return " ".join(parts)


def detect_weapon_from_col(col):
    """Запасной поиск типа оружия в классах/атрибутах элемента."""
    parts = []

    if col.get("class"):
        parts.extend(col.get("class"))

    parts.append(flatten_attrs(col))

    haystack = " ".join(parts).lower()

    if KNIFE_ANY_RE.search(haystack):
        return "knife"

    if GUN_ANY_RE.search(haystack):
        return "gun"

    return None


def parse_num(text, default=0):
    """Разбирает цену.

    Примеры:
      1,234.56 -> 1234.56
      1234,56 -> 1234.56
      1,234 -> 1234
      0 -> 0
    """
    if text is None:
        return default

    raw = re.sub(r"[^\d.,+\-]", "", str(text).strip())

    if not raw or raw in ("+", "-", ".", ","):
        return default

    if "," in raw and "." in raw:
        # Считаем запятую разделителем тысяч: 1,234.56
        raw = raw.replace(",", "")

    elif "," in raw:
        parts = raw.split(",")

        # Если одна запятая и ровно 3 цифры после неё — тысячи: 1,234
        # Если несколько запятых — тоже считаем их тысячными.
        if (len(parts) == 2 and len(parts[1]) == 3) or len(parts) > 2:
            raw = raw.replace(",", "")
        else:
            # Иначе десятичный разделитель: 12,34
            raw = raw.replace(",", ".")

    try:
        value = Decimal(raw)
    except InvalidOperation:
        return default

    if value == value.to_integral_value():
        return int(value)

    return float(value)


def is_untradable(col):
    """Проверяет, помечен ли предмет как untradable."""
    text_parts = [
        col.get_text(" ", strip=True),
        flatten_attrs(col),
        " ".join(col.get("class", [])),
    ]

    text = " ".join(text_parts).lower()
    return bool(UNTRADABLE_RE.search(text))


def extract_price(col):
    """Достаёт цену из атрибутов или внутренних элементов колонки."""
    for attr in ("data-value", "data-price", "data-rap"):
        if col.get(attr) is not None:
            value = parse_num(col.get(attr), default=None)
            if value is not None:
                return value

    for element in col.select(
        '[data-value], [data-price], [class*="value"], [class*="price"]'
    ):
        candidate = (
            element.get("data-value")
            or element.get("data-price")
            or element.get_text(" ", strip=True)
        )

        value = parse_num(candidate, default=None)
        if value is not None:
            return value

    return 0


def _parse_col(col, untradable=False):
    """Парсит один предмет."""
    name_el = col.select_one(".itemhead")
    raw_name = name_el.get_text(" ", strip=True) if name_el else None

    if not raw_name:
        return None

    # Сначала определяем тип по исходному тексту: там могут быть (Gun)/(Knife).
    weapon_type = detect_weapon_from_text(raw_name)

    # Чистим скобки.
    name_no_paren = remove_paren_suffixes(raw_name)

    if weapon_type is None:
        weapon_type = detect_weapon_from_text(name_no_paren)

    if weapon_type is None:
        weapon_type = detect_weapon_from_col(col)

    # Удаляем конечные Gun/Knife уже после определения типа.
    name = remove_trailing_weapon_words(name_no_paren)

    # Применяем словарь исключений.
    # Пробуем разные варианты: исходный, без скобок, без Gun/Knife.
    alias_candidates = [raw_name, name_no_paren, name]

    for candidate in alias_candidates:
        key = norm_key(candidate)
        if key in ALIASES:
            name = ALIASES[key]
            break

    # На всякий случай повторно чистим скобки и хвосты после alias.
    name = remove_paren_suffixes(name)
    name_before_trailing = name
    name = remove_trailing_weapon_words(name)

    if weapon_type is None:
        weapon_type = detect_weapon_from_text(raw_name)

    if weapon_type is None:
        weapon_type = detect_weapon_from_text(name_before_trailing)

    if weapon_type is None:
        weapon_type = detect_weapon_from_col(col)

    name = MULTISPACE_RE.sub(" ", name).strip()

    if not name:
        name = name_no_paren.strip() or raw_name.strip()

    if untradable or is_untradable(col):
        value = "untradable"
    else:
        value = extract_price(col)

    return {
        "name": name,
        "value": value,
        "type": weapon_type,
    }


# ---------- Быстрый путь: curl_cffi ----------


def scrape_fast():
    """curl_cffi: обходит anti-bot по TLS-отпечатку."""
    if not HAS_CURL:
        print("[fast] curl_cffi не установлен — пропуск быстрого пути")
        return []

    items = []
    categories_with_data = 0

    with cf_requests.Session() as session:
        for i, category in enumerate(CATEGORIES):
            category = category.strip()

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

            soup = make_soup(resp.text)
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
        print(
            f"[fast] мало данных: {len(items)} предметов "
            f"из {categories_with_data} категорий — путь не сработал"
        )
        return []

    return items


# ---------- Запасной путь: undetected_chromedriver ----------


def scrape_browser():
    """Невидимый Chrome, если curl_cffi не сработал."""
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
    categories_with_data = 0

    try:
        driver = uc.Chrome(options=options)

        for i, category in enumerate(CATEGORIES):
            category = category.strip()

            if i > 0:
                time.sleep(random.uniform(DELAY_MIN_SECONDS, DELAY_MAX_SECONDS))

            url = f"{BASE_PREFIX}{category}"
            untradable = category in UNTRADABLE_CATEGORIES

            print(f"[browser] парсим: {url}")

            try:
                driver.get(url)
                time.sleep(5)
                soup = make_soup(driver.page_source)
            except Exception as exc:
                print(f"[browser] не получилось '{category}': {exc}")
                continue

            count = 0

            for col in soup.select(".itemcolumn"):
                item = _parse_col(col, untradable=untradable)
                if item:
                    items.append(item)
                    count += 1

            if count:
                categories_with_data += 1

            print(f"[browser] {category}: {count}")

    except Exception as exc:
        print(f"[browser] ошибка: {exc}")

    finally:
        if driver is not None:
            driver.quit()

    if len(items) < MIN_ITEMS_SANITY or categories_with_data < MIN_CATEGORIES_SANITY:
        print(
            f"[browser] мало данных: {len(items)} предметов "
            f"из {categories_with_data} категорий — браузерный путь не сработал"
        )
        return []

    return items


# ---------- Сохранение результата ----------


def empty_result():
    return {
        "Оружие": {
            "Ножи": {},
            "Пистолеты": {},
        },
        "Прочее": {},
    }


def add_leaf(container, name, value):
    """Добавляет предмет в словарь.

    Если предмет с таким именем уже есть и цена отличается,
    создаётся ключ вида 'Name (2)', чтобы не терять данные.
    """
    if name not in container:
        container[name] = value
        return

    if container[name] == value:
        return

    base = name
    n = 2

    while f"{base} ({n})" in container:
        n += 1

    container[f"{base} ({n})"] = value


def add_item(result, item):
    name = item.get("name")
    if not name:
        return

    value = item.get("value", 0)
    weapon_type = item.get("type")

    if weapon_type == "knife":
        add_leaf(result["Оружие"]["Ножи"], name, value)
    elif weapon_type == "gun":
        add_leaf(result["Оружие"]["Пистолеты"], name, value)
    else:
        add_leaf(result["Прочее"], name, value)


def count_result(result):
    knives = len(result["Оружие"]["Ножи"])
    guns = len(result["Оружие"]["Пистолеты"])
    other = len(result["Прочее"])
    return knives + guns + other


def main():
    items = scrape_fast()

    if not items:
        items = scrape_browser()

    result = empty_result()

    for item in items:
        add_item(result, item)

    total = count_result(result)

    if total == 0:
        print("НЕ УДАЛОСЬ собрать цены. Проверьте доступ к supremevalues.com")
        return

    now = datetime.now(timezone.utc)

    PRICES_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )

    META_PATH.write_text(
        json.dumps(
            {
                "updatedAt": now.isoformat(),
                "count": total,
                "weapons": {
                    "knives": len(result["Оружие"]["Ножи"]),
                    "guns": len(result["Оружие"]["Пистолеты"]),
                },
                "other": len(result["Прочее"]),
            },
            ensure_ascii=False,
            indent=4,
        ),
        encoding="utf-8",
    )

    print(f"[done] успешно обновлено: {total} предметов -> {PRICES_PATH}")


if __name__ == "__main__":
    main()
