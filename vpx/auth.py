import os
from pathlib import Path
import requests
import json
from typing import Dict

def get_credentials_path() -> Path:
    """Get the path where credentials should be stored"""
    if os.name == 'nt':  # Windows
        base_dir = Path(os.environ['LOCALAPPDATA'])
    else:  # Unix-like
        base_dir = Path.home() / '.config'
    
    return base_dir / 'vpx' / 'credentials.json'

def authenticate_user(license_key: str) -> Dict:
    """Verify license key and get credentials"""
    # TODO: Replace with your actual license verification endpoint
    response = requests.post(
        'http://localhost:3000/api/auth',
        json={'license_key': license_key}
    )
    
    if response.status_code != 200:
        raise ValueError(f"Invalid license key: {response.json().get('error', 'Unknown error')}")
        
    return response.json()

def get_stored_credentials() -> Dict:
    """Get stored credentials if they exist"""
    creds_path = get_credentials_path()
    
    if not creds_path.exists():
        raise ValueError("Not authenticated. Please run 'vpx login' first")
        
    with open(creds_path) as f:
        return json.load(f) 