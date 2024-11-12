import tkinter as tk
from tkinter import ttk
from .debug_window import DebugWindow
from typing import Optional, Dict, Any

class VPXLauncher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("VPX Design Suite")
        self.root.geometry("1600x900")
        
        # Configure style
        style = ttk.Style()
        style.configure('Tool.TFrame', padding=10)
        style.configure('Header.TLabel', font=('Helvetica', 16, 'bold'))
        style.configure('Tool.TButton', padding=5)
        
        # Create main container
        self.main_container = ttk.Frame(self.root)
        self.main_container.pack(expand=True, fill='both')
        
        # Add header
        self.header = ttk.Frame(self.main_container)
        self.header.pack(fill='x', padx=20, pady=10)
        
        ttk.Label(
            self.header, 
            text="VPX Design Suite", 
            style='Header.TLabel'
        ).pack(side='left')
        
        # Create tools container
        self.tools_container = ttk.Frame(self.main_container, style='Tool.TFrame')
        self.tools_container.pack(expand=True, fill='both', padx=20, pady=10)
        
        # Add tool sections
        self.create_design_tools()
        self.create_verification_tools()
        self.create_analysis_tools()
        
        # Store active windows
        self.active_windows: Dict[str, Any] = {}

    def create_design_tools(self):
        """Create design tools section"""
        frame = ttk.LabelFrame(self.tools_container, text="Design Tools", padding=10)
        frame.pack(fill='x', pady=5)
        
        ttk.Button(
            frame,
            text="RTL Designer",
            command=self.launch_rtl_designer,
            style='Tool.TButton'
        ).pack(side='left', padx=5)
        
        ttk.Button(
            frame,
            text="FSM Designer",
            command=self.launch_fsm_designer,
            style='Tool.TButton'
        ).pack(side='left', padx=5)

    def create_verification_tools(self):
        """Create verification tools section"""
        frame = ttk.LabelFrame(self.tools_container, text="Verification Tools", padding=10)
        frame.pack(fill='x', pady=5)
        
        ttk.Button(
            frame,
            text="RTL Debugger",
            command=self.launch_debugger,
            style='Tool.TButton'
        ).pack(side='left', padx=5)
        
        ttk.Button(
            frame,
            text="Testbench Generator",
            command=self.launch_testbench_generator,
            style='Tool.TButton'
        ).pack(side='left', padx=5)

    def create_analysis_tools(self):
        """Create analysis tools section"""
        frame = ttk.LabelFrame(self.tools_container, text="Analysis Tools", padding=10)
        frame.pack(fill='x', pady=5)
        
        ttk.Button(
            frame,
            text="Logic Analyzer",
            command=self.launch_logic_analyzer,
            style='Tool.TButton'
        ).pack(side='left', padx=5)
        
        ttk.Button(
            frame,
            text="Timing Analyzer",
            command=self.launch_timing_analyzer,
            style='Tool.TButton'
        ).pack(side='left', padx=5)

    def launch_rtl_designer(self):
        """Launch RTL Designer window"""
        if 'rtl_designer' not in self.active_windows:
            self.active_windows['rtl_designer'] = DebugWindow()
            self.active_windows['rtl_designer'].protocol(
                "WM_DELETE_WINDOW", 
                lambda: self.close_window('rtl_designer')
            )

    def launch_fsm_designer(self):
        """Launch FSM Designer window"""
        # TODO: Implement FSM Designer
        pass

    def launch_debugger(self):
        """Launch RTL Debugger window"""
        if 'debugger' not in self.active_windows:
            self.active_windows['debugger'] = DebugWindow()
            self.active_windows['debugger'].protocol(
                "WM_DELETE_WINDOW", 
                lambda: self.close_window('debugger')
            )

    def launch_testbench_generator(self):
        """Launch Testbench Generator window"""
        # TODO: Implement Testbench Generator
        pass

    def launch_logic_analyzer(self):
        """Launch Logic Analyzer window"""
        # TODO: Implement Logic Analyzer
        pass

    def launch_timing_analyzer(self):
        """Launch Timing Analyzer window"""
        # TODO: Implement Timing Analyzer
        pass

    def close_window(self, window_name: str):
        """Close a specific tool window"""
        if window_name in self.active_windows:
            self.active_windows[window_name].destroy()
            del self.active_windows[window_name]

    def run(self):
        """Start the launcher"""
        self.root.mainloop()

def launch_gui():
    """Launch the VPX GUI"""
    launcher = VPXLauncher()
    launcher.run() 