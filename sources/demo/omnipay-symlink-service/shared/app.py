"""Symlink service - shared app code."""
from flask import Flask

app = Flask(__name__)

@app.route("/health")
def health():
    return {"status": "healthy", "service": "symlink-service"}
