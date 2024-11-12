import typer
from typing import Optional, List, Dict
import os
from vpx import __app_name__, __version__
from vpx.diann.helper_agents import Diann, DesignVerifier
from vpx.auth import authenticate_user, get_stored_credentials, logout_user, require_auth
from vpx.gui.debug_window import DebugWindow
from colorama import init, Fore, Style
import subprocess
import tempfile

app = typer.Typer()

# Add the ASCII art banner with proper escaping
BANNER = f"""
{Fore.RED}  ____  {Fore.YELLOW}/ /_    {Fore.GREEN} ____ {Fore.CYAN}___  {Fore.BLUE}__  {Fore.MAGENTA}__  {Style.RESET_ALL}
{Fore.RED} / __ \\{Fore.YELLOW}/ __ \\   {Fore.GREEN}/ __ {Fore.CYAN}`__ \\{Fore.BLUE}/ / {Fore.MAGENTA}/ /  {Style.RESET_ALL}
{Fore.RED}/ /_/ {Fore.YELLOW}/ / / /  {Fore.GREEN}/ / /{Fore.CYAN} / / {Fore.BLUE}/ /_{Fore.MAGENTA}/ /   {Style.RESET_ALL}
{Fore.RED}\\____/{Fore.YELLOW}_/ /_/  {Fore.GREEN}/_/ /_{Fore.CYAN}/ /_/{Fore.BLUE}\\__,{Fore.MAGENTA}_/    {Style.RESET_ALL}
"""

def version_callback(value: bool) -> None:
    if value:
        init()  # Initialize colorama
        typer.echo(BANNER)
        typer.echo(f"{__app_name__} v{__version__}")
        raise typer.Exit()

@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show the application's version and exit.",
        callback=version_callback,
        is_eager=True,
    )
) -> None:
    """
    VPX - Verilog Processing Extensions
    """
    return

@app.command()
# @require_auth
def implement(prompt: str = typer.Argument(..., help="The prompt to run implementation with")):
    """
    Run implementation with the given prompt and show live progress in GUI.
    """
    # Launch GUI first
    window = DebugWindow()
    
    # Create Diann instance with GUI callback
    diann = Diann(
        solution_folder="solutions", 
        specification=prompt, 
        verbose=True,
        gui_callback=window.update_implementation_progress
    )
    
    # Run implementation (will update GUI via callback)
    rtl = diann.run()
    
    # Create temporary file for final RTL
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sv', delete=False) as tmp_file:
        tmp_file.write(rtl)
        tmp_file.flush()
        window.load_rtl_file(tmp_file.name)
        
        # Show timing diagram if available
        if diann.context and diann.context.timing_plan:
            vcd_file = window.generate_timing_vcd(diann.context.timing_plan)
            if vcd_file:
                try:
                    subprocess.Popen(['gtkwave', vcd_file])
                except FileNotFoundError:
                    typer.echo("GTKWave not found. Please install GTKWave to view timing diagrams.")
        
        # Start GUI main loop
        window.mainloop()
        
        # Cleanup
        os.unlink(tmp_file.name)

@app.command()
def login(
    email: str = typer.Option(..., prompt=True),
    license_key: str = typer.Option(..., prompt=True),
    force: bool = typer.Option(False, "--force", "-f")
):
    """
    Login to VPX.

    Options:
        --email: Your email address
        --license-key: Your VPX license key
        --force, -f: Force re-authentication even if already logged in
    """
    if not force and get_stored_credentials():
        typer.echo("Already authenticated. Use --force to re-authenticate.")
        return
    try:
        authenticate_user(email, license_key)
        typer.echo("Successfully authenticated!")
    except Exception as e:
        typer.echo(f"Authentication failed: {str(e)}", err=True)
        raise typer.Exit(1)

@app.command()
def logout():
    """Clear saved VPX credentials."""
    try:
        logout_user()
        typer.echo("Successfully logged out")
    except Exception as e:
        typer.echo(f"Logout failed: {str(e)}", err=True)
        raise typer.Exit(1)

@app.command()
def debug_gui(
    rtl_files: Optional[List[str]] = typer.Argument(
        None, 
        help="Optional list of RTL files or directories to load in file explorer",
        exists=True,  # Verify files/directories exist
    )
):
    """
    Launch the graphical debug interface.

    Arguments:
        rtl_files: Optional list of RTL files (.v, .sv) or directories to show in file explorer
    """
    try:
        window = DebugWindow()
        
        if rtl_files:
            # Get absolute paths
            abs_paths = [os.path.abspath(f) for f in rtl_files]
            
            # If single file provided, load it
            if len(abs_paths) == 1 and os.path.isfile(abs_paths[0]):
                window.load_rtl_file(abs_paths[0])
            
            # Set file explorer to parent directory of first file/directory
            first_path = abs_paths[0]
            start_dir = os.path.dirname(first_path) if os.path.isfile(first_path) else first_path
            window.set_explorer_path(start_dir)
            
            # Filter files to show only provided files
            window.set_explorer_filter(abs_paths)
            
        window.mainloop()
    except Exception as e:
        typer.echo(f"Error launching GUI: {str(e)}", err=True)
        raise typer.Exit(1)

