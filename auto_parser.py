import json
import time
import undetected_chromedriver as uc
from bs4 import BeautifulSoup

# Ссылки на абсолютно ВСЕ категории сайта
CATEGORIES = [
    "https://supremevalues.com/godlies",
    "https://supremevalues.com/ancients",
    "https://supremevalues.com/chromas",
    "https://supremevalues.com/vintages",
    "https://supremevalues.com/collectibles",
    "https://supremevalues.com/pets",
    "https://supremevalues.com/legendaries",
    "https://supremevalues.com/rares",
    "https://supremevalues.com/uncommons",
    "https://supremevalues.com/commons"
]

# Сюда вписывай мусорные скины, которых нет на сайте.
# Скрипт будет добавлять их в базу при каждом обновлении автоматически.
CUSTOM_ITEMS = {
    "Aquarium": 1,
    "Palms": 1,
    "Bunnies": 1,
    "Splash": 1,
    "Blue Elite": 2,
    "Green Elite": 2,
    "Cotton Candy": 5,
    "Rune": 1,
    "Deep Sea": 1,
    "Floral": 1,
    "Pop Art": 1,
    "Robot": 1,
    "Sunny": 1,
    "Default Knife": 0,
    "Default Gun": 0
}

def run_parser():
    print("Настраиваем невидимый браузер для обхода Cloudflare...")
    options = uc.ChromeOptions()
    # Запускаем без визуального окна
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = uc.Chrome(options=options)
    all_prices = {}
    
    try:
        for url in CATEGORIES:
            print(f"Парсим категорию: {url}")
            driver.get(url)
            # Ждем 5 секунд, чтобы страница полностью прогрузилась и прошла проверка на бота
            time.sleep(5) 
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            headers = soup.find_all(class_='itemhead')
            
            for header in headers:
                name = header.get_text(strip=True)
                parent = header.parent
                if parent:
                    # Ищем ценник рядом с названием
                    value_el = parent.select_one('[class*="value"]')
                    if not value_el and parent.parent:
                        value_el = parent.parent.select_one('[class*="value"]')
                        
                    if name and value_el:
                        val_str = ''.join(filter(str.isdigit, value_el.get_text()))
                        if val_str:
                            all_prices[name] = int(val_str)
                            
    except Exception as e:
        print(f"Произошла ошибка при парсинге: {e}")
    finally:
        driver.quit()
        
    # Если парсер сработал и собрал данные
    if all_prices:
        # Добавляем наши ручные предметы (коммонки и т.д.) к спарсенным
        all_prices.update(CUSTOM_ITEMS)
        
        with open("prices.json", "w", encoding="utf-8") as f:
            json.dump(all_prices, f, ensure_ascii=False, indent=4)
        print(f"Успех! База обновлена. Всего предметов: {len(all_prices)}")
    else:
        print("Не удалось собрать цены. Cloudflare оказался сильнее.")

if __name__ == "__main__":
    run_parser()
