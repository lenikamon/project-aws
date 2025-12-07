import os
import re
import html
import sys

# --- 1. CONFIGURACIÓN DE CARPETAS Y CONSTANTES ---

INPUT_FOLDER = os.path.join('Back_End','Data', 'texts')
OUTPUT_FOLDER = os.path.join('Back_End', 'Data', 'Clean_Text')

# Generamos una lista negra combinada para la limpieza inicial masiva
LISTA_NEGRA_COMBINADA = [
    "Skip to content", "Top Menu", "Top Menú", "Main Menu", "MENÚ",
    "Inicio", "UNISON", "DEPARTAMENTO", "FACULTAD",
    "ACERCA DEL PROGRAMA", "INFORMACIÓN PARA ALUMNOS", "ADMISIÓN",
    "DOCENTES", "EDITORIAL", "NOTICIAS Y AVISOS", 
    "NOTICIAS Y AVISOS ANTERIORES", "Previous", "Next",
    "Conócenos", "Misión y Visión", "Plan de Estudios", "Requisitos",
    "Egreso", "Titulación", "Idioma", "Servicio Social", "CENEVAL",
    "Culturest", "Prácticas Profesionales", "Programa", "Alumnos",
    "Ingreso", "Plan de Estudios 2025-2", "Plan de Estudios 2005-2",
    "Tesis", "LCC-HUB", "Reestructuración LCC", "Licenciatura en Ciencias de la Computación",
    "AI-Linkup", "Banner Reestructuración LCC", "25 Aniversario LCC",
    "Departamento de Matemáticas", "Universidad de Sonora",
    "Presentación", "Directorio", "Trayectorias Escolares", "Tutorías",
    "-->" 
]

INDICADORES_CODIGO = [
    "body{", "img.emoji", "img.wp-smiley", ".recentcomments", 
    "!function", "window._wpemoji", "var ", "$(document)", "$(\"#", 
    "owlCarousel", "function() {", "});",
    "!important", "box-shadow:", "height:", "width:", "margin:", 
    "vertical-align:", "padding:", "display:", "border:", "background:",
    ".wp-block-", ".has-", "autoPlay:", "items :", "itemsDesktop", 
    "itemsDesktopSmall", "//Set AutoPlay", "{"
]

INDICADORES_RUIDO_ESTRUCTURAL = [
    "==> picture", "----- Start of picture text", "----- End of picture text",
    "> [[|]]", "+-", "| Proyecto curricular", "| Elaboró:", 
    "| Bibliografía"
]

LISTA_NEGRA_LOWER = {item.lower() for item in LISTA_NEGRA_COMBINADA}

# --- FUNCIONES DE SOPORTE ---

def juntar_lineas_cortas(lineas_limpias: list[str]) -> list[str]:
    """Combina líneas cortas (menos de 60 caracteres) con la siguiente, si termina en coma o no alfanumérico."""
    texto_combinado = []
    i = 0
    while i < len(lineas_limpias):
        linea_actual = lineas_limpias[i]
        
        if len(linea_actual) < 60 and i + 1 < len(lineas_limpias):
            siguiente_linea = lineas_limpias[i+1]
            

            if (linea_actual.endswith(('.', ',', ':', ';')) or len(linea_actual) < 30) and siguiente_linea and siguiente_linea[0].islower():
                texto_combinado.append(linea_actual + ' ' + siguiente_linea)
                i += 2
                continue
                
        texto_combinado.append(linea_actual)
        i += 1
        
    return texto_combinado

# --- 3. FUNCIÓN DE LIMPIEZA---

def limpieza(texto: str) -> str:
    """Aplica las reglas de limpieza al texto dado."""
    if not texto: return ""

    texto = html.unescape(texto)
    # 1. Limpieza de comentarios y caracteres no deseados
    texto = re.sub(r'/\*.*?\*/', '', texto, flags=re.DOTALL) 
    
    lineas = texto.split('\n')
    lineas_limpias = []
    
    for linea in lineas:
        linea_strip = linea.strip()
        
        if not linea_strip:
            continue
            
        linea_lower = linea_strip.lower()
            
        # 2. Regla Anti-Código
        es_codigo = False
        for ind in INDICADORES_CODIGO:
            if ind in linea_strip:
                es_codigo = True
                break
        if "{" in linea_strip and "}" not in linea_strip and len(linea_strip) < 60: 
            es_codigo = True
        if linea_strip in ["});", "}", "-->"]:
            es_codigo = True

        if es_codigo:
            continue

        # 3. REGLA DE LISTA NEGRA ESTRICTA (Coincidencia de línea COMPLETA)
        if linea_lower in LISTA_NEGRA_LOWER:
            continue 

        # 4. Regla de Ruido Estructural/OCR y Footers
        es_ruido_estructural = False
        for ruido in INDICADORES_RUIDO_ESTRUCTURAL:
            if ruido.lower() in linea_lower and len(linea_strip) < len(ruido) + 30: 
                es_ruido_estructural = True
                break
        
        # Regla específica para el footer de la Unison
        if "universidad de sonora" in linea_lower and "|" in linea_strip:
            es_ruido_estructural = True
            
        # Paginación y filas de tabla
        if re.search(r'^\d+\s*\|\s*Proyecto curricular', linea_strip) or linea_strip.startswith('+---') or (linea_strip.startswith('| ') and all(c in '| +-.' for c in linea_strip)):
             es_ruido_estructural = True
            
        if es_ruido_estructural:
            continue
            
        # 5. Regla de longitud mínima
        if len(linea_strip) < 3 and not linea_strip[0].isalnum():
            continue

        lineas_limpias.append(linea_strip)

    # 6. POST-PROCESAMIENTO: Juntar líneas fragmentadas (opcional)
    lineas_fluidez = juntar_lineas_cortas(lineas_limpias)
    
    texto_final = "\n".join(lineas_fluidez)
    texto_final = re.sub(r'\n{3,}', '\n\n', texto_final) # Normalizar saltos de línea
    
    return texto_final

# --- 4. FUNCIÓN DE EJECUCIÓN  ---

def main(input_folder: str = INPUT_FOLDER, output_folder: str = OUTPUT_FOLDER):
    """Orquesta la limpieza de archivos desde la carpeta de entrada a la de salida."""
    try:
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            
        archivos = [f for f in os.listdir(input_folder) if f.endswith('.txt')]
        print(f"EJECUTANDO LIMPIEZA en {len(archivos)} archivos...")
        
        count = 0
        for filename in archivos:
            path_origen = os.path.join(input_folder, filename)
            path_destino = os.path.join(output_folder, filename)
            
            with open(path_origen, 'r', encoding='utf-8', errors='ignore') as f:
                contenido = f.read()
            
            limpio = limpieza(contenido)
            
            if len(limpio.strip()) > 30:
                with open(path_destino, 'w', encoding='utf-8') as f:
                    f.write(limpio)
                count += 1
                
        print(f"Limpieza terminada. {count} archivos procesados. Resultados en '{output_folder}'.")
        return output_folder

    except FileNotFoundError:
        print(f"Error: La carpeta de entrada '{input_folder}' no se encontró. Saliendo.")
        sys.exit(1)
    except Exception as e:
        print(f"Error al ejecutar la limpieza: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()