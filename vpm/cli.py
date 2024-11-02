from typing import Optional
import typer
from . import __app_name__, __version__
from .diann.helper_agents import Diann
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