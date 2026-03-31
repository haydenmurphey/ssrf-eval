from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({"service": "Internal Admin Dashboard", "status": "Restricted Access"})

@app.route('/admin/secrets')
def get_secrets():
    secret = os.environ.get('SECRET_API_KEY', 'NOT_FOUND')
    return jsonify({"admin_data": "sensitive", "token": secret})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)