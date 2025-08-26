#!/usr/bin/env python3
"""
Test script for the file upload API endpoint
"""

import requests
import json

# API configuration
API_BASE_URL = "http://localhost:8000"
API_KEY = "test-api-key-12345"

def test_file_upload():
    """Test the file upload endpoint"""
    
    # Test file path
    test_file_path = "agriculture_workers_percent_of_employment.csv"
    
    try:
        # Prepare the file for upload
        with open(test_file_path, 'rb') as f:
            files = {'file': (test_file_path, f, 'text/csv')}
            headers = {'Authorization': f'Bearer {API_KEY}'}
            
            # Make the upload request
            response = requests.post(
                f"{API_BASE_URL}/upload",
                files=files,
                headers=headers
            )
            
            print(f"Upload Response Status: {response.status_code}")
            print(f"Upload Response: {response.text}")
            
            if response.status_code == 200:
                upload_data = response.json()
                print(f"File uploaded successfully: {upload_data}")
                
                # Now test the extract endpoint
                extract_data = {
                    "file_path": upload_data["file_path"],
                    "extraction_config": {
                        "confidence_threshold": 0.7,
                        "max_entities_per_column": 100,
                        "enable_semantic_similarity": True,
                        "enable_hierarchical_discovery": True
                    }
                }
                
                extract_response = requests.post(
                    f"{API_BASE_URL}/extract",
                    json=extract_data,
                    headers=headers
                )
                
                print(f"Extract Response Status: {extract_response.status_code}")
                print(f"Extract Response: {extract_response.text}")
                
            else:
                print(f"Upload failed with status {response.status_code}")
                
    except FileNotFoundError:
        print(f"Test file not found: {test_file_path}")
    except requests.exceptions.ConnectionError:
        print("Failed to connect to API server. Make sure it's running on http://localhost:8000")
    except Exception as e:
        print(f"Error during test: {e}")

if __name__ == "__main__":
    test_file_upload()

