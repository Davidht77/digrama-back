import json
import boto3
import os
import uuid
import logging
from pathlib import Path

# --- Librerías que el usuario puede usar en su código ---
# Importamos todo lo que queremos exponer al código del usuario.
# Esto es parte de nuestra "sandbox" de seguridad.
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import EC2, Lambda, EKS
from diagrams.aws.database import RDS, DynamoDB
from diagrams.aws.network import ELB, APIGateway, Route53
from diagrams.aws.storage import S3
from diagrams.gcp.compute import ComputeEngine, KubernetesEngine
from diagrams.gcp.database import SQL, BigQuery
from diagrams.gcp.network import LoadBalancing, Vpc
from diagrams.azure.compute import VirtualMachine, KubernetesServices
from diagrams.azure.database import SQLDatabase, CosmosDb
from diagrams.azure.network import ApplicationGateway, VirtualNetworks
from diagrams.onprem.compute import Server
from diagrams.onprem.database import PostgreSQL, MongoDB
from diagrams.onprem.network import Nginx

# Configuración del logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Cliente de S3 y nombre del bucket desde las variables de entorno
S3_BUCKET_NAME = os.environ.get("DIAGRAMS_BUCKET")
s3 = boto3.client("s3")


def _create_secure_globals(diagram_type):
    """
    Crea un diccionario 'globals' seguro para la función exec()
    basado en el tipo de diagrama.
    """
    safe_modules = {
        "Diagram": Diagram,
        "Cluster": Cluster,
        "Edge": Edge,
    }

    if diagram_type == "aws":
        from diagrams.aws.compute import EC2, Lambda, EKS
        from diagrams.aws.database import RDS, DynamoDB
        from diagrams.aws.network import ELB, APIGateway, Route53
        from diagrams.aws.storage import S3
        safe_modules.update({
            "EC2": EC2,
            "Lambda": Lambda,
            "EKS": EKS,
            "RDS": RDS,
            "DynamoDB": DynamoDB,
            "ELB": ELB,
            "APIGateway": APIGateway,
            "Route53": Route53,
            "S3": S3,
        })
    elif diagram_type == "gcp":
        from diagrams.gcp.compute import ComputeEngine, KubernetesEngine
        from diagrams.gcp.database import SQL, BigQuery
        from diagrams.gcp.network import LoadBalancing, Vpc
        safe_modules.update({
            "ComputeEngine": ComputeEngine,
            "KubernetesEngine": KubernetesEngine,
            "SQL": SQL,
            "BigQuery": BigQuery,
            "LoadBalancing": LoadBalancing,
            "Vpc": Vpc,
        })
    elif diagram_type == "azure":
        from diagrams.azure.compute import VirtualMachine, KubernetesServices
        from diagrams.azure.database import SQLDatabase, CosmosDb
        from diagrams.azure.network import ApplicationGateway, VirtualNetworks
        safe_modules.update({
            "VirtualMachine": VirtualMachine,
            "KubernetesServices": KubernetesServices,
            "SQLDatabase": SQLDatabase,
            "CosmosDb": CosmosDb,
            "ApplicationGateway": ApplicationGateway,
            "VirtualNetworks": VirtualNetworks,
        })
    elif diagram_type == "onprem":
        from diagrams.onprem.compute import Server
        from diagrams.onprem.database import PostgreSQL, MongoDB
        from diagrams.onprem.network import Nginx
        safe_modules.update({
            "Server": Server,
            "PostgreSQL": PostgreSQL,
            "MongoDB": MongoDB,
            "Nginx": Nginx,
        })
    else:
        raise ValueError(f"Tipo de diagrama no soportado: {diagram_type}")

    return {"__builtins__": {}}, safe_modules


