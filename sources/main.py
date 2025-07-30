"""
Main Entry Point

Entry point for the Knowlly Data Processing API.
"""

import uvicorn
import sys
import os

# Add the sources directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Api.Api.main import app

if __name__ == "__main__":
    uvicorn.run(
        "Api.Api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    ) 