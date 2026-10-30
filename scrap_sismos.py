import requests
import boto3
from datetime import datetime

URL_BASE = "https://ultimosismo.igp.gob.pe/api/ultimo-sismo/ajaxb/{anio}"
NOMBRE_TABLA = "TablaSismos"


def lambda_handler(event, context):
    # 1. URL del API del IGP con el año actual
    url = URL_BASE.format(anio=datetime.now().year)

    # 2. Petición HTTP
    try:
        respuesta = requests.get(url, timeout=10)
    except requests.RequestException:
        return {
            'statusCode': 502,
            'body': 'No se pudo acceder al API del IGP'
        }

    if respuesta.status_code != 200:
        return {
            'statusCode': respuesta.status_code,
            'body': 'Error al acceder al API del IGP'
        }

    # 3. El API devuelve una lista JSON ordenada del más antiguo al más reciente
    sismos = respuesta.json()

    # 4. Los 10 últimos, con el más reciente primero
    ultimos = sismos[-10:][::-1]

    # 5. Armar los items (magnitud/latitud/longitud vienen como texto
    #    y profundidad como entero, así que DynamoDB los acepta sin Decimal)
    items = []
    for i, s in enumerate(ultimos, start=1):
        items.append({
            'id': s['codigo'],  # único por sismo, ej. 2026-0758
            '#': i,
            'fecha_hora_local': s['fecha_local'][:10] + ' ' + s['hora_local'][11:19],
            'magnitud': s['magnitud'],
            'profundidad_km': s['profundidad'],
            'referencia': s['referencia'],
            'latitud': s['latitud'],
            'longitud': s['longitud'],
            'intensidad': s.get('intensidad') or '',
            'reporte_pdf': s.get('reporte_acelerometrico_pdf') or '',
        })

    # 6. Vaciar la tabla y guardar los 10 sismos
    tabla = boto3.resource('dynamodb').Table(NOMBRE_TABLA)

    scan = tabla.scan()
    with tabla.batch_writer() as batch:
        for each in scan['Items']:
            batch.delete_item(Key={'id': each['id']})

    with tabla.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)

    # 7. Respuesta
    return {
        'statusCode': 200,
        'body': items
    }