def generate_diagram_image(source_code, diagram_id, diagram_type):
    """
    Ejecuta el código fuente de 'diagrams' en un entorno controlado,
    genera la imagen del diagrama, y la sube a S3.
    """
    # Directorio temporal de Lambda, el único lugar donde podemos escribir archivos.
    tmp_dir = Path("/tmp") / diagram_id
    tmp_dir.mkdir(exist_ok=True)

    # Cambiamos al directorio temporal para que la librería 'diagrams'
    # genere el archivo de imagen aquí.
    original_cwd = os.getcwd()
    os.chdir(tmp_dir)

    generated_file = None
    try:
        # Ejecutar el código del usuario en un entorno restringido
        logger.info(f"Ejecutando código de diagrama para {diagram_id}")
        safe_globals, safe_locals = _create_secure_globals(diagram_type)
        exec(source_code, safe_globals, safe_locals)
        logger.info("Ejecución de código completada.")

        # Buscar el archivo de imagen generado (PNG por defecto)
        output_files = list(tmp_dir.glob("*.png"))
        if not output_files:
            raise RuntimeError(
                "El código se ejecutó pero no se generó ningún archivo de diagrama (.png)."
            )
        generated_file = output_files[0]
        logger.info(f"Archivo de diagrama generado: {generated_file.name}")

        # Definir las rutas (keys) en S3
        diagram_key = f"{diagram_type}/{diagram_id}/{generated_file.name}"
        source_key = f"{diagram_type}/{diagram_id}/source.py"

        # Subir el diagrama generado a S3
        s3.upload_file(str(generated_file), S3_BUCKET_NAME, diagram_key)
        logger.info(f"Diagrama subido a s3://{S3_BUCKET_NAME}/{diagram_key}")

        # Subir el código fuente original a S3
        s3.put_object(
            Bucket=S3_BUCKET_NAME, Key=source_key, Body=source_code
        )
        logger.info(f"Código fuente subido a s3://{S3_BUCKET_NAME}/{source_key}")

        return diagram_key, source_key

    finally:
        # Limpieza: eliminar archivos y directorio temporal
        if generated_file and generated_file.exists():
            generated_file.unlink()
        if tmp_dir.exists():
            tmp_dir.rmdir()
        # Restaurar el directorio de trabajo original
        os.chdir(original_cwd)


def generate_flowchart(event, context):
    """
    Punto de entrada de la API. Recibe el código y el tipo,
    y devuelve las URLs de los artefactos generados.
    """
    try:
        body = json.loads(event.get("body", "{}"))
        diagram_type = body.get("type")
        source_code = body.get("source")

        if not diagram_type or not source_code:
            return {
                "statusCode": 400,
                "body": json.dumps(
                    {"error": "Faltan los campos 'type' y 'source' en el body."}
                ),
            }

        # Validar el tipo de diagrama
        supported_diagram_types = ["aws", "gcp", "azure", "onprem"]
        if diagram_type not in supported_diagram_types:
            return {
                "statusCode": 400,
                "body": json.dumps(
                    {"error": f"Tipo de diagrama '{diagram_type}' no soportado. Los tipos soportados son: {', '.join(supported_diagram_types)}."}
                ),
            }

        diagram_id = str(uuid.uuid4())
        diagram_key, source_key = generate_diagram_image(source_code, diagram_id, diagram_type)

        # Construir las URLs de acceso público a los objetos de S3
        region = os.environ.get("AWS_REGION")
        diagram_url = f"https://{S3_BUCKET_NAME}.s3.{region}.amazonaws.com/{diagram_key}"
        source_url = f"https://{S3_BUCKET_NAME}.s3.{region}.amazonaws.com/{source_key}"

        return {
            "statusCode": 201,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "message": f"Diagrama de {diagram_type.upper()} creado exitosamente.",
                    "diagramId": diagram_id,
                    "diagramUrl": diagram_url,
                    "sourceUrl": source_url,
                }
            ),
        }

    except Exception as e:
        logger.error(f"Error inesperado: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Error interno del servidor: {str(e)}"}),
        }