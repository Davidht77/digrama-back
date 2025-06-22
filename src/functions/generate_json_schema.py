import json
import os
import uuid
import boto3

dynamodb = boto3.resource('dynamodb')
table_name = os.environ['TABLE_NAME']
table = dynamodb.Table(table_name)

def generate_diagram(event, context, diagram_type):
    try:
        body = json.loads(event['body'])
        data = body.get('data')
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'Invalid JSON in request body'})
        }

    if not data:
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'Missing data in request body'})
        }

    diagram_id = str(uuid.uuid4())
    
    # Aquí iría la lógica para generar el diagrama según el tipo y los datos.
    # Por ahora, solo devolveremos un mensaje de éxito y guardaremos los datos.

    item = {
        'id': diagram_id,
        'type': diagram_type,
        'data': data,
        'createdAt': boto3.dynamodb.types.Decimal(json.dumps(event['requestContext']['requestTimeEpoch'])),
        'updatedAt': boto3.dynamodb.types.Decimal(json.dumps(event['requestContext']['requestTimeEpoch']))
    }

    table.put_item(Item=item)

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': f'Diagram of type {diagram_type} generated and saved successfully!',
            'diagramId': diagram_id,
            'data': data
        })
    }

def generate_json_schema(event, context):
    return generate_diagram(event, context, 'json-schema')