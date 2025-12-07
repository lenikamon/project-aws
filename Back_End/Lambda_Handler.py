# Back_End/lambda_handler.py
# Código que será comprimido y subido a AWS Lambda.

import json
import boto3
import os
import logging

# Configuración de Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# El nombre del Endpoint se lee desde las variables de entorno de la Lambda
ENDPOINT_NAME = os.environ.get('ENDPOINT_NAME') 
runtime = boto3.client('sagemaker-runtime')

def lambda_handler(event, context):
    """
    Función principal de Lambda que invoca el Endpoint de SageMaker.
    """
    # --- 1. CONFIGURACIÓN CORS ---
    headers = {
        "Access-Control-Allow-Origin": "*", 
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "OPTIONS,POST,GET"
    }
    
    # Manejo de la solicitud CORS "preflight" (OPTIONS)
    if event.get('httpMethod') == 'OPTIONS':
        return {'statusCode': 200, 'headers': headers, 'body': json.dumps('CORS OK')}
    
    try:
        # 2. Leer la pregunta
        body_str = event.get('body', '{}')
        body = json.loads(body_str) if isinstance(body_str, str) else body_str
        pregunta = body.get('question', '') or body.get('inputs', '')
        
        if not pregunta:
            return {'statusCode': 400, 'headers': headers, 'body': json.dumps({'error': 'Falta la pregunta'})}

        # 3. Preparar payload para SageMaker
        payload = {"inputs": pregunta}
        
        # 4. Invocar al Endpoint de SageMaker
        response = runtime.invoke_endpoint(
            EndpointName=ENDPOINT_NAME,
            ContentType='application/json',
            Body=json.dumps(payload)
        )
        
        # 5. Procesar respuesta del Endpoint Proxy
        result = json.loads(response['Body'].read().decode())
        texto_respuesta = result[0].get('generated_text', 'Respuesta no válida del Endpoint.')

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({'answer': texto_respuesta})
        }

    except Exception as e:
        logger.error(f"Error al invocar SageMaker: {str(e)}")
        # Devuelve un 500 con el error para el frontend
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': f'Error interno del servicio RAG. Revise logs.'})
        }