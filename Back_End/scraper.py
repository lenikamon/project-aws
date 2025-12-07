
import os
import re
import requests
import time
import sys
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import tempfile
import pymupdf4llm 
import pymupdf4llm.layout

# --- CONFIGURACIÓN Y LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "https://cc.unison.mx/"
OUTPUT_FOLDER = os.path.join("Back_End", "Data", "texts")
MAX_PAGINAS = 500

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
}

# Conjunto para rastrear URLs visitadas y evitar bucles
visitados = set()

# --- FUNCIONES CORE ---

def obtener_html(url: str) -> BeautifulSoup | None:
    """Intenta obtener el HTML de la URL dada."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()  # Genera una excepción para códigos 4xx/5xx
        return BeautifulSoup(r.text, "html.parser")
    except requests.exceptions.RequestException as e:
        logger.warning(f"Error HTTP/Conexión al obtener {url}: {e}")
        return None


def formatear_nombre(url: str) -> str:
    """Convierte la URL a un nombre de archivo seguro y conciso."""
    nombre = url.replace(BASE_URL, "")
    nombre = re.sub(r'[^a-zA-Z0-9_-]', "_", nombre)
    return nombre[:80] if nombre else "index"


def guardar_texto(nombre: str, texto: str):
    """Guarda el texto extraído en la carpeta de salida."""
    if len(texto.strip()) < 20:
        return

    path = os.path.join(OUTPUT_FOLDER, f"{nombre}.txt")

    if os.path.exists(path):
        logger.debug(f"Archivo ya existe, ignorado: {nombre}")
        return

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(texto)
        logger.info(f"Guardado: {path}")
    except IOError as e:
        logger.error(f"Error al escribir el archivo {nombre}: {e}")


def procesar_pdf(url: str):
    """Descarga y extrae texto de un PDF usando pymupdf4llm."""
    logger.info(f"Procesando PDF: {url}")

    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()

        nombre = formatear_nombre(url)

        # Usar un archivo temporal para el procesamiento
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(r.content)
            tmp_path = tmp.name

        # Extraer texto usando la librería optimizada
        texto = pymupdf4llm.to_text(tmp_path)
        
        guardar_texto(nombre, texto)

        os.remove(tmp_path) # Limpiar el archivo temporal

    except requests.exceptions.RequestException:
        logger.warning("No se pudo descargar el PDF (Error HTTP/Timeout).")
    except Exception as e:
        logger.error(f"Error procesando PDF {url}: {e}")


def procesar_html(url: str, soup: BeautifulSoup):
    """Extrae texto de la página HTML."""
    texto = soup.get_text("\n", strip=True)
    nombre = formatear_nombre(url)
    guardar_texto(nombre, texto)


def obtener_links(soup: BeautifulSoup, url_actual: str) -> list[str]:
    """Extrae todos los enlaces válidos para rastrear."""
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()

        # Ignorar anclas internas o enlaces vacíos
        if not href or href.startswith(('#', 'mailto:', 'tel:')):
            continue

        link = urljoin(url_actual, href)

        # Solo rastrear enlaces dentro del dominio base y que no sean anclas internas
        if link.startswith(BASE_URL) and "#" not in link[len(BASE_URL):]:
            links.append(link)

    return links


def crawl(url: str):
    """Lógica recursiva del rastreador."""
    if url in visitados:
        return

    if len(visitados) >= MAX_PAGINAS:
        return

    # Limpieza de URL para evitar repeticiones por anclas
    clean_url = url.split('#')[0]

    if clean_url in visitados:
        return
        
    logger.info(f"Visitando: {clean_url} (Páginas visitadas: {len(visitados)})")
    visitados.add(clean_url)

    if clean_url.lower().endswith(".pdf"):
        procesar_pdf(clean_url)
        return

    soup = obtener_html(clean_url)
    if not soup:
        return

    procesar_html(clean_url, soup)

    nuevos_links = obtener_links(soup, clean_url)

    for link in nuevos_links:
        crawl(link)
        time.sleep(0.1) # Pausa breve para evitar bloqueo

def main():
    """Punto de entrada principal para el rastreo de datos."""
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    logger.info("Iniciando rastreo del sitio web de la UNISON...")
    try:
        crawl(BASE_URL)
    except RecursionError:
        logger.error("Rastreo detenido: Se alcanzó el límite de recursión de Python. Use un proceso asíncrono o aumente el límite de recursión (sys.setrecursionlimit).")
        
    logger.info(f"Rastreo completado. Total de páginas únicas procesadas: {len(visitados)}")

if __name__ == "__main__":
    main()