import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import os
import re

OUTPUT_FILE = "tripadvisor_reviews.csv" # archivo final


def connect_to_chrome():
    # conectarse a Chrome para Selenium con el puerto de depuración abierto (chrome --remote-debugging-port=9222)
    options = Options()
    options.debugger_address = "127.0.0.1:9222"
    driver = webdriver.Chrome(options=options)
    return driver


def clean_text(text):
    # si el texto es None o vacio, devuelve cadena vacia
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip() # limpieza


def extract_reviews(driver):
    # obtiene todo el HTML de la página y lo procesa con BeautifulSoup para extraer las reviews
    soup = BeautifulSoup(driver.page_source, "lxml")
    data = []

    # bloque completo de cada reseña
    review_cards = soup.find_all("div", class_=lambda c: c and "lwGaE" in c.split())
    print("Cards encontradas:", len(review_cards)) # imprime num cards q ha encontrado en esa página

    # recorre cada card de review encontrada
    for card in review_cards: 
        try:
            # bloque principal de la review del usuario
            main_block = card.find("div", class_=lambda c: c and "tuuww" in c.split())
            if not main_block: # si no existe el bloque, se salta esa reviews
                continue

            # texto de la review del usuario (solo el del bloque principal)
            review_span = main_block.find("span", class_=lambda c: c and "JguWG" in c.split())
            if not review_span:
                continue

            # extrae el texto de la review, lo limpia y verifica que tenga al menos 5 palabras para considerarla válida
            review_text = clean_text(review_span.get_text(" ", strip=True))
            if not review_text or len(review_text.split()) < 5:
                continue
            review_lower = review_text.lower()

            # filtra textos que no son reviews reales sino basura de la interfaz de TripAdvisor (e.g. textos legales)
            if (
                "esta es la versión de nuestra página web" in review_lower
                or "tripadvisor llc no garantiza" in review_lower
                or "tripadvisor llc no es una agencia de reservas" in review_lower
                or "sitios web externos" in review_lower
                or "opiniones (" in review_lower
                or "escribe una opinión" in review_lower
                or "sube una foto" in review_lower
            ):
                continue

            # busca bloque de ruta y tipo de vuelo
            route_div = main_block.find("div", class_=lambda c: c and "ZNjnF" in c.split())
            if not route_div:
                continue

            route_spans = route_div.find_all("span", class_=lambda c: c and "thpSa" in c.split())
            if len(route_spans) < 2: # si no encuentra ambos spans (ruta y tipo de vuelo), se salta esa review
                continue
            
            # extrae y limpia
            route_text = clean_text(route_spans[0].get_text(" ", strip=True))
            flight_type = clean_text(route_spans[1].get_text(" ", strip=True))

            if " - " not in route_text: # la ruta debe tener formato "origen - destino", si no lo tiene, se salta esa review
                continue

            origin, destination = [x.strip() for x in route_text.split(" - ", 1)] # separa origen y destino

            # rating global: primer svg evwcZ del card
            overall_rating = None
            svg = card.find("svg", class_="evwcZ")
            if svg:
                title_tag = svg.find("title")
                if title_tag: # usa regex para capturar el numero antes de "de 5" en el título del svg
                    m = re.search(r"(\d)\s*de\s*5", title_tag.get_text(" ", strip=True))
                    if m:
                        overall_rating = int(m.group(1))

            # fecha del viaje
            travel_date = "Desconocida" # valor por defecto si no se encuentra la fecha
            card_text = card.get_text(" ", strip=True)
            m_date = re.search(
                r"Fecha del viaje:\s*([A-Za-záéíóúñÁÉÍÓÚÑ]+\s+de\s+\d{4})",
                card_text,
                re.IGNORECASE
            )
            if m_date:
                travel_date = m_date.group(1).strip()

            # origen del usuario
            user_origin = "Desconocido"
            qihsu = card.find("div", class_=lambda c: c and "QIHsu" in c.split())
            if qihsu:
                vylts = qihsu.find("div", class_=lambda c: c and "vYLts" in c.split())
                if vylts: # el bloque vYLts suele contener el origen del usuario,
                    # pero a veces también contiene texto de contribuciones del usuario,
                    # por eso se limpia y se verifica que no contenga palabras como "contribu" antes de asignarlo como origen
                    txt = clean_text(vylts.get_text(" ", strip=True))
                    if txt and "contribu" not in txt.lower():
                        user_origin = txt

            # añade la review extraída a la lista final de resultados
            data.append({
                "origin_user": user_origin,
                "origin": origin,
                "destination": destination,
                "flight_type": flight_type,
                "travel_date": travel_date,
                "overall_rating": overall_rating,
                "review_text": review_text
            })

        except Exception as e:
            print("Error en una review:", e)
            continue

    print("Reviews válidas extraídas:", len(data))
    if data:
        print("Primera review:", data[0]["review_text"][:120])

    return data


def save_reviews(reviews):
    df_new = pd.DataFrame(reviews) # convierte la lista de reviews a un DataFrame de pandas

    if os.path.exists(OUTPUT_FILE): # si el archivo ya existe, carga lo anterior y concatena
        df_old = pd.read_csv(OUTPUT_FILE)
        df_old = df_old.drop(columns=["id"], errors="ignore")
        df_total = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_total = df_new.copy()

    df_total.drop_duplicates(subset=["review_text"], inplace=True) # elimina duplicados basándose solo en el texto de la review así evita guardar varias veces la misma reseña
    df_total = df_total.reset_index(drop=True) 
    df_total["id"] = range(1, len(df_total) + 1)

    cols = ["id"] + [col for col in df_total.columns if col != "id"]
    df_total = df_total[cols]

    df_total.to_csv(OUTPUT_FILE, index=False, encoding="utf-8")
    print("Total guardadas:", len(df_total))


if __name__ == "__main__":
    # conecta Selenium al Chrome ya abierto en modo debug
    driver = connect_to_chrome()
    print("Conectado a Chrome")

    # abre directamente la página de reviews de Vueling en TripAdvisor
    driver.get("https://www.tripadvisor.es/Airline_Review-d8729185-Reviews-Vueling-Airlines")

    while True: # bucle para scrapear varias páginas manualmente
        input("\nPulsa ENTER para scrapear esta página")
        reviews = extract_reviews(driver)
        save_reviews(reviews)

        next_page = input("\n'n' para ir a la siguiente página o ENTER para terminar: ")
        if next_page != "n":
            break

        print("Ve al navegador y pulsa Next page")
        input("Pulsa ENTER cuando cargue")

    driver.quit()