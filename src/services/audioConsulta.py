from datetime import datetime
import os
import subprocess
import tempfile
from flask import jsonify, request, Response, send_file 
from bson import Binary, json_util, ObjectId
import openai
from config.mongodb import mongo

openai.api_key = 'sk-proj-MP9Ya1BxiAyVYUqsCUm2T3BlbkFJYrYn1V9rjR1N4MQEl6DV'

def send_audioConsultaToWhisper_service(request):
    file = request.files['archivo']
    # Creamos un archivo temporal .wav
    # with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav_file:
    #     wav_file_path = temp_wav_file.name

    # # Convertimos el archivo recibido a formato .wav usando ffmpeg
    # subprocess.run(['ffmpeg', '-i', file_path, '-ac', '1', '-ar', '16000', wav_file_path])
    # return send_file(wav_file_path, as_attachment=True, attachment_filename='converted_audio.wav')
    try:
        response = openai.Whip.query(model="whisper-large", inputs={"speech": file.read()})
        return jsonify({'transcription': response['text']}), 200
    
    except Exception as e:
        return str(e), 500
    
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
    # file_path = os.path.join(tempfile.gettempdir(), file.filename)
    # file.save(file_path)

    # responseWhisper = send_audioConsultaToWhisper_service(file_path)
    result_a = save_audio_file_in_storage_service(request)
    result_b = send_audioConsultaToWhisper_service(request)
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


    
