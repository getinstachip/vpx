from typer.testing import CliRunner
from vpx.cli import app
from pathlib import Path
import pytest

runner = CliRunner()

def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "vpx v0.1.0" in result.stdout

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

def test_diann_missing_input():
    result = runner.invoke(app, ["diann", "nonexistent.raw", "output"])
    assert result.exit_code == 2  # Typer exits with 2 for argument validation errors
    assert "does not exist" in result.stdout

@pytest.fixture
def sample_input(tmp_path):
    input_file = tmp_path / "input.raw"
    input_file.touch()
    return input_file

@pytest.fixture
def sample_config(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.touch()
    return config_file

def test_diann_basic(sample_input, tmp_path):
    output_dir = tmp_path / "output"
    result = runner.invoke(app, ["diann", str(sample_input), str(output_dir)])
    assert result.exit_code == 0
    assert "DIA-NN analysis completed" in result.stdout

def test_diann_with_config(sample_input, sample_config, tmp_path):
    output_dir = tmp_path / "output"
    result = runner.invoke(app, [
        "diann",
        str(sample_input),
        str(output_dir),
        "--config",
        str(sample_config)
    ])
    assert result.exit_code == 0
    assert "DIA-NN analysis completed" in result.stdout 
