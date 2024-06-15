import base64
from datetime import datetime
from pydub import AudioSegment
import os
import subprocess
import tempfile
from flask import jsonify, request, Response, send_file
from bson import Binary, json_util, ObjectId
import openai
from config.mongodb import mongo
# from transcriber import Transcriber

openai.api_key = os.getenv('openai.api_key')

def verify_pitos(request):
    file = request.files['archivo']
    file_binary = Binary(file.read())

    if len(file_binary):
        return True
    else:
        return False

def send_audioConsultaToWhisper_service(file):

    input_path = 'input_file.wav'
    output_path = 'output_file.mp3'

    tetas = file.read()

    # Verificar el contenido del archivo antes de guardarlo
    file_content = Binary(file.read())
    if len(file_content) == 0:
        print(f"Archivo {file_content}")
        return "El archivo de entrada está vacío", 400

    # Guardar el archivo y verificar
    try:
        with open(input_path, 'wb') as f:
            f.write(file_content)
        print(f"Archivo guardado en {input_path}")
    except Exception as e:
        print(f"Error al guardar el archivo: {e}")
        return "Error al guardar el archivo", 500

    # Verificar el tamaño del archivo guardado
    if not os.path.exists(input_path):
        print(f"El archivo {input_path} no existe")
        return "El archivo de entrada no se guardó correctamente", 400

    if os.path.getsize(input_path) == 0:
        print(f"El archivo {input_path} esta vacio")
        return "El archivo de entrada esta vacio", 400

    result = subprocess.run(['ffmpeg', '-i', input_path, output_path], capture_output=True, text=True)

     # Imprimir la salida estándar y el error estándar de ffmpeg
    print("ffmpeg stdout:", result.stdout)
    print("ffmpeg stderr:", result.stderr)

    # Verificar si el comando fue exitoso
    if result.returncode != 0:
        return f"ffmpeg error: {result.stderr}", 500

    try:
        with open(output_path, 'rb') as file_binary:
            transcript = openai.audio.transcriptions.create(
                file = file_binary,
                model = "whisper-1",
                response_format = "verbose_json",
                timestamp_granularities = ["word"]
            )
            return jsonify(transcript.words), 200
            # return jsonify({'transcription': response['text']}), 200

    except Exception as e:
        print(f"Error: {e}")
        return str(e), 500

    finally:
            # Eliminar archivos temporales
        if os.path.exists(input_path):
            os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)

def save_audio_file_in_storage_service(file, title):

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
        'title': title
    })
    result = {
        'id': str(response.inserted_id),
        'title': title,
        'type': type,
        'date_time': date_time,
        'size': size,
        'stored_in_db': False
    }
    return result


def create_audioConsulta_service():
    # file_path = os.path.join(tempfile.gettempdir(), file.filename)
    # file.save(file_path)

    # responseWhisper = send_audioConsultaToWhisper_service(file_path)
    # pepe = request.files['archivo']
    # pepe_te = request.form.get('title', '')

    pitochu=request.data

    file = request.files['archivo']
    title_audio = request.form.get('title', '')

    result_a = save_audio_file_in_storage_service(file, title_audio)
    result_b = send_audioConsultaToWhisper_service(file)

    # aca recuperar archivo y pasarlo a nueva function
    # que lo convierta a .wav y lo envie a whisper para
    # obtener repuesta
    # despues sigue el procesamiento de esta functionpara
    # guardar el audio y transcripcion en mongo

    if result_a and result_b:
        return jsonify(result_b), 200
    else:
        return 'System internal Error', 400

def getAll_audioConsulta_service():
    data = mongo.db.audioConsulta.find()
    result = json_util.dumps(data)
    return Response(result, mimetype='application/json')

def  get_audioConsulta_service(id):
    data = mongo.db.audioConsulta.find_one({'_id': ObjectId(id)})
    result = json_util.dumps(data)
    return Response(result, mimetype='application/json')

def get_audioConsulta2_service(id):
    # Obtener el documento de MongoDB
    data = mongo.db.audioConsulta.find_one({'_id': ObjectId(id)})

    if not data:
        return "Audio no encontrado", 404

    # Obtener los bytes de audio del documento
    audio_data = data.get('file_binary', b'')

    try:
        # Guardar los datos de audio en un archivo temporal
        with tempfile.NamedTemporaryFile(delete=False,  suffix=".wav") as tmp_input_file:
            tmp_input_file.write(audio_data)
            input_path = tmp_input_file.name
            print(f"Archivo guardado temporalmente en {input_path}")

        # Especificar el nombre del archivo de salida
        output_path = tempfile.mktemp(suffix=".mp3")

        # Usar pydub para convertir el archivo de WAV a MP3
        audio = AudioSegment.from_wav(input_path)
        audio.export(output_path, format="mp3")

        print(f"Archivo convertido y guardado en {output_path}")

        # Leer el archivo convertido para enviarlo en la respuesta
        with open(output_path, "rb") as f:
            result_data = f.read()

        return Response(result_data, mimetype="audio/mpeg")

    except Exception as e:
        print(f"Error general: {e}")
        return "Error general", 500

    # finally:
    #     # Asegúrate de eliminar los archivos temporales después de usarlos
    #     if os.path.exists(input_path):
    #         try:
    #             os.remove(input_path)
    #             print(f"Archivo temporal eliminado: {input_path}")
    #         except Exception as e:
    #             print(f"No se pudo eliminar el archivo temporal: {e}")

    #     if os.path.exists(output_path):
    #         try:
    #             os.remove(output_path)
    #             print(f"Archivo temporal eliminado: {output_path}")
    #         except Exception as e:
    #             print(f"No se pudo eliminar el archivo temporal: {e}")


def update_audioConsulta_service(id):
    data = request.get_json()
    if len(data) == 0:
        return 'Invalid payload', 400

    response = mongo.db.audioConsulta.update_one({'_id': ObjectId(id)},{'$set': data})

    if response.modified_count >= 1:
        return 'audioConsulta updated successfully', 200
    else:
        return 'audioConsulta not found', 404

def delete_audioConsulta_service(id):
    response = mongo.db.audioConsulta.delete_one({'_id': ObjectId(id)})
    if response.deleted_count >= 1:
        return 'audioConsulta deleted successfully', 200
    else:
        return 'audioConsulta not found', 404



