import svgwrite
from typing import List, Dict, Tuple
import re

class RTLVisualizer:
    def __init__(self, rtl_content: str):
        self.rtl_content = rtl_content
        self.ports = self._extract_ports()
        
    def _extract_ports(self) -> Dict[str, List[Dict[str, str]]]:
        """Extract ports from RTL content"""
        ports = {"input": [], "output": [], "inout": []}
        
        # Find module declaration
        module_match = re.search(r'module\s+\w+\s*\((.*?)\);', self.rtl_content, re.DOTALL)
        if not module_match:
            return ports
            
        port_list = module_match.group(1)
        port_declarations = [p.strip() for p in port_list.split(',')]
        
        for decl in port_declarations:
            parts = decl.strip().split()
            if not parts:
                continue
                
            direction = parts[0] if parts[0] in ['input', 'output', 'inout'] else None
            if not direction:
                continue
                
            # Handle vector ports
            width = 1
            name = parts[-1].replace(';', '')
            width_match = re.search(r'\[(\d+):0\]', decl)
            if width_match:
                width = int(width_match.group(1)) + 1
                
            ports[direction].append({
                "name": name,
                "width": width
            })
            
        return ports
        
    def generate_svg(self, width: int = 400, height: int = 300) -> str:
        """Generate SVG representation of the module"""
        dwg = svgwrite.Drawing(size=(width, height))
        
        # Module box
        box_margin = 40
        box_width = width - 2 * box_margin
        box_height = height - 2 * box_margin
        
        # Draw module box
        dwg.add(dwg.rect(
            (box_margin, box_margin),
            (box_width, box_height),
            fill='white',
            stroke='black',
            stroke_width=2
        ))
        
        # Calculate pin spacing
        max_pins = max(
            len(self.ports["input"]),
            len(self.ports["output"])
        )
        pin_spacing = box_height / (max_pins + 1) if max_pins > 0 else box_height/2
        
        # Draw input pins
        for i, port in enumerate(self.ports["input"], 1):
            y = box_margin + i * pin_spacing
            # Pin line
            dwg.add(dwg.line(
                (0, y),
                (box_margin, y),
                stroke='black',
                stroke_width=2
            ))
            # Port name
            dwg.add(dwg.text(
                port["name"],
                insert=(box_margin + 5, y + 5),
                font_size='12px'
            ))
            # Width indicator if > 1
            if port["width"] > 1:
                dwg.add(dwg.text(
                    f'[{port["width"]-1}:0]',
                    insert=(box_margin + 5, y - 5),
                    font_size='10px',
                    fill='blue'
                ))
        
        # Draw output pins
        for i, port in enumerate(self.ports["output"], 1):
            y = box_margin + i * pin_spacing
            # Pin line
            dwg.add(dwg.line(
                (box_margin + box_width, y),
                (width, y),
                stroke='black',
                stroke_width=2
            ))
            # Port name
            dwg.add(dwg.text(
                port["name"],
                insert=(box_margin + box_width - 50, y + 5),
                font_size='12px',
                text_anchor='end'
            ))
            # Width indicator if > 1
            if port["width"] > 1:
                dwg.add(dwg.text(
                    f'[{port["width"]-1}:0]',
                    insert=(box_margin + box_width - 50, y - 5),
                    font_size='10px',
                    fill='blue',
                    text_anchor='end'
                ))
        
        return dwg.tostring() 