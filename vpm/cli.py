from typing import Optional
import typer
from . import __app_name__, __version__

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
def hello(
    name: str = typer.Argument(..., help="The name of the person to greet"),
) -> None:
    """Greet someone by name."""
    typer.echo(f"Hello {name}")

@app.command()
def goodbye(
    name: str = typer.Argument(..., help="The name of the person to bid farewell"),
    formal: bool = typer.Option(
        False,
        "--formal",
        "-f",
        help="Use formal farewell message"
    ),
) -> None:
    """Say goodbye to someone."""
    if formal:
        typer.echo(f"Goodbye Mr. {name}. Have a good day.")
    else:
        typer.echo(f"Bye {name}!") 