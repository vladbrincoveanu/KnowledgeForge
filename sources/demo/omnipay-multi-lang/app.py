from flask import Flask
import requests

app = Flask(__name__)

@app.route("/health")
def health():
    return {"status": "healthy", "service": "multi-lang"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
