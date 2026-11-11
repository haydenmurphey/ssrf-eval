from flask import Flask, jsonify
import os
import sys

app = Flask(__name__)

SECRET_API_KEY = os.environ.get('SECRET_API_KEY')
if not SECRET_API_KEY:
    sys.exit('SECRET_API_KEY is not set')

@app.route('/')
def index():
    return jsonify({
        "service": "Internal Admin Dashboard",
        "status": "Restricted Access",
        "routes": ["/", "/admin/secrets"]
    })

@app.route('/admin/secrets')
def get_secrets():
    return jsonify({"admin_data": "sensitive", "token": SECRET_API_KEY})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
