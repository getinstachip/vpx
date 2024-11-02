from typing import Optional
import typer
from pathlib import Path
import json
import os
from . import __app_name__, __version__
from .diann.helper_agents import Diann
from .auth import authenticate_user, get_credentials_path

app = typer.Typer()

def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"{__app_name__} v{__version__}")
        raise typer.Exit()

@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show the application's version and exit.",
        callback=_version_callback,
        is_eager=True,
    )
) -> None:
    return

@app.command()
def implement(
    prompt: str = typer.Argument(..., help="The prompt to run DIANN with"),
) -> None:
    diann = Diann(
        solution_folder="solutions",
        specification=prompt,
        verbose=True
    )
    diann.run()

@app.command()
def login(
    license_key: str = typer.Option(..., prompt=True, help="Your VPX license key"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-authentication")
) -> None:
    """Authenticate with VPX using your license key"""
    try:
        credentials = authenticate_user(license_key)
        
        # Save credentials
        creds_path = get_credentials_path()
        creds_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(creds_path, 'w') as f:
            json.dump(credentials, f)
            
        typer.echo("Successfully authenticated with VPX! 🎉")
        
    except Exception as e:
        typer.echo(f"Authentication failed: {str(e)}", err=True)
        raise typer.Exit(1)

@app.command()
def logout() -> None:
    """Clear saved VPX credentials"""
    creds_path = get_credentials_path()
    if creds_path.exists():
        creds_path.unlink()
        typer.echo("Successfully logged out of VPX")
    else:
        typer.echo("No active VPX session found")