from typer.testing import CliRunner
from vpm.cli import app

runner = CliRunner()

def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "vpm v0.1.0" in result.stdout

def test_hello():
    result = runner.invoke(app, ["hello", "John"])
    assert result.exit_code == 0
    assert "Hello John" in result.stdout

def test_goodbye():
    result = runner.invoke(app, ["goodbye", "John"])
    assert result.exit_code == 0
    assert "Bye John!" in result.stdout

def test_formal_goodbye():
    result = runner.invoke(app, ["goodbye", "John", "--formal"])
    assert result.exit_code == 0
    assert "Goodbye Mr. John. Have a good day." in result.stdout 