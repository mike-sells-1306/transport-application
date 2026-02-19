from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

@app.route('/api/hello')
def hello():
    return jsonify({"message": "Transport backend running"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
