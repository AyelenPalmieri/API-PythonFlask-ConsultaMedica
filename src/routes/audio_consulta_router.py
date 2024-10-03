from flask import Blueprint, request

from services.audio_consulta_service import send_audio_to_whisper_service, upload_audio_file_in_storage_service, get_audio_file
#create_audio_service, get_all_audio_service, get_audio_service, update_audio_service, delete_audio_service,

audio_consulta_service = Blueprint('audio_consulta_service', __name__)

def init_audio_consulta_service(db, fs):
    # @audio_consulta_service.route('/', methods=['GET'])
    # def get_all_audio():
    #     return get_all_audio_service()

    # @audio_consulta_service.route('/<id>', methods=['GET'])
    # def get_audio(id):
    #     return get_audio_service(id)

    @audio_consulta_service.route('/transcribe', methods=['POST'])
    def transcribe_audio_file():
        data = request.get_json()
        file_id = data['file_id']
        return send_audio_to_whisper_service('66fd9f9a5eaa8d65a86ad172', fs)

    @audio_consulta_service.route('/upload', methods=['POST'])
    def upload_audio_file_in_storage():
        return upload_audio_file_in_storage_service(db, fs)

    @audio_consulta_service.route('/file/<file_id>', methods=['GET'])
    def retrieve_audio_file(file_id):
        return get_audio_file(file_id, fs)

    # @audio_consulta_service.route('/transcribe/<file_id>', methods=['POST'])
    # def send_audio_to_whisper(file_id):
    #     return send_audio_to_whisper_service(file_id, fs)

    # @audio_consulta_service.route('/<id>', methods=['PUT'])
    # def update_audio(id):
    #     return update_audio_service(id)

    # @audio_consulta_service.route('/<id>', methods=['DELETE'])
    # def delete_audio(id):
    #     return delete_audio_service(id)


