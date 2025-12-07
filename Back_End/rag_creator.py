
import os
import sys
import zipfile
import shutil
import glob

# --- PARCHE CRÍTICO PARA SQLITE ---
__import__('pysqlite3')
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

# --- IMPORTS DE RAG ---
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

# --- CONFIGURACIÓN ---
CLEAN_FOLDER = os.path.join('Back_End', 'Data', 'Clean_Text')
DB_PERSIST_PATH = 'chroma_db_local'
ARTIFACT_NAME = 'chroma_db.zip'

def create_chroma_db_artifact(clean_folder: str = CLEAN_FOLDER, output_artifact_name: str = ARTIFACT_NAME):
    """
    Carga los documentos limpios, crea la DB ChromaDB y la comprime en un archivo ZIP.
    Retorna el nombre del archivo ZIP creado.
    """
    try:
        # --- 1. CARGAR Y DIVIDIR DOCUMENTOS ---
        print("Cargando archivos de texto limpio...")
        loader = DirectoryLoader(clean_folder, glob="*.txt", loader_cls=TextLoader)
        docs_raw = loader.load()

        if not docs_raw:
            print(f"Error: No se encontraron archivos en '{clean_folder}'. Saliendo.")
            return None

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=3000, chunk_overlap=300)
        docs = text_splitter.split_documents(docs_raw)
        
        # --- 2. CREAR EMBEDDINGS ---
        print("Generando Embeddings y creando ChromaDB...")
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        
        if os.path.exists(DB_PERSIST_PATH):
            shutil.rmtree(DB_PERSIST_PATH)
        
        Chroma.from_documents(
            documents=docs, 
            embedding_function=embeddings,
            persist_directory=DB_PERSIST_PATH
        )
        
        # --- 3. COMPRIMIR LA DB ---
        print(f"Comprimiendo base de datos en {output_artifact_name}...")
        
        with zipfile.ZipFile(output_artifact_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(DB_PERSIST_PATH):
                for file in files:
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, os.path.relpath(file_path, DB_PERSIST_PATH))
        
        # Limpiar la carpeta local
        shutil.rmtree(DB_PERSIST_PATH)
        
        print(f"Artefacto RAG creado con éxito: {output_artifact_name}")
        return output_artifact_name

    except Exception as e:
        print(f"Error al crear el artefacto RAG: {e}")
        sys.exit(1)

if __name__ == "__main__":
    create_chroma_db_artifact()