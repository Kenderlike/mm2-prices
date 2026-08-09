import json
import requests

def get_supreme_values():
    # Заголовки, чтобы сайт думал, что мы обычный браузер, а не бот
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # Здесь мы будем прописывать логику вытягивания сотен скинов.
    # Пока вставляем тестовый набор самых популярных предметов, 
    # чтобы проверить, что наш бот на GitHub вообще работает и создает файл.
    parsed_data = {
        "Icebreaker": 225,
        "Heartblade": 65,
        "Corrupt": 3200,
        "Harvester": 4500,
        "Bat": 1250,
        "Makeshift": 900,
        "Default Knife": 1,
        "Default Gun": 1
    }
    
    return parsed_data

if __name__ == "__main__":
    print("Запуск сбора цен...")
    prices = get_supreme_values()
    
    # Автоматически создаем и записываем все цены в нужный файл
    with open("prices.json", "w", encoding="utf-8") as file:
        json.dump(prices, file, ensure_ascii=False, indent=4)
        
    print("Цены успешно сохранены!")
