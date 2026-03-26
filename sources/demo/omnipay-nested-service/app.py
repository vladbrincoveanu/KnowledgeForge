"""
OmniPay Nested Service - Edge Case Testing

This service has nested directories that might be mistaken for separate services.
Tests extraction's ability to distinguish between:
- Actual separate services
- Subprojects/internal modules that are part of the same service
"""
from flask import Flask

app = Flask(__name__)

@app.route("/health")
def health():
    return {"status": "healthy", "service": "nested-service"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
