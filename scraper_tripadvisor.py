import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import os
import re

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
    rating_svgs = soup.select("svg.evwcZ")  # todos los svg con rating

    # sacar solo fechas tipo "marzo de 2026"
    dates = []
    for d in date_tags:
        text = d.get_text()
        if "Fecha del viaje" in text:
            b = d.find("b")
            if b:
                dates.append(b.get_text(strip=True))

    blacklist = BLACKLIST

    route_index = 0
    date_index = 0
    rating_index = 0

    for review_tag in review_spans:
        review_text = review_tag.get_text(strip=True)
        review_lower = review_text.lower()
        if any(word in review_lower for word in blacklist):
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
        # busco el SVG más cercano al review_tag dentro del mismo bloque
        parent_block = review_tag.find_parent("div", class_="YibKl")
        if parent_block:
            svg_tag = parent_block.select_one("div.VVbkp svg title")
            if svg_tag:
                match = re.search(r"(\d) de 5", svg_tag.get_text())
                if match:
                    overall_rating = int(match.group(1))

        # --- separar origin/destination ---
        if route_text and " - " in route_text:
            origin, destination = route_text.split(" - ", 1)
            data.append({
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
    else:
        df_total = df_new

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