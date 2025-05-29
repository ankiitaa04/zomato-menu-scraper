from flask import Flask, render_template, request
import requests
from bs4 import BeautifulSoup
import re
import json
from html import unescape
import time
import random

app = Flask(__name__)

user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15',
    'Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36',
]

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

    headers = {'User-Agent': random.choice(user_agents)}

    time.sleep(3)  # simple rate limiting

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        return None, None, f"Error fetching page: {e}"

    print(f"DEBUG: Response snippet -> {response.text[:200]}")

    soup = BeautifulSoup(response.text, 'html.parser')

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
    app.run(debug=True)
