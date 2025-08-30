"""Main entry point for the KnowledgeForge API."""

import uvicorn
import logging
from pathlib import Path
import sys

# Add the app directory to the Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

from app.app import app
from app.core.config import get_settings

if __name__ == "__main__":
    try:
        # Load configuration
        config = get_settings()
        
        # Configure logging
        logging.basicConfig(
            level=getattr(logging, config.logging.level),
            format=config.logging.format
        )
        
        # Run the application
        uvicorn.run(
            "app.app:app",
            host="0.0.0.0",
            port=8000,
            reload=config.debug,
            log_level=config.logging.level.lower(),
            access_log=True
        )
        
    except Exception as e:
        logging.error(f"Failed to start application: {e}")
        sys.exit(1)
