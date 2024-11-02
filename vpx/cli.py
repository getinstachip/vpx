from typing import Optional
import typer
from pathlib import Path
import json
import os
from . import __app_name__, __version__
from .diann.helper_agents import Diann
from .auth import authenticate_user, get_stored_credentials, logout_user, require_auth

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
@require_auth
def implement(
    prompt: str = typer.Argument(..., help="The prompt to run implementation with"),
) -> None:
    diann = Diann(
        solution_folder="solutions",
        specification=prompt,
        verbose=True
    )
    diann.run()

@app.command()
def login(
    email: str = typer.Option(..., prompt=True, help="Any email"),
    license_key: str = typer.Option(..., prompt=True, help="Your VPX license key"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-authentication")
) -> None:
    """Authenticate with VPX using your license key"""
    if not force:
        existing_creds = get_stored_credentials()
        if existing_creds:
            typer.echo("Already authenticated. Use --force to re-authenticate.")
            return

    try:
        authenticate_user(email, license_key)
        typer.echo("Successfully authenticated with VPX! 🎉")
    except Exception as e:
        typer.echo(f"Authentication failed: {str(e)}", err=True)
        raise typer.Exit(1)

@app.command()
def logout() -> None:
    """Clear saved VPX credentials"""
    try:
        logout_user()
        typer.echo("Successfully logged out of VPX")
    except Exception as e:
        typer.echo(f"Logout failed: {str(e)}", err=True)
        raise typer.Exit(1)