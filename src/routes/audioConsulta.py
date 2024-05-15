from flask import Blueprint, request
import magic

from services.audioConsulta import create_audioConsulta_service, getAll_audioConsulta_service, get_audioConsulta_service, update_audioConsulta_service, delete_audioConsulta_service

audioConsulta = Blueprint('audioConsulta', __name__)

@audioConsulta.route('/', methods=['GET'])
def getAll_audioConsulta():
    return getAll_audioConsulta_service()

@audioConsulta.route('/<id>', methods=['GET'])
def get_audioConsulta(id):
    return get_audioConsulta_service(id)

@audioConsulta.route('/', methods=['POST'])
def create_audioConsulta():
    if validar_archivo_blob_wav(request.files['archivo']):
        return create_audioConsulta_service()
    else:
        return 'Internal Error', 500

@audioConsulta.route('/<id>', methods=['PUT'])
def update_audioConsulta(id):
    return update_audioConsulta_service(id)

@audioConsulta.route('/<id>', methods=['DELETE'])
def delete_audioConsulta(id):
    return delete_audioConsulta_service(id)

def validar_archivo_blob_wav(archivo):
    # Crear un objeto magic
    detector = magic.Magic(mime=True)
    # Obtener el mimetype del archivo
    mimetype = detector.from_buffer(archivo.read(1024))  # Leemos solo los primeros 1024 bytes para detectar el tipo
    # Verificar si el mimetype es de tipo audio/wav
    if mimetype == 'audio/x-wav' or mimetype == 'audio/wav':
        return True
    else:
        return False