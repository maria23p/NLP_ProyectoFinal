import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import os
import re

# CONFIGURACIÓN
AIRLINES = [
     #{
     #    "name": "Vueling Airlines",
     #    "prefix": "VLG",
     #    "url": "https://www.tripadvisor.es/Airline_Review-d8729185-Reviews-Vueling-Airlines",
     #    "output": "vueling.csv"
     #},
    #{
    #    "name": "Iberia",
    #    "prefix": "IBE",
    #    "url": "https://www.tripadvisor.es/Airline_Review-d8729089-Reviews-Iberia",
    #    "output": "iberia.csv"
    #},
    {
        "name": "Volotea",
        "prefix": "VOE",
        "url": "https://www.tripadvisor.es/Airline_Review-d10533097-Reviews-Volotea",
        "output": "volotea.csv"
    },
    {
        "name": "Iberia Express",
        "prefix": "IBS",
        "url": "https://www.tripadvisor.es/Airline_Review-d10823588-Reviews-Iberia-Express",
        "output": "iberia_express.csv"
    },
    {
        "name": "Binter",
        "prefix": "IBB",
        "url": "https://www.tripadvisor.es/Airline_Review-d8729034-Reviews-Binter",
        "output": "binter.csv"
    },
    {
        "name": "Air Europa",
        "prefix": "AEA",
        "url": "https://www.tripadvisor.es/Airline_Review-d8729002-Reviews-Air-Europa",
        "output": "air_europa.csv"
    }
]

# CONEXIÓN
def connect_to_chrome():
    options = Options()
    options.debugger_address = "127.0.0.1:9222"
    driver = webdriver.Chrome(options=options)
    return driver

# UTILIDADES
def clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()

def is_valid_review(review_text):
    if not review_text or len(review_text.split()) < 5:
        return False

    review_lower = review_text.lower()

    basura = [
        "esta es la versión de nuestra página web",
        "tripadvisor llc no garantiza",
        "tripadvisor llc no es una agencia de reservas",
        "sitios web externos",
        "opiniones (",
        "escribe una opinión",
        "sube una foto",
    ]

    return not any(x in review_lower for x in basura)

# EXTRACCIÓN
def extract_reviews(driver, airline_name):
    soup = BeautifulSoup(driver.page_source, "lxml")
    data = []

    review_cards = soup.find_all("div", class_=lambda c: c and "lwGaE" in c.split())
    print("Cards encontradas:", len(review_cards))

    if len(review_cards) < 5:
        print("POSIBLE ERROR: pocas cards detectadas")

    for card in review_cards:
        try:
            # bloque principal
            main_block = card.find("div", class_=lambda c: c and "tuuww" in c.split())
            if not main_block:
                continue

            # texto reseña
            review_span = main_block.find("span", class_=lambda c: c and "JguWG" in c.split())
            if not review_span:
                continue

            review_text = clean_text(review_span.get_text(" ", strip=True))
            if not is_valid_review(review_text):
                continue

            # defaults
            origin = "Desconocido"
            destination = "Desconocido"
            flight_type = "Desconocido"
            travel_date = "Desconocida"
            rating = None
            origin_user = "Desconocido"

            # ruta y tipo de vuelo
            route_div = main_block.find("div", class_=lambda c: c and "ZNjnF" in c.split())
            if route_div:
                route_spans = route_div.find_all("span", class_=lambda c: c and "thpSa" in c.split())

                if len(route_spans) >= 1:
                    route_text = clean_text(route_spans[0].get_text(" ", strip=True))
                    if " - " in route_text:
                        origin, destination = [x.strip() for x in route_text.split(" - ", 1)]

                if len(route_spans) >= 2:
                    flight_type = clean_text(route_spans[1].get_text(" ", strip=True))

            # rating
            svg = card.find("svg", class_="evwcZ")
            if svg:
                title_tag = svg.find("title")
                if title_tag:
                    m = re.search(r"(\d)\s*de\s*5", title_tag.get_text(" ", strip=True))
                    if m:
                        rating = int(m.group(1))

            # fecha del viaje
            card_text = card.get_text(" ", strip=True)
            m_date = re.search(
                r"Fecha del viaje:\s*([A-Za-záéíóúñÁÉÍÓÚÑ]+\s+de\s+\d{4})",
                card_text,
                re.IGNORECASE
            )
            if m_date:
                travel_date = m_date.group(1).strip()

            # origen del usuario
            qihsu = card.find("div", class_=lambda c: c and "QIHsu" in c.split())
            if qihsu:
                vylts = qihsu.find("div", class_=lambda c: c and "vYLts" in c.split())
                if vylts:
                    txt = clean_text(vylts.get_text(" ", strip=True))
                    if txt and "contribu" not in txt.lower():
                        origin_user = txt

            data.append({
                "airline": airline_name,
                "origin_user": origin_user,
                "origin": origin,
                "destination": destination,
                "flight_type": flight_type,
                "travel_date": travel_date,
                "rating": rating,
                "review_text": review_text
            })

        except Exception as e:
            print("Error en una review:", e)
            continue

    print("Reviews válidas:", len(data))
    if data:
        print("Última review:", data[-1]["review_text"][:120])

    return data

# GUARDADO
def save_reviews(reviews, output_file, prefix):
    if not reviews:
        print("No hay reviews nuevas para guardar.")
        return

    df_new = pd.DataFrame(reviews)

    if os.path.exists(output_file):
        df_old = pd.read_csv(output_file)
        df_old = df_old.drop(columns=["id"], errors="ignore")
        df_total = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_total = df_new.copy()

    df_total.drop_duplicates(subset=["airline", "review_text"], inplace=True)
    df_total = df_total.reset_index(drop=True)

    # id único con prefijo
    df_total["id"] = [f"{prefix}_{i:04d}" for i in range(1, len(df_total) + 1)]

    cols = ["id"] + [col for col in df_total.columns if col != "id"]
    df_total = df_total[cols]

    df_total.to_csv(output_file, index=False, encoding="utf-8")
    print("Total guardadas:", len(df_total))

# MAIN
if __name__ == "__main__":
    driver = connect_to_chrome()

    for airline in AIRLINES:
        print("\n==========")
        print("Scrapeando:", airline["name"])

        driver.get(airline["url"])

        while True:
            input("\nENTER para scrapear esta página...")
            reviews = extract_reviews(driver, airline["name"])
            save_reviews(reviews, airline["output"], airline["prefix"])

            nxt = input("\n'n' para ir a la siguiente página o ENTER para cambiar de aerolínea: ")
            if nxt.lower() != "n":
                break

            print("Pulsa Next en navegador")
            input("ENTER cuando cargue...")

    driver.quit()