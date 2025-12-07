
-----

#  Projecto AWS - CHATBOT LCC

Plataforma web con un chatbot inteligente que responde preguntas sobre información institucional específicamente sobre la Licenciatura en Ciencias de la Computación de la Universidad de Sonora usando IA generativa y RAG, desplegada en AWS con API Gateway, SageMaker y Amplify, e integrada con Cognito para autenticación.

## I.  Adquisición de Datos y Despliegue del Proxy

Esta fase asegura que los datos estén limpios, vectorizados y el **Proxy RAG** esté alojado en **SageMaker**.

### 1\. Documentos del RAG (S3 y Proceso Local)

El proceso de ingesta local es fundamental para la calidad del RAG.

  * **Adquisición de Datos:** El script **`Back_End/scraper.py`** se utiliza para la adquisición inicial de PDFs/HTML, guardándolos en `Back_End/Data/texts`.
  * **Limpieza y Vectorización:** El script **`Back_End/deploy_full_stack.py`** ejecuta automáticamente la limpieza (`cleaner.py`), la vectorización (`rag_creator.py`), la creación del **Bucket S3** (si no existe), y sube los artefactos (el ZIP de la base de datos vectorial).

### 2\. Creación de Endpoint de SageMaker (El Proxy RAG)

El Endpoint aloja tu código de inferencia (`gemini_proxy.py`) que maneja la búsqueda RAG y la llamada de baja latencia a la API de Gemini.

| Opción | Comando Principal | Obtención del ENDPOINT\_NAME  |
| :--- | :--- | :--- |
| **Opción A: AUTOMÁTICA** | **`python Back_End/deploy_full_stack.py`** (Se ejecuta desde la carpeta `Back_End`) | El script inicia el despliegue. Copiar el nombre generado desde la consola de SageMaker una vez que el estado sea **`InService`**. |
| **Opción B: MANUAL** | Ejecutar la última celda de despliegue en **`Notebook del Proyecto.ipynb`** (en SageMaker). | Copiar el nombre de la variable `predictor.endpoint_name` de la salida de la Notebook. |

-----

## II.  Conexión de Servicios y Exposición Pública

Una vez que el Endpoint de SageMaker está **`InService`**, se configuran los *serverless* para la conectividad.

### 3\. Backend: AWS Lambda (`RAG_Backend`)

La Lambda actúa como el ***bridge* seguro** de comunicación entre el API Gateway y el Endpoint de SageMaker.

1.  **Crear Función:** Crear la función **`RAG_Backend`** (Runtime Python 3.12).
2.  **Subir Código:** Subir el contenido del archivo **`Back_End/Lambda_Handler.py`** como código de la función.
3.  **Permisos:** El **Rol de IAM** de la Lambda debe tener la política **`AmazonSageMakerRuntimeAccess`**.
4.  **Inyección del Endpoint :** Agregar la variable de entorno:
      * **Clave:** `ENDPOINT_NAME`
      * **Valor:** Pega el nombre del Endpoint de SageMaker copiado en el Paso 2.

### 4\. Lambda + API Gateway (Exposición Pública)

Conectar la función Lambda con una **API Gateway** para obtener una URL pública HTTPS.

1.  Acceder a **API Gateway** y dar clic en **Create API**.
2.  Elegir **HTTP API** (más simple).
3.  **Integración:** Crear una integración con la Lambda: `Integration type: Lambda` → `Lambda: RAG_Backend`.
4.  **Ruta:** Crear la ruta `Method: POST` en `Path: /chat`.
5.  **CORS:** Habilitar CORS (`Allow Origins: *`, `Allow Methods: OPTIONS, POST`).
6.  **Deploy API** y **Copiar la URL resultante**.

-----

## III.  Frontend y Seguridad

### 5\. Página Web (AWS Amplify)

El frontend se encarga de la interfaz y la comunicación con el API.

1.  **Conectar HTML:** Abrir el archivo **`Front_End/index.html`** y reemplazar la variable `API_GATEWAY_URL` con la URL copiada en el Paso 4.
2.  **Subir a Amplify:** Subir la carpeta **`Front_End`** a **AWS Amplify** para el *hosting*.
      * *Amplify se encarga de:* Desplegar, hostear la página y proveer una URL pública.

### 6\. Seguridad (AWS Cognito)

**AWS Cognito** proporciona autenticación y gestión de usuarios para la aplicación.

1.  **Crear User Pool:** Crea un **User Pool** para definir los atributos de usuario (email, nombre, etc.).
2.  **Crear App Client:** Crea un **App Client** para generar los identificadores necesarios.
3.  **Implementación Web:** La lógica de *login* y *registro* se implementa en el Frontend usando los SDK de Cognito.

-----

**Link de Ejemplo:** [https://staging.d3503m3mxp9bxi.amplifyapp.com/?code=a541d8ac-7f6f-4834-b389-f38c61889363](https://staging.d3503m3mxp9bxi.amplifyapp.com/?code=a541d8ac-7f6f-4834-b389-f38c61889363)
