# src/functions/generate_json_schema.py

import json
import os
import uuid
import logging
import pathlib
import boto3
# ¡Importante! La librería de Python para Graphviz
from graphviz import Source

# --- Configuración ---
logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO').upper())
s3 = boto3.client('s3')
DIAGRAM_BUCKET = os.environ.get("DIAGRAM_BUCKET")

# --- La Lógica Principal de Conversión ---

def _build_dot_nodes(data, parent_id, dot_lines, node_counter):
    """
    Función recursiva para construir los nodos del grafo en lenguaje DOT.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            node_counter[0] += 1
            current_id = f'node{node_counter[0]}'
            
            # Escapamos las comillas y caracteres especiales para el label
            escaped_key = json.dumps(key)

            if isinstance(value, (dict, list)):
                dot_lines.append(f'    {current_id} [label={escaped_key}, shape=box, style=rounded];')
                dot_lines.append(f'    {parent_id} -> {current_id};')
                _build_dot_nodes(value, current_id, dot_lines, node_counter)
            else:
                escaped_value = json.dumps(value)
                node_text = f'<{escaped_key}<BR/><FONT POINT-SIZE="10">{escaped_value}</FONT>>'
                dot_lines.append(f'    {current_id} [label={node_text}, shape=box];')
                dot_lines.append(f'    {parent_id} -> {current_id};')

    elif isinstance(data, list):
        for index, item in enumerate(data):
            node_counter[0] += 1
            current_id = f'node{node_counter[0]}'
            
            if isinstance(item, (dict, list)):
                dot_lines.append(f'    {current_id} [label="Índice: {index}", shape=ellipse];')
                dot_lines.append(f'    {parent_id} -> {current_id};')
                _build_dot_nodes(item, current_id, dot_lines, node_counter)
            else:
                escaped_value = json.dumps(item)
                node_text = f'<Índice {index}<BR/><FONT POINT-SIZE="10">{escaped_value}</FONT>>'
                dot_lines.append(f'    {current_id} [label={node_text}, shape=box];')
                dot_lines.append(f'    {parent_id} -> {current_id};')

def json_to_dot(json_data):
    """
    Convierte un objeto JSON (ya parseado) a sintaxis de lenguaje DOT de Graphviz.
    """
    dot_lines = [
        'digraph JSONTree {',
        '    node [fontname="helvetica"];'
    ]
    node_counter = [0]
    
    root_id = 'node0'
    dot_lines.append(f'    {root_id} [label="JSON Root", shape=Mdiamond];')
    
    _build_dot_nodes(json_data, root_id, dot_lines, node_counter)
    
    dot_lines.append('}')
    return "\n".join(dot_lines)


# --- El Handler de Lambda ---

def generate_json_schema(event, context):
    """
    Punto de entrada de Lambda. Recibe un JSON y devuelve la URL de una imagen.
    """
    if not DIAGRAM_BUCKET:
        logger.error("La variable de entorno DIAGRAM_BUCKET no está configurada.")
        return {'statusCode': 500, 'body': json.dumps({'error': 'Configuración del servidor incompleta.'})}

    try:
        body = json.loads(event.get('body', '{}'))
        json_string = body.get('user_code') # Reusamos 'user_code' para consistencia

        if not json_string:
            return {'statusCode': 400, 'body': json.dumps({'error': 'Falta el campo "user_code" con el JSON.'})}

        try:
            data = json.loads(json_string)
        except json.JSONDecodeError:
            return {'statusCode': 400, 'body': json.dumps({'error': 'El "user_code" no es un JSON válido.'})}

        # 1. Generar la sintaxis DOT
        dot_syntax = json_to_dot(data)
        
        # 2. Renderizar la imagen usando Graphviz
        unique_id = str(uuid.uuid4())
        output_format = 'png'
        # La librería crea un archivo en /tmp con el nombre que le damos
        output_path_prefix = f"/tmp/{unique_id}"
        
        source = Source(dot_syntax)
        # El método render llama al programa 'dot' y crea la imagen
        # Devuelve la ruta completa al archivo generado, ej: '/tmp/some_id.png'
        rendered_path_str = source.render(output_path_prefix, format=output_format, cleanup=True)
        rendered_path = pathlib.Path(rendered_path_str)

        if not rendered_path.exists():
            raise IOError("La generación del diagrama con Graphviz falló y no se creó el archivo.")

        # 3. Subir los artefactos a S3
        s3_diagram_key = f"diagrams/json_{unique_id}.{output_format}"
        s3_source_key = f"source_codes/json_{unique_id}.json"

        s3.upload_file(
            str(rendered_path),
            DIAGRAM_BUCKET,
            s3_diagram_key,
            ExtraArgs={
                'ContentType': 'image/png',
                'ContentDisposition': 'inline'
            }
        )
        
        s3.put_object(Bucket=DIAGRAM_BUCKET, Key=s3_source_key, Body=json_string.encode('utf-8'))

        # 4. Generar la URL de respuesta
        region = os.environ.get("AWS_REGION", "us-east-1")
        diagram_url = f"https://{DIAGRAM_BUCKET}.s3.{region}.amazonaws.com/{s3_diagram_key}"
        
        # 5. Limpiar el archivo local
        rendered_path.unlink()

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Diagrama JSON generado exitosamente!',
                'diagram_url': diagram_url
            })
        }
    except Exception as e:
        logger.error(f"Error inesperado en generate_json_schema: {e}", exc_info=True)
        return {'statusCode': 500, 'body': json.dumps({'error': f"Error interno del servidor: {str(e)}"}) }