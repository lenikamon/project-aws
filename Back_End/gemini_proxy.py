# backend/gemini_proxy.py
# Modulo de inferencia para el Endpoint de SageMaker.

import os
import sys
import json
import boto3
import zipfile
import shutil
import time 

# Necesario para que ChromaDB funcione en el entorno de Linux de SageMaker.
__import__('pysqlite3')
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

# --- IMPORTS Y CONFIGURACIÓN ---
from google import genai
from google.genai import types
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma


GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY') 
BUCKET_NAME = os.environ.get('S3_BUCKET')
DB_ZIP_KEY = os.environ.get('DB_ZIP_KEY')

# MODELO CORREGIDO 
MODEL_NAME = 'gemini-2.5-flash' 
EXTRACT_PATH = '/tmp/chroma_db'

db_client = None 
gemini_client = None

def model_fn(model_dir):
    """
    Inicializa el sistema RAG (ChromaDB y Cliente Gemini).
    Esta función se ejecuta solo UNA VEZ al iniciar el Endpoint.
    """
    global db_client, gemini_client
    print("Iniciando Proxy Gemini en SageMaker...")
    
    if not GEMINI_API_KEY:
        raise EnvironmentError("ERROR: GEMINI_API_KEY no configurada. Verifique las variables de entorno.")

    # 1. Descargar y Cargar DB Chroma
    s3_client = boto3.client('s3')
    local_zip_path = '/tmp/chroma_db.zip'

    if os.path.exists(EXTRACT_PATH):
        shutil.rmtree(EXTRACT_PATH)
    os.makedirs(EXTRACT_PATH, exist_ok=True)
    
    s3_client.download_file(BUCKET_NAME, DB_ZIP_KEY, local_zip_path)
    
    # Descomprimir la DB
    with zipfile.ZipFile(local_zip_path, 'r') as zip_ref:
        zip_ref.extractall(EXTRACT_PATH)
    
    # Cargar Embeddings (el modelo HuggingFace corre localmente)
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    db_client = Chroma(persist_directory=EXTRACT_PATH, embedding_function=embeddings)
    
    # 2. Inicializar Cliente Gemini
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    
    print("Sistema RAG con Proxy Gemini listo.")
    return {"db": db_client, "gemini_client": gemini_client}


def predict_fn(data, context):
    """
    Ejecuta el ciclo RAG: Búsqueda de Contexto y Llamada al LLM.
    Esta función se ejecuta en CADA solicitud de la Lambda.
    """
    # 1. Recuperar artefactos inicializados
    db = context["db"]
    gemini = context["gemini_client"]

    # 2. Leer la pregunta del payload 
    if isinstance(data, list):
        input_data = data[0]
    else:
        input_data = data
        
    pregunta = input_data.get('inputs', input_data.get('question', '')) 
    
    if not pregunta:
        raise ValueError("Pregunta vacía recibida.")
        
    # 3. RAG: Búsqueda de contexto
    docs_encontrados = db.similarity_search(pregunta, k=7)
    contexto_acumulado = "\n".join([doc.page_content.replace('\n', ' ').strip() for doc in docs_encontrados])
    
    # 4. Prompt para Gemini (Formato Chat)
    prompt_final = f"""<|im_start|>system
Eres un asistente administrativo útil. Responde de forma muy concisa usando SOLO el siguiente contexto.
Reglas:
1. Responde usando SOLO el contexto.
2. Si la respuesta no está, di "No tengo información."
<|im_end|>
<|im_start|>user
Contexto:\n{contexto_acumulado}\n\nPregunta: {pregunta}
<|im_end|>
"""
    
    # 5. Llamar a la API de Gemini
    response = gemini.models.generate_content(
        model=MODEL_NAME,
        contents=[prompt_final],
        config=types.GenerateContentConfig(temperature=0.01)
    )
    
    texto_respuesta = response.text.strip()
    
    # 6. Devolver en el formato esperado por SageMaker/Lambda
    return [{"generated_text": texto_respuesta}]