@app.command()
def debug_logic_cone(
    output_signal: str = typer.Argument(..., help="Output signal to analyze"),
    rtl_file: str = typer.Option(..., "--rtl", "-r", help="RTL file path")
):
    """
    Analyze logic cone for an output signal.

    Arguments:
        output_signal: Name of the output signal to analyze

    Options:
        --rtl, -r: Path to the RTL file to analyze
    """
    try:
        verifier = DesignVerifier(context=None, rtl=None, verbose=True)
        with open(rtl_file, 'r') as f:
            verifier.rtl = f.read()
        result = verifier.analyze_logic_cone(output_signal)
        
        typer.echo(f"\nLogic Cone Analysis for {output_signal}:")
        typer.echo("-" * 40)
        for section in ["inputs", "intermediate"]:
            typer.echo(f"\n{section.title()} ({len(result[section])}):")
            for signal in result[section]:
                typer.echo(f"  - {signal}")
        typer.echo(f"\nLogic Depth: {result['depth']}")
        typer.echo("\nExpressions:")
        for signal, expr in result['expressions'].items():
            typer.echo(f"  {signal} = {expr}")
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)

@app.command()
def debug_test_vectors(
    rtl_file: str = typer.Option(..., "--rtl", "-r", help="RTL file path"),
    num: int = typer.Option(20, "--num", "-n", help="Number of vectors"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file")
):
    """
    Generate test vectors.

    Options:
        --rtl, -r: Path to the RTL file to analyze
        --num, -n: Number of test vectors to generate (default: 20)
        --output, -o: Optional file to save the vectors to
    """
    try:
        verifier = DesignVerifier(context=None, rtl=None, verbose=True)
        with open(rtl_file, 'r') as f:
            verifier.rtl = f.read()
        vectors = verifier.generate_test_vectors(num)
        
        result = "Test Vectors:\n" + "-" * 40 + "\n"
        for i, vector in enumerate(vectors, 1):
            result += f"\nVector {i}:\n"
            for signal, value in vector.items():
                result += f"  {signal} = {value}\n"
                
        if output:
            with open(output, 'w') as f:
                f.write(result)
            typer.echo(f"Vectors written to {output}")
        else:
            typer.echo(result)
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)

@app.command()
def debug_gen_tb(
    rtl_file: str = typer.Option(..., "--rtl", "-r", help="RTL file path"),
    vectors: Optional[str] = typer.Option(None, "--vectors", "-v", help="Test vectors file"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file")
):
    """
    Generate testbench.

    Options:
        --rtl, -r: Path to the RTL file to analyze
        --vectors, -v: Optional file containing test vectors
        --output, -o: Optional file to save the testbench to
    """
    try:
        verifier = DesignVerifier(context=None, rtl=None, verbose=True)
        with open(rtl_file, 'r') as f:
            verifier.rtl = f.read()
            
        if vectors:
            with open(vectors, 'r') as f:
                test_vector = {}  # TODO: Parse vectors file
        else:
            test_vector = verifier.generate_test_vectors(1)[0]
            
        testbench = verifier.generate_testbench(test_vector)
        
        if output:
            with open(output, 'w') as f:
                f.write(testbench)
            typer.echo(f"Testbench written to {output}")
        else:
            typer.echo(testbench)
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)

@app.command()
def launch_gui():
    """Launch the VPX GUI"""
    from .gui.launcher import launch_gui
    launch_gui()

@app.command()
def verify(
    rtl_files: List[str] = typer.Argument(
        ..., 
        help="List of RTL files (.sv) to verify",
        exists=True,
    ),
    test_dir: Optional[str] = typer.Option(
        None,
        "--test-dir", 
        "-t",
        help="Directory containing test cases"
    ),
    gui: bool = typer.Option(
        True,
        "--gui/--no-gui",
        help="Launch GUI for verification results"
    )
):
    """
    Run comprehensive simulation-based verification on RTL files.
    
    Arguments:
        rtl_files: List of SystemVerilog files to verify
        
    Options:
        --test-dir, -t: Directory containing test cases
        --gui/--no-gui: Enable/disable GUI (default: enabled)
    """
    try:
        # Create verifier instance
        verifier = DesignVerifier(
            context=None,
            rtl=None,
            verbose=True
        )
        
        # Load all RTL files
        rtl_content = ""
        for file in rtl_files:
            with open(file, 'r') as f:
                rtl_content += f.read() + "\n"
        verifier.rtl = rtl_content
        
        # Launch GUI if enabled
        window = None
        if gui:
            window = DebugWindow()
            window.load_rtl_files(rtl_files)
        
        # Run verification flow
        results = verifier.run_verification(
            test_dir=test_dir,
            gui_callback=window.update_verification_progress if window else None
        )
        
        # Show results in GUI or console
        if window:
            window.show_verification_results(results)
            window.mainloop()
        else:
            _print_verification_results(results)
            
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)

def _print_verification_results(results: Dict):
    """Print verification results to console"""
    typer.echo("\nVerification Results:")
    typer.echo("-" * 40)
    
    # Print test case results
    typer.echo("\nTest Cases:")
    for test in results.get('test_cases', []):
        status = "✓" if test['passed'] else "✗"
        typer.echo(f"  {status} {test['name']}")
        if not test['passed']:
            typer.echo(f"    Error: {test['error']}")
            
    # Print assertion results
    typer.echo("\nAssertions:")
    for assertion in results.get('assertions', []):
        status = "✓" if assertion['passed'] else "✗"
        typer.echo(f"  {status} {assertion['name']}")
        if not assertion['passed']:
            typer.echo(f"    Failed at: {assertion['failure_point']}")
            
    # Print coverage results
    coverage = results.get('coverage', {})
    typer.echo("\nCoverage:")
    typer.echo(f"  Line Coverage: {coverage.get('line', 0)}%")
    typer.echo(f"  Branch Coverage: {coverage.get('branch', 0)}%")
    typer.echo(f"  FSM Coverage: {coverage.get('fsm', 0)}%")

if __name__ == "__main__":
    app()