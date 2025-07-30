#!/usr/bin/env python3
"""
Configuration Setup Script

Helps users set up their configuration by copying from default template.
"""

import json
import os
import sys
from pathlib import Path

def setup_configuration():
    """Set up configuration files."""
    print("🔧 Knowlly Configuration Setup")
    print("=" * 40)
    
    config_path = Path("config.json")
    default_config_path = Path("config.default.json")
    
    # Check if config.json already exists
    if config_path.exists():
        print(f"⚠️  {config_path} already exists!")
        response = input("Do you want to overwrite it? (y/N): ").lower().strip()
        if response != 'y':
            print("Setup cancelled.")
            return
    
    # Check if default config exists
    if not default_config_path.exists():
        print(f"❌ {default_config_path} not found!")
        print("Please ensure config.default.json exists in the current directory.")
        return
    
    try:
        # Load default configuration
        with open(default_config_path, 'r') as f:
            default_config = json.load(f)
        
        # Create config.json
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
        
        print(f"✅ Created {config_path} from template")
        print("\n📝 Next steps:")
        print("1. Edit config.json with your actual values")
        print("2. Update database connection strings")
        print("3. Set your security keys")
        print("4. Configure logging and other settings")
        print("\n🔒 Note: config.json is gitignored to protect your secrets")
        
    except Exception as e:
        print(f"❌ Error creating configuration: {e}")
        return

def validate_configuration():
    """Validate the current configuration."""
    print("\n🔍 Validating Configuration")
    print("=" * 30)
    
    config_path = Path("config.json")
    
    if not config_path.exists():
        print("❌ config.json not found!")
        return False
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Check required sections
        required_sections = ['database', 'cache', 'storage', 'api', 'logging', 'security']
        missing_sections = []
        
        for section in required_sections:
            if section not in config:
                missing_sections.append(section)
        
        if missing_sections:
            print(f"❌ Missing configuration sections: {', '.join(missing_sections)}")
            return False
        
        # Check critical values
        critical_checks = [
            ('database.mongodb.connection_string', 'MongoDB connection string'),
            ('storage.minio.access_key', 'MinIO access key'),
            ('storage.minio.secret_key', 'MinIO secret key'),
            ('security.jwt_secret', 'JWT secret key')
        ]
        
        issues = []
        for key, description in critical_checks:
            keys = key.split('.')
            value = config
            try:
                for k in keys:
                    value = value[k]
                if not value or value.startswith('your_') or value == 'username:password':
                    issues.append(f"⚠️  {description} needs to be configured")
            except (KeyError, TypeError):
                issues.append(f"❌ {description} is missing")
        
        if issues:
            print("Configuration issues found:")
            for issue in issues:
                print(f"  {issue}")
            return False
        
        print("✅ Configuration is valid!")
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in config.json: {e}")
        return False
    except Exception as e:
        print(f"❌ Error validating configuration: {e}")
        return False

def main():
    """Main setup function."""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "setup":
            setup_configuration()
        elif command == "validate":
            validate_configuration()
        else:
            print("Usage: python setup_config.py [setup|validate]")
    else:
        print("Knowlly Configuration Setup")
        print("=" * 30)
        print("Commands:")
        print("  setup    - Create config.json from template")
        print("  validate - Validate current configuration")
        print("\nExample: python setup_config.py setup")

if __name__ == "__main__":
    main() 