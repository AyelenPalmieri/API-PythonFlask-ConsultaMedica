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
from pydub import AudioSegment
import speech_recognition as sr
# from pydub import AudioSegment
# from pydub.silence import detect_nonsilent


openai.api_key = os.getenv('openai.api_key')

# def is_audio_silent(file_path, silence_threshold=-0.0, silence_duration=5000):
#     """
#     Verifica si un archivo de audio está en silencio.

#     :param file_path: Ruta del archivo de audio.
#     :param silence_threshold: Umbral de silencio en dB (por defecto -50.0).
#     :param silence_duration: Duración mínima del silencio en milisegundos (por defecto 1000 ms).
#     :return: True si el audio está en silencio, False si contiene sonido.
#     """
#     audio = AudioSegment.from_file(file_path)
#     audio = audio.normalize()

#     # Ajustar el umbral de silencio
#     silence_thresh = audio.dBFS + silence_threshold
#     print(f"Nivel de silencio: {silence_thresh} dB")
#     print(f"Nivel promedio del audio: {audio.dBFS} dB")

#     # thresh = segment.dBFS - (segment.max_dBFS - segment.dBFS)
#     # non_silent_ranges = pydub.silence.detect_nonsilent(segment, min_silence_len=1000, silence_thresh=thresh)

#     # Utiliza el método detect_nonsilent para encontrar rangos de audio no silencioso
#     nonsilent_ranges = detect_nonsilent(
#         audio,
#         min_silence_len=silence_duration,
#         # silence_thresh=audio.dBFS + silence_threshold
#         silence_thresh=silence_thresh + silence_threshold
#     )

#      # Imprimir los rangos no silenciosos detectados
#     if nonsilent_ranges:
#         print("Rangos no silenciosos detectados:", nonsilent_ranges)
#         return False  # Hay audio, por lo tanto, no es silencio
#     else:
#         print("No se detectaron rangos no silenciosos. El audio es considerado silencio.")
#         return True  # No hay audio, se considera silencio

def is_audio_silent(file_path):
    """
    Verifica si un archivo de audio contiene habla o solo ruido/silencio.

    :param file_path: Ruta del archivo de audio.
    :return: True si el audio contiene solo ruido o silencio, False si contiene habla.
    """
    recognizer = sr.Recognizer()
    audio_segment = AudioSegment.from_file(file_path)

    # Convertir el archivo de audio a un formato compatible para el análisis
    wav_path = file_path.replace(".wav", "_temp.wav")
    audio_segment.export(wav_path, format="wav")

    try:
        # Cargar el archivo de audio para el reconocimiento de voz
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)

            try:
                # Intentar reconocer el habla en el archivo de audio
                recognizer.recognize_google(audio_data)
                print("Se detectó habla, no es silencio ni solo ruido")
                return False  # Se detectó habla, no es silencio ni solo ruido
            except sr.UnknownValueError:
                print("No se detectó habla, se considera ruido o silencio")
                return True  # No se detectó habla, se considera ruido o silencio
            except sr.RequestError:
                print("Error con el servicio de reconocimiento de voz")
                return True
    finally:
        # Eliminar archivo temporal después de que todos los procesos hayan terminado
        if os.path.exists(wav_path):
            os.remove(wav_path)

def upload_audio_file_in_storage_service(_mongod, _gridfs):
    try:
        if 'archivo' not in request.files:
            return jsonify({'error': 'No se ha enviado el archivo'}), 400

        # Obtener el archivo enviado en el formulario
        archivo = request.files['archivo']

        # Crear un archivo temporal para verificar el silencio
        temp_file_path = create_unique_temp_file(suffix=".wav")

        # Guardar el archivo en un archivo temporal para análisis
        with open(temp_file_path, 'wb') as temp_file:
            temp_file.write(archivo.read())
            temp_file.flush()

        # Verificar si el audio contiene solo ruido o silencio
        if is_audio_silent(temp_file_path):
            os.remove(temp_file_path)
            return jsonify({'error': 'El audio no contiene habla y no se almacenará.'}), 412

        # Reiniciar el archivo en el objeto de archivo (se requiere para cargar nuevamente)
        archivo.seek(0)

        title = request.form.get('title')
        full_filename = f"{title}"
        mimetype = archivo.mimetype
        file_binary = Binary(archivo.read())
        size = len(file_binary)

        # Subir el archivo a GridFS
        file_id = _gridfs.put(file_binary, filename=full_filename, content_type=mimetype)


        # Eliminar el archivo temporal
        os.remove(temp_file_path)

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


