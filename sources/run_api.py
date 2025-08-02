#!/usr/bin/env python3
"""
Simple script to run the API and catch errors.
"""

import sys
import os
import traceback

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    try:
        print("🔧 Importing FastAPI app...")
        from Api.Api.main import app
        print("✅ FastAPI app imported successfully")
        
        print("🚀 Starting uvicorn server...")
        import uvicorn
        
        # Load configuration
        from Api.Infrastructure.config_manager import config_manager
        api_config = config_manager.get_api_config()
        
        print(f"📋 API Configuration:")
        print(f"   Host: {api_config['host']}")
        print(f"   Port: {api_config['port']}")
        print(f"   Debug: {api_config['debug']}")
        
        # Run the server
        uvicorn.run(
            app,
            host=api_config['host'],
            port=api_config['port'],
            log_level="info",
            reload=api_config['debug']
        )
        
    except Exception as e:
        print(f"❌ Error starting API: {e}")
        print("\n🔍 Full traceback:")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 