from flask import Flask, render_template, request
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import shutil
import re
import json
from html import unescape
import time
import os

app = Flask(__name__)

def extract_needed_data(json_data):
    if isinstance(json_data, str):
        json_data = json.loads(json_data)

    pages = json_data.get("pages", {})
    current_page = pages.get('current', {})
    resId = str(current_page.get("resId", ""))
    print(f"DEBUG: Extracted resId = {resId}")

    restaurant_data = pages.get('restaurant', {}).get(resId, {})
    name = restaurant_data.get("sections", {}).get("SECTION_BASIC_INFO", {}).get('name', 'Restaurant')
    print(f"DEBUG: Restaurant Name = {name}")

    menus = restaurant_data.get("order", {}).get("menuList", {}).get("menus", [])

    filtered_data = []
    for menu in menus:
        category_name = menu.get("menu", {}).get("name", "")
        for category in menu.get("menu", {}).get("categories", []):
            sub_category_name = category.get("category", {}).get("name", "")
            for item in category.get("category", {}).get("items", []):
                item_data = item.get("item", {})
                filtered_data.append({
                    "restaurant": name,
                    "category": category_name,
                    "sub_category": sub_category_name,
                    "dietary_slugs": ','.join(item_data.get("dietary_slugs", [])),
                    "item_name": item_data.get("name", ""),
                    "price": item_data.get("display_price", ""),
                    "desc": item_data.get("desc", "")
                })

    return filtered_data, name

def get_menu(url):
    if not url.endswith('/order'):
        url += '/order'

    print(f"DEBUG: Fetching URL -> {url}")

    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        # Automatically detect the binary location of Chrome or Chromium
        chromium_path = shutil.which("chromium-browser") or shutil.which("chromium") or shutil.which("google-chrome")
        if chromium_path:
            chrome_options.binary_location = chromium_path
        else:
            print("⚠️ Chromium not found in environment.")

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(url)
        time.sleep(5)  # wait for page to load

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        driver.quit()

        scripts = soup.find_all('script')
        for script in scripts:
            if 'window.__PRELOADED_STATE__' in script.text:
                match = re.search(r'window\.__PRELOADED_STATE__ = JSON\.parse\((.+?)\);', script.text)
                if match:
                    try:
                        escaped_json = match.group(1)
                        decoded_json_str = unescape(escaped_json)
                        parsed_json = json.loads(decoded_json_str)
                        preloaded_state = json.loads(parsed_json)

                        menu_data, restaurant_name = extract_needed_data(preloaded_state)
                        return menu_data, restaurant_name, None
                    except Exception as e:
                        return None, None, f"Error parsing embedded JSON: {e}"

        return None, None, "No embedded menu data found on this page."
    except Exception as e:
        return None, None, f"Selenium error: {e}"

@app.route("/", methods=["GET", "POST"])
def index():
    error = None
    menu_items = None
    restaurant_name = None

    if request.method == "POST":
        url = request.form.get("url", "").strip()
        if not url:
            error = "Please enter a valid Zomato restaurant URL."
        else:
            menu_items, restaurant_name, error = get_menu(url)

    return render_template("index.html", error=error, menu_items=menu_items, restaurant_name=restaurant_name)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
