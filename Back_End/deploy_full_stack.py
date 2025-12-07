# scripts/deploy_full_stack.py
# Modulo de orquestacion para la limpieza, creacion de artefactos RAG y el despliegue
# completo del Proxy Gemini en AWS SageMaker.

import os
import sys
import time
import subprocess
import logging
import boto3
from dotenv import load_dotenv
from cleaner import main as clean_data_main
from rag_creator import create_chroma_db_artifact
# --- IMPORTS DE DESPLIEGUE ---
import sagemaker
from sagemaker.huggingface import HuggingFaceModel



# --- 1. CONFIGURACIÓN INICIAL ---

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv('vars.env') 

# Carga de variables críticas
S3_BUCKET = os.environ.get("S3_BUCKET_NAME")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ENDPOINT_NAME = f'gemini-proxy-{time.strftime("%Y%m%d-%H%M%S")}'
DB_ZIP_S3_KEY = 'rag-artifacts/chroma_db.zip'
CODE_ZIP_DIR = os.path.join('model_deploy_proxy', 'code')

# Obtener la región de la sesión de SageMaker
SESS = sagemaker.Session()
AWS_REGION = SESS.boto_region_name

# --- 2. FUNCIONES DE AWS CORE ---

def create_s3_bucket(bucket_name: str, region: str):
    """Verifica si el bucket existe, y lo crea si es necesario."""
    s3_client = boto3.client('s3', region_name=region)
    
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        logger.info(f"El Bucket '{bucket_name}' ya existe. Continuando.")
    except Exception as e:
        logger.info(f"El Bucket '{bucket_name}' no existe. Creándolo en la región {region}...")
        try:
            if region == 'us-east-1':
                s3_client.create_bucket(Bucket=bucket_name)
            else:
                s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': region}
                )
            logger.info(f"Bucket '{bucket_name}' creado con éxito.")
        except Exception as create_error:
            logger.error(f"Error fatal al crear el bucket: {create_error}")
            sys.exit(1)


def upload_rag_artifacts_to_s3(db_zip_name: str, bucket: str) -> str:
    """Sube el archivo ZIP de ChromaDB y el código del Proxy a S3."""
    logger.info("Iniciando carga de artefactos a S3...")
    s3_client = boto3.client('s3')
    
    # 1. Subir ChromaDB ZIP
    SESS.upload_data(path=db_zip_name, bucket=bucket, key_prefix='rag-artifacts')
    logger.info(f"ChromaDB ZIP subido a s3://{bucket}/{DB_ZIP_S3_KEY}")
    
    # 2. Empaquetar el código del Proxy
    logger.info("Empaquetando código del Proxy (inference/requirements)...")
    
    if not os.path.exists(CODE_ZIP_DIR):
        os.makedirs(CODE_ZIP_DIR)
        
    
    subprocess.run(['cp', 'gemini_proxy.py', os.path.join(CODE_ZIP_DIR, 'inference.py')], check=True)
    
    subprocess.run(['cp', 'requirements.txt', CODE_ZIP_DIR], check=True)

    subprocess.run(['tar', '-czvf', 'model_proxy.tar.gz', '-C', 'model_deploy_proxy', 'code'], check=True)

    # 3. Subir el paquete de código
    model_uri = SESS.upload_data(path='model_proxy.tar.gz', bucket=bucket, key_prefix='rag-code-proxy')
    logger.info(f"Paquete de código subido a: {model_uri}")
    
    return model_uri
def deploy_sagemaker_proxy(model_uri: str, bucket: str, api_key: str) -> str:
    """Despliega el Endpoint de SageMaker con las variables de entorno de Gemini."""
    logger.info(f"Lanzando Endpoint Proxy SageMaker: {ENDPOINT_NAME}")
    
    role = sagemaker.get_execution_role()
    
    huggingface_model = HuggingFaceModel(
        model_data=model_uri,
        role=role,
        transformers_version="4.37.0",
        pytorch_version="2.1.0",
        py_version="py310",
        env={ 
            'GEMINI_API_KEY': api_key, 
            'S3_BUCKET': bucket,
            'DB_ZIP_KEY': DB_ZIP_S3_KEY,
            'HF_TASK': 'text-generation',
            'SAGEMAKER_MODEL_SERVER_WORKERS': '1',
        }
    )

    predictor = huggingface_model.deploy(
        initial_instance_count=1,
        instance_type="ml.m5.xlarge", 
        endpoint_name=ENDPOINT_NAME,
        wait=False
    )
    
    logger.info(f"Despliegue de Endpoint iniciado. Nombre: {ENDPOINT_NAME}")
    return ENDPOINT_NAME

# --- 3. ORQUESTACIÓN PRINCIPAL ---

def main():
    logger.info("--- INICIO: DESPLIEGUE RAG PORTABLE ---")
    
    # Validaciones iniciales
    if not S3_BUCKET or not GEMINI_API_KEY:
        logger.error("ERROR: Variables de entorno AWS (S3_BUCKET_NAME) o GEMINI (GEMINI_API_KEY) faltantes. Revise vars.env.")
        sys.exit(1)

    # 1. Crear S3 Bucket
    create_s3_bucket(S3_BUCKET, AWS_REGION)
    
    # 2. Limpieza y Creación de Artefactos RAG
    clean_data_main(input_folder=os.path.join('Back_End','Data', 'texts'), output_folder=os.path.join('Back_End', 'Data', 'Clean_Text'))
    db_zip_name = create_chroma_db_artifact(clean_folder=os.path.join('Back_End', 'Data', 'Clean_Text'))

    # 3. Subir a S3 y Empaquetar el Código del Proxy
    code_uri = upload_rag_artifacts_to_s3(db_zip_name, S3_BUCKET)

    # 4. Desplegar SageMaker Endpoint (Proxy Gemini)
    endpoint_name = deploy_sagemaker_proxy(code_uri, S3_BUCKET, GEMINI_API_KEY)
    
    logger.info("\n--- PROCESO DE BACKEND FINALIZADO ---")
    logger.info(f"Endpoint de SageMaker listo: {endpoint_name}")
    logger.info("El despliegue del Endpoint puede tardar 5-10 minutos. Revisa la consola de SageMaker.")

if __name__ == "__main__":
    main()