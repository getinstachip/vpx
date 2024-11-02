from pathlib import Path
import os
import requests
from typing import Dict, Optional
from netrc import netrc, NetrcParseError
from functools import wraps
import typer

def get_netrc_path() -> Path:
    """Get the path to the .netrc file."""
    return Path.home() / ('.netrc' if os.name != 'nt' else '_netrc')

def store_credentials(email: str, key: str) -> None:
    """Store credentials in the .netrc file."""
    netrc_path = get_netrc_path()
    
    # Read existing netrc content
    try:
        existing_netrc = netrc(str(netrc_path))
        entries = existing_netrc.hosts
    except (FileNotFoundError, NetrcParseError):
        entries = {}

    # Update or add new credentials
    with open(netrc_path, 'w') as netrc_file:
        for machine, auth in entries.items():
            if machine != 'api.getinstachip.com':  # Preserve other entries
                login, account, password = auth
                netrc_file.write(f'machine {machine}\n')
                netrc_file.write(f'login {login}\n')
                if account:
                    netrc_file.write(f'account {account}\n')
                netrc_file.write(f'password {password}\n')
        
        # Add our service credentials
        netrc_file.write(f'machine api.getinstachip.com\n')
        netrc_file.write(f'login {email}\n')
        netrc_file.write(f'password {key}\n')
    
    # Set appropriate file permissions
    if os.name != 'nt':  # Unix-like systems
        os.chmod(netrc_path, 0o600)

def get_stored_credentials() -> Optional[Dict[str, str]]:
    """Get stored credentials from .netrc if they exist."""
    try:
        nrc = netrc(str(get_netrc_path()))
        auth = nrc.authenticators('api.getinstachip.com')
        if auth:
            return {
                'license_key': auth[0]
            }
    except (FileNotFoundError, NetrcParseError):
        pass
    return None

def authenticate_user(email: str, license_key: str) -> Dict:
    """Verify license key and store credentials."""
    response = requests.post(
        'https://getinstachip.com/api/auth',
        json={'license_key': license_key}
    )
    
    if response.status_code != 200:
        error_message = response.json().get('error', 'Unknown error')
        raise ValueError(f'Invalid license key: {error_message}')
        
    credentials = response.json()
    store_credentials(email, license_key)
    return credentials

def logout_user() -> None:
    """Clear stored credentials from .netrc file."""
    netrc_path = get_netrc_path()
    if not netrc_path.exists():
        return
    
    try:
        existing_netrc = netrc(str(netrc_path))
        entries = existing_netrc.hosts
    except NetrcParseError:
        entries = {}
    
    # Rewrite netrc file without our service entry
    with open(netrc_path, 'w') as netrc_file:
        for machine, auth in entries.items():
            if machine != 'api.getinstachip.com':
                login, account, password = auth
                netrc_file.write(f'machine {machine}\n')
                netrc_file.write(f'login {login}\n')
                if account:
                    netrc_file.write(f'account {account}\n')
                netrc_file.write(f'password {password}\n')

def require_auth(f):
    """Decorator to require authentication before running a command"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            creds = get_stored_credentials()
            if not creds:
                typer.echo("Authentication required. Please run 'vpx login' first.", err=True)
                raise typer.Exit(1)
            return f(*args, **kwargs)
        except (FileNotFoundError, NetrcParseError):
            typer.echo("Authentication required. Please get a license key from https://getinstachip.com or contact team@getinstachip.com", err=True)
            raise typer.Exit(1)
    return wrapper