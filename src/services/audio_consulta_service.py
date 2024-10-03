import base64
from datetime import datetime
import io
import os
import subprocess
import tempfile
from flask import jsonify, request, Response, send_file
from bson import Binary, json_util, ObjectId
import openai
from config.mongodb import mongo


openai.api_key = os.getenv('openai.api_key')

def upload_audio_file_in_storage_service(_mongod, _gridfs):
    try:
        if 'archivo' not in request.files:
            return jsonify({'error': 'No se ha enviado el archivo'}), 400

        # Obtener el archivo enviado en el formulario
        archivo = request.files['archivo']

        title = request.form.get('title')
        full_filename = f"{title}"
        mimetype = archivo.mimetype
        file_binary = Binary(archivo.read())
        size = len(file_binary)

        # Subir el archivo a GridFS
        file_id = _gridfs.put(file_binary, filename=full_filename, content_type=mimetype)

        # Responder con el ID del archivo subido y los metadatos
        return jsonify({
            'message': 'Archivo subido correctamente',
            'file_id': str(file_id),
            'metadata': {
                'filename': full_filename,
                'mimetype': mimetype,
                'size': size,
                # 'sizeUnit': size_unit
            }
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_audio_from_gridfs(file_id, _gridfs):
    try:
        # Intenta encontrar el archivo en GridFS
        file_data = _gridfs.find_one({"_id": ObjectId(file_id)})

        if not file_data:
            return None, 'Archivo no encontrado'

        # Recuperar el archivo
        file_binary = _gridfs.get(file_data._id).read()
        mimetype = file_data.content_type
        filename = file_data.filename

        return file_binary, mimetype, filename

    except Exception as e:
        return None, str(e)


def get_audio_file(file_id, _gridfs):
    try:
        file_binary, mimetype, filename = get_audio_from_gridfs(file_id, _gridfs)

        if file_binary is None:
            return jsonify({'error': mimetype}), 404  # mimetype contiene el mensaje de error

        # Verifica que el mimetype sea correcto para un archivo de audio
        if not mimetype.startswith('audio/'):
            return jsonify({'error': 'El archivo recuperado no es de tipo audio'}), 400

        # Enviar el archivo recuperado como descarga
        return send_file(io.BytesIO(file_binary), mimetype=mimetype, as_attachment=True, download_name=filename)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def create_unique_temp_file(suffix=".wav"):
    """
    Crea un archivo temporal con un nombre único y devuelve el nombre del archivo.
    El archivo no se eliminará automáticamente al cerrar para permitir su manipulación posterior.
    """
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_file.close()  # Cerramos el archivo para poder usarlo en otros procesos
    return temp_file.name


def generate_report_from_transcript(transcript_text):
    """
    Función que toma una transcripción y la envía a la API de OpenAI para formatearla en un reporte.

    :param transcript_text: Texto de la transcripción obtenida de Whisper.
    :return: Reporte formateado.
    """
    # Instrucciones y transcripción para enviar a ChatGPT
    messages = [
        {"role": "system", "content": "Eres un asistente que formatea transcripciones en un reporte médico estructurado."},
        {"role": "user", "content": f"""
        Por favor, genera un reporte médico estructurado a partir de la siguiente transcripción. Usa el siguiente formato:
        Título: [El título general del reporte]
        Subtítulo 1: [Descripción breve]
        Texto: [Cuerpo de la sección]
        Subtítulo 2: [Descripción breve]
        Texto: [Cuerpo de la sección]
        Conclusión: [Descripción breve]
        Texto: [Conclusión]

        Transcripción:
        {transcript_text}
        """}
    ]
    try:
        # Llamada a la API de OpenAI para generar el reporte
        # response = openai.ChatCompletion.create(
        #     model="gpt-4",
        #     messages=[
        #         {"role": "system", "content": "Eres un asistente que da formato técnico a reportes médico."},
        #         {"role": "user", "content": prompt}
        #     ]
        # )
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0
        )

        # Obtener el reporte formateado desde la respuesta
        formatted_report = response.choices[0].message.content

        # Retornar el reporte formateado
        return jsonify({'formatted_report': formatted_report}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


def send_audio_to_whisper_service(file_id, _gridfs):
    try:
        # # Intenta encontrar el archivo en GridFS
        # file_data = _gridfs.find_one({"_id": ObjectId(file_id)})
        # # file_data = get_audio_file(file_id, _gridfs)

        # if not file_data:
        #     return jsonify({'error': 'Archivo no encontrado'}), 404

        # # Recuperar el archivo en formato binario
        # file_binary = _gridfs.get(file_data._id).read()

        # Usa la función get_audio_from_gridfs para obtener el archivo desde GridFS
        file_binary, mimetype, filename = get_audio_from_gridfs(file_id, _gridfs)

        if file_binary is None:
            return jsonify({'error': mimetype}), 404  # mimetype contiene el mensaje de error

        # Verifica que el archivo sea de tipo audio
        if not mimetype.startswith('audio/'):
            return jsonify({'error': 'El archivo recuperado no es de tipo audio'}), 400

        # Crear archivos temporales con nombres únicos
        temp_file_path = create_unique_temp_file(suffix=".wav")
        converted_file_path = create_unique_temp_file(suffix=".wav")

        # Guardar el archivo binario en el archivo temporal
        with open(temp_file_path, 'wb') as temp_file:
            temp_file.write(file_binary)
            temp_file.flush()

        # Convertir el archivo a formato .wav usando ffmpeg
        subprocess.run(['ffmpeg', '-y', '-i', temp_file_path, converted_file_path], check=True)

        # Ahora enviamos el archivo convertido a Whisper para transcripción
        with open(converted_file_path, 'rb') as audio_file:
            transcription  = openai.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )

        # La transcripción se obtiene accediendo al atributo "text"
        transcript_text = transcription.text

        # Eliminar los archivos temporales
        os.remove(temp_file_path)
        os.remove(converted_file_path)

        # return jsonify({'transcription': transcript_text}), 200
        return generate_report_from_transcript(transcript_text)

    except Exception as e:
        return jsonify({'error': str(e)}), 500









def save_audio_file_in_storage_service(request):
    file = request.files['archivo']
    title_audio = request.form.get('title', '')

    file_name = file.filename
    type = file.mimetype
    file_binary = Binary(file.read())
    date_time = datetime.now()
    size = len(file_binary)

    response = mongo.db.audioConsulta.insert_one({
        'file_name': file_name,
        'type': type,
        'file_binary': file_binary,
        'date_time': date_time,
        'size': size,
        'stored_in_db': False,
        'title': title_audio
    })
    result = {
        'id': str(response.inserted_id),
        'title': title_audio,
        'type': type,
        'date_time': date_time,
        'size': size,
        'stored_in_db': False
    }
    return result

def create_audioConsulta_service():
    result_a = save_audio_file_in_storage_service(request)
    result_b = send_audio_to_whisper_service(request)
    # aca recuperar archivo y pasarlo a nueva function
    # que lo convierta a .wav y lo envie a whisper para
    # obtener repuesta
    # despues sigue el procesamiento de esta function para
    # guardar el audio y transcripcion en mongo

    if result_a and result_b:
        return jsonify(result_b), 200
    else:
        return 'System internal Error', 400

# def get_all_audio_service():
#     data = mongo.db.audioConsulta.find()
#     result = json_util.dumps(data)
#     return Response(result, mimetype='application/json')

# def  get_audio_service(id):
#     data = mongo.db.audioConsulta.find_one({'_id': ObjectId(id)})
#     result = json_util.dumps(data)
#     return Response(result, mimetype='application/json')

# def update_audio_service(id):
#     data = request.get_json()
#     if len(data) == 0:
#         return 'Invalid payload', 400

#     response = mongo.db.audioConsulta.update_one({'_id': ObjectId(id)},{'$set': data})

#     if response.modified_count >= 1:
#         return 'audioConsulta updated successfully', 200
#     else:
#         return 'audioConsulta not found', 404

# def delete_audio_service(id):
#     response = mongo.db.audioConsulta.delete_one({'_id': ObjectId(id)})
#     if response.deleted_count >= 1:
#         return 'audioConsulta deleted successfully', 200
#     else:
#         return 'audioConsulta not found', 404



