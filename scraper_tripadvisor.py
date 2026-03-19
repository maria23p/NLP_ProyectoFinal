import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import os
import re

# prueba maria
OUTPUT_FILE = "tripadvisor_reviews.csv"

BLACKLIST = [
    "hola",
    "gracias por compartir",
    "quedamos a tu disposición",
    "instagram",
    "facebook",
    "x)",
    "vueling team",
    "si lo deseas",
    "puedes contactarnos"
]

def connect_to_chrome():
    options = Options()
    options.debugger_address = "127.0.0.1:9222"
    driver = webdriver.Chrome(options=options)
    return driver

def extract_reviews(driver):
    soup = BeautifulSoup(driver.page_source, "lxml")
    data = []

    review_spans = soup.select("span.JguWG")
    routes = soup.select("span.thpSa")
    date_tags = soup.select("span:has(b)")

    # Fechas tipo "marzo de 2026"
    dates = []
    for d in date_tags:
        text = d.get_text()
        if "Fecha del viaje" in text:
            b = d.find("b")
            if b:
                dates.append(b.get_text(strip=True))

    route_index = 0
    date_index = 0

    for review_tag in review_spans:
        review_text = review_tag.get_text(strip=True)
        review_lower = review_text.lower()
        if any(word in review_lower for word in BLACKLIST):
            continue

        # --- ruta ---
        if route_index < len(routes):
            route_text = routes[route_index].get_text(strip=True)
            route_index += 1
        else:
            continue

        # --- tipo vuelo ---
        flight_type = None
        if route_index < len(routes):
            flight_type = routes[route_index].get_text(strip=True)
            route_index += 1

        # --- fecha ---
        if date_index < len(dates):
            travel_date = dates[date_index]
            date_index += 1
        else:
            travel_date = "Desconocida"

        # --- rating ---
        overall_rating = None
        try:
            container = review_tag.find_parent()
            svg = container.find_previous("svg", class_="evwcZ") or container.find_next("svg", class_="evwcZ")
            if svg:
                title = svg.find("title")
                if title:
                    text = title.get_text()
                    match = re.search(r"(\d)\s*de\s*5", text)
                    if match:
                        overall_rating = int(match.group(1))
        except:
            pass

        # --- origen del usuario ---
        user_origin = "Desconocido"
        try:
            author_box = review_tag.find_previous("div", class_="QIHsu")
            if author_box:
                geo_section = author_box.find("div", class_="vYLts")
                if geo_section:
                    candidates = geo_section.find_all("div", class_="biGQs")
                    for c in candidates:
                        text = c.get_text(strip=True)
                        if (text and 
                            "contribu" not in text.lower() and 
                            not text.isdigit() and 
                            "navcl" in c.get("class", [])):
                            user_origin = text
                            break
        except:
            pass

        # --- separar origin/destination ---
        if route_text and " - " in route_text:
            origin, destination = route_text.split(" - ", 1)
            data.append({
                "origin_user": user_origin,
                "origin": origin,
                "destination": destination,
                "flight_type": flight_type,
                "travel_date": travel_date,
                "overall_rating": overall_rating,
                "review_text": review_text
            })

    return data

def save_reviews(reviews):
    df_new = pd.DataFrame(reviews)

    if os.path.exists(OUTPUT_FILE):
        df_old = pd.read_csv(OUTPUT_FILE)
        df_total = pd.concat([df_old, df_new])
        df_total.drop_duplicates(inplace=True)

        if "id" in df_total.columns:
            start_id = int(df_total["id"].max()) + 1
        else:
            start_id = 1
    else:
        df_total = df_new
        start_id = 1

    # Resetear índice y asignar IDs
    df_total = df_total.reset_index(drop=True)
    df_total["id"] = range(start_id, start_id + len(df_total))

    # Mover 'id' a la primera columna
    cols = ["id"] + [col for col in df_total.columns if col != "id"]
    df_total = df_total[cols]

    df_total.to_csv(OUTPUT_FILE, index=False)
    print("Total guardadas:", len(df_total))

if __name__ == "__main__":
    driver = connect_to_chrome()
    print("Conectado a Chrome")

    while True:
        input("\nPulsa ENTER para scrapear esta página")
        reviews = extract_reviews(driver)
        print("Reviews encontradas:", len(reviews))
        save_reviews(reviews)

        next_page = input("\n'n' para ir a la siguiente página o ENTER para terminar: ")
        if next_page != "n":
            break
        print("Ve al navegador y pulsa Next page")
        input("Pulsa ENTER cuando cargue")

    driver.quit()