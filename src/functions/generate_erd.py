import json
import os
import uuid
import logging
import pathlib
import boto3
from diagrams import Diagram, Edge
from diagrams.aws.compute import EC2
from diagrams.aws.network import VPC
from diagrams.aws.database import RDS
from diagrams.aws.storage import S3
from diagrams.onprem.database import PostgreSQL, MySQL
from diagrams.onprem.network import Internet
from diagrams.onprem.compute import Server
from diagrams.gcp.compute import ComputeEngine
from diagrams.gcp.network import Network
from diagrams.gcp.database import SQL
from diagrams.azure.compute import VirtualMachine
from diagrams.azure.network import VirtualNetwork
from diagrams.azure.database import SQLDatabase
from eralchemy import render_er

# Configuración del logger
logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO').upper())
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Inicializar cliente S3
s3 = boto3.client('s3')

# Bucket S3 para almacenar diagramas
DIAGRAM_BUCKET = "diagrams-bucket-hackathon"

def _create_secure_globals(diagram_type):
    """Crea un diccionario de globales seguro para la ejecución de código dinámico."""
    secure_globals = {
        '__builtins__': {
            'min': min,
            'max': max,
            'sum': sum,
            'len': len,
            'dict': dict,
            'list': list,
            'tuple': tuple,
            'set': set,
            'str': str,
            'int': int,
            'float': float,
            'bool': bool,
            'None': None,
            'True': True,
            'False': False,
            'range': range,
            'zip': zip,
            'map': map,
            'filter': filter,
            'abs': abs,
            'round': round,
            'pow': pow,
            'divmod': divmod,
            'isinstance': isinstance,
            'issubclass': issubclass,
            'Exception': Exception,
            'TypeError': TypeError,
            'ValueError': ValueError,
            'KeyError': KeyError,
            'AttributeError': AttributeError,
            'IndexError': IndexError,
            'StopIteration': StopIteration,
            'enumerate': enumerate,
            'sorted': sorted,
            'all': all,
            'any': any,
            'next': next,
            'iter': iter,
            'hasattr': hasattr,
            'getattr': getattr,
            'setattr': setattr,
            'delattr': delattr,
            'callable': callable,
            'repr': repr,
            'hash': hash,
            'id': id,
            'format': format,
            'frozenset': frozenset,
            'memoryview': memoryview,
            'bytearray': bytearray,
            'bytes': bytes,
            'complex': complex,
            'super': super,
            'property': property,
            'classmethod': classmethod,
            'staticmethod': staticmethod,
            'object': object,
            'type': type,
            'print': print
        },
        'Diagram': Diagram,
        'Edge': Edge,
        '__name__': '__main__'
    }

    if diagram_type == 'aws':
        secure_globals.update({
            'EC2': EC2,
            'VPC': VPC,
            'RDS': RDS,
            'S3': S3
        })
    elif diagram_type == 'gcp':
        secure_globals.update({
            'ComputeEngine': ComputeEngine,
            'Network': Network,
            'SQL': SQL
        })
    elif diagram_type == 'azure':
        secure_globals.update({
            'VirtualMachine': VirtualMachine,
            'VirtualNetwork': VirtualNetwork,
            'SQLDatabase': SQLDatabase
        })
    elif diagram_type == 'onprem':
        secure_globals.update({
            'PostgreSQL': PostgreSQL,
            'MySQL': MySQL,
            'Internet': Internet,
            'Server': Server
        })
    elif diagram_type == 'erd':
        secure_globals.update({
            'render_er': render_er
        })
    
    return secure_globals

def generate_diagram_image(user_code, diagram_type, output_format='png'):
    """Genera un diagrama a partir del código del usuario y lo sube a S3."""
    unique_id = str(uuid.uuid4())
    output_name = f"diagram_{unique_id}"
    output_path = pathlib.Path(f"/tmp/{output_name}")

    if diagram_type == 'erd':
        # Para ERD, user_code es la cadena de conexión de la base de datos
        db_connection_string = user_code
        try:
            render_er(db_connection_string, f"{output_path}.{output_format}")
            logger.info(f"ERD generated at {output_path}.{output_format}")
        except Exception as e:
            logger.error(f"Error generating ERD: {e}")
            raise ValueError(f"Error generating ERD: {e}")
    else:
        # Para otros tipos de diagramas (AWS, GCP, Azure, On-Premise)
        secure_globals = _create_secure_globals(diagram_type)
        local_vars = {}
        try:
            exec(user_code, secure_globals, local_vars)
            
            # Asume que el código del usuario define un objeto Diagram llamado 'graph'
            graph = local_vars.get('graph')
            if not graph:
                raise ValueError("User code must define a 'Diagram' object named 'graph'.")

            graph.render(output_path, format=output_format, cleanup=True)
            logger.info(f"Diagram generated at {output_path}.{output_format}")
        except Exception as e:
            logger.error(f"Error executing user code or generating diagram: {e}")
            raise ValueError(f"Error executing user code or generating diagram: {e}")

    # Subir el diagrama a S3
    s3_key = f"diagrams/{output_name}.{output_format}"
    try:
        s3.upload_file(f"{output_path}.{output_format}", DIAGRAM_BUCKET, s3_key)
        diagram_url = f"https://{DIAGRAM_BUCKET}.s3.amazonaws.com/{s3_key}"
        logger.info(f"Diagram uploaded to S3: {diagram_url}")
    except Exception as e:
        logger.error(f"Error uploading diagram to S3: {e}")
        raise IOError(f"Error uploading diagram to S3: {e}")

    # Subir el código fuente a S3
    source_code_key = f"source_codes/{output_name}.py"
    try:
        s3.put_object(Bucket=DIAGRAM_BUCKET, Key=source_code_key, Body=user_code.encode('utf-8'))
        source_code_url = f"https://{DIAGRAM_BUCKET}.s3.amazonaws.com/{source_code_key}"
        logger.info(f"Source code uploaded to S3: {source_code_url}")
    except Exception as e:
        logger.error(f"Error uploading source code to S3: {e}")
        raise IOError(f"Error uploading source code to S3: {e}")

    return diagram_url, source_code_url

def create(event, context):
    """Función principal de Lambda para generar diagramas."""
    try:
        body = json.loads(event['body'])
        user_code = body.get('user_code')
        diagram_type = body.get('diagram_type')
        output_format = body.get('output_format', 'png')

        if not user_code or not diagram_type:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing user_code or diagram_type in request body.'})
            }

        diagram_url, source_code_url = generate_diagram_image(user_code, diagram_type, output_format)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Diagram generated and uploaded successfully!',
                'diagram_url': diagram_url,
                'source_code_url': source_code_url
            })
        }
    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body.")
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid JSON in request body.'})
        }
    except ValueError as ve:
        logger.error(f"Validation error: {ve}")
        return {
            'statusCode': 400,
            'body': json.dumps({'error': str(ve)})
        }
    except IOError as ioe:
        logger.error(f"File operation error: {ioe}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f"File operation error: {ioe}"})
        }
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f"An unexpected error occurred: {e}"})
        }