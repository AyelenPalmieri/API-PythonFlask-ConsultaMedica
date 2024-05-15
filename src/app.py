from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from dotenv import load_dotenv
import os

from config.mongodb import mongo
from routes.audioConsulta import audioConsulta

load_dotenv()

app = Flask(__name__)

@app.before_request
def before_request():
    headers = {'Access-Control-Allow-Origin': '*',
               'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
               'Access-Control-Allow-Headers': 'Content-Type'}
    if request.method.lower() == 'options':
        return jsonify(headers), 200
    
CORS(app, resources={r"/audioConsulta/*": {"origins": "http://localhost:4200"}})

app.config['MONGO_URI'] = os.getenv('MONGO_URI')
mongo.init_app(app)

@app.route('/')
def index():
    return render_template('index.html')

app.register_blueprint(audioConsulta, url_prefix='/audioConsulta')

if __name__ == '__main__':
    app.run(debug=True, port=4000)