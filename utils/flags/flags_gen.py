import os
import io
import requests
import pycountry
from PIL import Image

# --- КОНФІГУРАЦІЯ ---
OUTPUT_DIR = "game_assets/flags_iso3"
TARGET_SIZE = (450, 300)  # Ширина x Висота
# Використовуємо FlagCDN (w640 дає високу якість)
CDN_URL_TEMPLATE = "https://flagcdn.com/w640/{iso2}.png"

class FlagProcessor:
    def __init__(self):
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
        
        self.countries = [
            c for c in pycountry.countries 
            if hasattr(c, 'alpha_2') and hasattr(c, 'alpha_3')
        ]

    def run(self):
        print(f"Починаємо обробку {len(self.countries)} країн...")
        print(f"Метод: Примусове стискання (Resize) до {TARGET_SIZE[0]}x{TARGET_SIZE[1]}")
        print("Весь малюнок буде збережено (без обрізки).\n")

        success = 0
        for country in self.countries:
            iso2 = country.alpha_2.lower()
            iso3 = country.alpha_3.upper()
            
            if self.download_and_resize(iso2, iso3):
                print(f"[OK] {iso3}")
                success += 1
            else:
                print(f"[FAIL] {iso3}")

        print(f"\nГотово! Оброблено {success} прапорів.")

    def download_and_resize(self, iso2, iso3):
        url = CDN_URL_TEMPLATE.format(iso2=iso2)
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                return False

            with Image.open(io.BytesIO(resp.content)) as img:
                # Переконуємося, що працюємо в якісному кольоровому просторі
                if img.mode in ("P", "L"):
                    img = img.convert("RGBA")
                
                # ВИКОРИСТОВУЄМО .resize ЗАМІСТЬ .fit
                # Це стисне прапор США, Великої Британії тощо рівно у 400x300
                # Жодні зірки чи смуги не вилізуть за межі.
                final_img = img.resize(TARGET_SIZE, Image.Resampling.LANCZOS)
                
                save_path = os.path.join(OUTPUT_DIR, f"{iso3}.png")
                # Зберігаємо з максимальним стисненням для гри
                final_img.save(
                    save_path, 
                    "PNG", 
                    optimize=True, 
                    compress_level=9
                )
                return True
        except Exception as e:
            print(f"Помилка {iso3}: {e}")
            return False

if __name__ == "__main__":
    app = FlagProcessor()
    app.run()