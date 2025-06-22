# src/functions/generate_erd.py

import json
import os
import uuid
import logging
import pathlib
import boto3
from eralchemy import render_er
# ¡LA CORRECCIÓN! Importamos el nombre correcto de la excepción: ParseException
from pyparsing import ParseException

# --- Configuración ---
logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO').upper())
s3 = boto3.client('s3')
DIAGRAM_BUCKET = os.environ.get("DIAGRAM_BUCKET")

def generate_erd(event, context):
    """
    Función principal de Lambda para generar diagramas Entidad-Relación.
    """
    if not DIAGRAM_BUCKET:
        logger.error("La variable de entorno DIAGRAM_BUCKET no está configurada.")
        return {'statusCode': 500, 'body': json.dumps({'error': 'Configuración del servidor incompleta.'})}

    try:
        body = json.loads(event.get('body', '{}'))
        user_code = body.get('user_code')

        if not user_code:
            return {'statusCode': 400, 'body': json.dumps({'error': 'Falta el campo "user_code".'})}

        unique_id = str(uuid.uuid4())
        output_format = 'png'
        
        source_file_path = pathlib.Path(f"/tmp/{unique_id}.er")
        output_path = pathlib.Path(f"/tmp/{unique_id}.{output_format}")

        source_file_path.write_text(user_code)

        render_er(str(source_file_path), str(output_path))
        
        if not output_path.exists():
            raise IOError("La generación del diagrama con eralchemy falló y no se creó el archivo.")

        s3_diagram_key = f"diagrams/erd_{unique_id}.{output_format}"
        s3_source_key = f"source_codes/erd_{unique_id}.er"

        s3.upload_file(str(output_path), DIAGRAM_BUCKET, s3_diagram_key)
        s3.put_object(Bucket=DIAGRAM_BUCKET, Key=s3_source_key, Body=user_code.encode('utf-8'))

        region = os.environ.get("AWS_REGION", "us-east-1")
        diagram_url = f"https://{DIAGRAM_BUCKET}.s3.{region}.amazonaws.com/{s3_diagram_key}"
        
        source_file_path.unlink()
        output_path.unlink()

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Diagrama ERD generado exitosamente!',
                'diagram_url': diagram_url
            })
        }
    
    # ¡LA CORRECCIÓN! Capturamos el nombre correcto de la excepción: ParseException
    except ParseException as pe:
        error_message = f"Error de sintaxis en tu código ERD en la línea {pe.lineno}: '{pe.line}'"
        logger.error(error_message)
        return {
            'statusCode': 400,
            'body': json.dumps({'error': error_message})
        }
    
    except Exception as e:
        logger.error(f"Error inesperado en generate_erd: {e}", exc_info=True)
        return {'statusCode': 500, 'body': json.dumps({'error': f"Error interno del servidor: {str(e)}"}) }