def delete_audio_file_from_storage_service(file_id, _gridfs):
    try:
        # Convertir el file_id a un ObjectId
        object_id = ObjectId(file_id)

        # Verificar si el archivo existe en GridFS
        if not _gridfs.exists(object_id):
            return jsonify({'error': 'El archivo no existe'}), 404

        # Eliminar el archivo de GridFS
        _gridfs.delete(object_id)

        # Responder con un mensaje de confirmación
        return jsonify({'message': 'Archivo eliminado correctamente'}), 200

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


def send_audio_to_whisper_service(file_id, _gridfs):
    try:
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

        # # Guardar el archivo binario en el archivo temporal
        # with open(temp_file_path, 'wb') as temp_file:
        #     temp_file.write(file_binary)
        #     temp_file.flush()

        try:
            # Guardar y convertir el archivo a .wav
            save_file(temp_file_path, file_binary)
            convert_to_wav(temp_file_path, converted_file_path)

            # # Convertir el archivo a formato .wav usando ffmpeg
            # subprocess.run(['ffmpeg', '-y', '-i', temp_file_path, converted_file_path], check=True)

            # Transcribir el audio usando Whisper
            transcript_text = transcribe_audio(converted_file_path)

            # # Ahora enviamos el archivo convertido a Whisper para transcripción
            # with open(converted_file_path, 'rb') as audio_file:
            #     transcription  = openai.audio.transcriptions.create(
            #         model="whisper-1",
            #         file=audio_file
            #     )

            # La transcripción se obtiene accediendo al atributo "text"
            # transcript_text = transcription.text

            # # Eliminar los archivos temporales
            # os.remove(temp_file_path)
            # os.remove(converted_file_path)

            # # return jsonify({'transcription': transcript_text}), 200
            # return generate_report_from_transcript(transcript_text)

            # Verifica si el texto de la transcripción está vacío o solo contiene espacios en blanco
            if not transcript_text or transcript_text.strip() == "":
                return jsonify({'error': 'La transcripción está vacía. No se puede generar un reporte.'}), 412

            # Generar el reporte formateado a partir de la transcripción
            return generate_report_from_transcript(transcript_text)

        finally:
            # Asegurar la eliminación de archivos temporales
            cleanup_files([temp_file_path, converted_file_path])

    except Exception as e:
        return jsonify({'error': f'Error en el procesamiento del audio: {str(e)}'}), 500


def save_file(file_path, file_binary):
    # Guardar el archivo binario en el archivo temporal
    with open(file_path, 'wb') as temp_file:
        temp_file.write(file_binary)
        temp_file.flush()

def convert_to_wav(input_path, output_path):
    """Convierte un archivo de audio a .wav usando ffmpeg."""
    try:
        subprocess.run(['ffmpeg', '-y', '-i', input_path, output_path], check=True)
    except subprocess.CalledProcessError as e:
        raise Exception(f"Error en la conversión a WAV: {str(e)}")

def transcribe_audio(file_path):
    """Usa el modelo de Whisper para transcribir el audio."""
    try:
        # Ahora enviamos el archivo convertido a Whisper para transcripción
        with open(file_path, 'rb') as audio_file:
            transcription = openai.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        return transcription.text
    except Exception as e:
        raise Exception(f"Error en la transcripción del audio: {str(e)}")


def cleanup_files(file_paths):
    """Elimina los archivos temporales especificados."""
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            print(f"Error al eliminar el archivo {path}: {str(e)}")


def generate_report_from_transcript(transcript_text):
    """
    Función que toma una transcripción y la envía a la API de OpenAI para formatearla en un reporte.
    Genera un reporte médico formateado a partir de una transcripción.

    :param transcript_text: Texto de la transcripción obtenida de Whisper.
    :return: Reporte formateado.
    """

    # Agrego un log para verificar el contenido de transcript_text
    print(f"Contenido de transcript_text: '{transcript_text}'")  # Debugging

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

        # Llamada a la API de OpenAI para generar el reporte
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
         return jsonify({'error': f'Error al generar el reporte: {str(e)}'}), 500










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

# def delete_audio_service(id):
#      response = mongo.db.audioConsulta.delete_one({'_id': ObjectId(id)})
#      if response.deleted_count >= 1:
#          return 'audioConsulta deleted successfully', 200
#      else:
#          return 'audioConsulta not found', 404

