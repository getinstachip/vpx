import networkx as nx
# from sv_parser import parse_sv
from typing import List
import subprocess
import json
import xml.etree.ElementTree as ET
import re
import math
    
class Tool:
    def __init__(self, name, description):
        self.name = name
        self.description = description
        self.current_command = ""
        self.current_output = ""

    def __str__(self):
        return f"{self.name}: {self.description}"
    
    def run_command(self, command: str):
        self.current_command = command
        self.current_output = subprocess.run(command, shell=True, capture_output=True, text=True)
        print(self.current_command)
        return self.current_output

class IcarusVerilog(Tool):
    def __init__(self):
        super().__init__(
            "Icarus Verilog",
            "Icarus Verilog is a Verilog and SystemVerilog compiler and simulator."
        )
        self.error_types = json.loads(open("guides/iverilog_errors__compilation.json").read())['error_types']

    def _convert_format_to_regex(self, format_string):
        escaped_string = re.escape(format_string)
        
        regex_string = escaped_string.replace(r'\{filename\}', r'(?P<filename>[^:]+)')
        regex_string = regex_string.replace(r'\{line_number\}', r'(?P<line_number>\d+)')
        regex_string = regex_string.replace(r'\{module_name\}', r'(?P<module_name>[^ ]+)')
        regex_string = regex_string.replace(r'\{port_name\}', r'(?P<port_name>[^ ]+)')
        regex_string = regex_string.replace(r'\{param_name\}', r'(?P<param_name>[^ ]+)')
        regex_string = regex_string.replace(r'\{net_name\}', r'(?P<net_name>[^ ]+)')
        regex_string = regex_string.replace(r'\{error_message\}', r'(?P<error_message>.+)')
        
        return f'^{regex_string}$'

    def compile_files(self, output_file_path: str, input_file_paths: List[str]):
        print(f"Compiling and simulating with Icarus Verilog: {output_file_path} {input_file_paths}")
        self.run_command(f"iverilog -g2012 -o {output_file_path} {' '.join(input_file_paths)}")
        if not self.current_output.stdout and not self.current_output.stderr:
            return self.current_output, True
        else:
            return self.current_output, False
        
    def get_compile_errors(self):
        errors = []
        error_lines = self.current_output.stderr.split('\n')
        for line in error_lines:
            if line != "":
                print("Line:", line)
                error_type_index = 0
                matched = False
                while error_type_index < len(self.error_types) and not matched:
                    error_type = self.error_types[error_type_index]
                    format_string = error_type.get('format', '')
                    regex_pattern = self._convert_format_to_regex(format_string)
                    match = re.match(regex_pattern, line)

                    if match:
                        error_info = match.groupdict()
                        error_info['type'] = error_type.get('type', 'Unknown')
                        error_info['debug_steps'] = error_type.get('debug_steps', [])
                        errors.append(error_info)
                        matched = True

                    error_type_index += 1

                if not matched:
                    error_info = {
                        'type': 'Unknown',
                        'debug_steps': [],
                        'message': line
                    }
                    errors.append(error_info)
        return errors
    
    def get_sim_errors(self):
        return self.current_output.stderr


class LogicAnalyzer(Tool):
    def __init__(self):
        super().__init__(
            "Logic Analyzer",
            "Logic Analyzer is a tool that analyzes the digital logic structure of a SystemVerilog module."
        )

    def parse_sv(self, file_path: str):
        return ""

    def _analyze_logic_cone(self, file_path, output_signal):
        parse_result = self.parse_sv(file_path)
        if parse_result is None:
            raise ValueError(f"Failed to parse {file_path}")

        syntax_tree = parse_result[0]
        logic_cone = nx.DiGraph()
        clock_domains = set()
        sequential_elements = set()
        combinational_logic = set()
        inputs = set()
        constant_signals = set()
        
        def trace_dependencies(node):
            if node.kind == "Port":
                self._handle_port(node, logic_cone, inputs)
            elif node.kind == "NetDeclaration":
                self._handle_net_declaration(node, logic_cone)
            elif node.kind == "RegDeclaration":
                self._handle_reg_declaration(node, logic_cone, sequential_elements)
            elif node.kind == "ContinuousAssign":
                self._handle_continuous_assign(node, logic_cone, combinational_logic)
            elif node.kind == "AlwaysConstruct":
                self._handle_always_construct(node, logic_cone, clock_domains, sequential_elements)
            
            for child in node.children:
                trace_dependencies(child)

        output_node = self._find_output_node(syntax_tree, output_signal)
        if output_node:
            trace_dependencies(output_node)
        else:
            raise ValueError(f"Output signal {output_signal} not found")

        return {
            'logic_cone': logic_cone,
            'clock_domains': clock_domains,
            'sequential_elements': sequential_elements,
            'combinational_logic': combinational_logic,
            'inputs': inputs,
            'constant_signals': constant_signals
        }

    def _handle_port(self, node, logic_cone, inputs):
        direction = node.children[0].kind
        signal_name = node.children[1].value
        if direction == "Input":
            inputs.add(signal_name)
        logic_cone.add_node(signal_name, type=direction.lower())

    def _handle_net_declaration(self, node, logic_cone):
        logic_cone.add_node(node.children[1].value, type='wire')

    def _handle_reg_declaration(self, node, logic_cone, sequential_elements):
        signal_name = node.children[1].value
        sequential_elements.add(signal_name)
        logic_cone.add_node(signal_name, type='reg')

    def _handle_continuous_assign(self, node, logic_cone, combinational_logic):
        lhs = node.children[0].children[0].value
        rhs = node.children[1].value
        combinational_logic.add(lhs)
        logic_cone.add_node(lhs, type='assign')
        logic_cone.add_edge(rhs, lhs)

    def _handle_always_construct(self, node, logic_cone, clock_domains, sequential_elements):
        clock_node = next((c for c in node.children if c.kind == "EventControl"), None)
        if clock_node:
            clock_domains.add(clock_node.children[0].value)
        for child in node.children:
            if child.kind in ["BlockingAssignment", "NonblockingAssignment"]:
                lhs = child.children[0].value
                rhs = child.children[1].value
                sequential_elements.add(lhs)
                logic_cone.add_node(lhs, type='reg')
                logic_cone.add_edge(rhs, lhs)

    def _find_output_node(self, syntax_tree, output_signal):
        return next(
            (n for n in syntax_tree.iter()
             if n.kind == "Port"
             and n.children[0].kind == "Output"
             and n.children[1].value == output_signal),
            None
        )

    def _calculate_logic_depth(self, logic_cone):
        return max(nx.dag_longest_path_length(logic_cone), 0)

    def _identify_critical_path(self, logic_cone):
        return nx.dag_longest_path(logic_cone)

    def _detect_feedback_loops(self, logic_cone):
        return list(nx.simple_cycles(logic_cone))

    def _calculate_fanin_fanout(self, logic_cone):
        fanin = {node: logic_cone.in_degree(node) for node in logic_cone.nodes()}
        fanout = {node: logic_cone.out_degree(node) for node in logic_cone.nodes()}
        return {'fanin': fanin, 'fanout': fanout}

    def comprehensive_logic_cone_analysis(self, file_path, output_signal):
        basic_analysis = self._analyze_logic_cone(file_path, output_signal)
        logic_cone = basic_analysis['logic_cone']

        return {
            **basic_analysis,
            'logic_depth': self._calculate_logic_depth(logic_cone),
            'critical_path': self._identify_critical_path(logic_cone),
            'feedback_loops': self._detect_feedback_loops(logic_cone),
            'fanin_fanout': self._calculate_fanin_fanout(logic_cone)
        }
    
class CircuitVisualizer(Tool):
    def __init__(self, circuit_fpath: str):
        super().__init__(
            "Circuit Visualizer",
            "Circuit Visualizer is a tool that visualizes the digital logic structure of a SystemVerilog module."
        )
        self.circuit_fpath = circuit_fpath
        self.refresh_circuit(circuit_fpath)

    def refresh_circuit(self, circuit_fpath: str):
        self.circuit = open(circuit_fpath).read() if circuit_fpath != "" else None

    def render_diagram(self, diagram):
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="800" style="background-color: white;">'
        svg += '<defs><marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" /></marker></defs>'
        print("Diagram:", diagram)
        diagram = ET.fromstring(diagram)
        module = diagram.find('module')

        print("Module:", module)
        
        if module is not None:
            svg = self._draw_module_box(svg, module)
            svg, port_positions = self._draw_ports(svg, module.findall('ports/port'))
        
        components = diagram.findall('./*')
        component_positions = {}
        
        x, y = 200, 200
        for component in components:
            if component.tag != 'module':
                svg, x, y = self._draw_single_component(svg, component, x, y, component_positions)
        
        # Draw connections
        # for component in components:
        #     if component.tag != 'module':
        #         for input_port in component.findall('input'):
        #             input_name = input_port.get('name')
        #             if input_name in port_positions:
        #                 start_x, start_y = port_positions[input_name]
        #                 end_x, end_y = component_positions[component.get('name')]['left'][0]
        #                 svg += f'<line x1="{start_x}" y1="{start_y}" x2="{end_x}" y2="{end_y}" stroke="black" stroke-dasharray="5,5" />'
                
        #         for output_port in component.findall('output'):
        #             output_name = output_port.get('name')
        #             if output_name in port_positions:
        #                 start_x, start_y = component_positions[component.get('name')]['right'][0]
        #                 end_x, end_y = port_positions[output_name]
        #                 svg += f'<line x1="{start_x}" y1="{start_y}" x2="{end_x}" y2="{end_y}" stroke="black" stroke-dasharray="5,5" />'

        svg += '</svg>'

        with open(f'states/partial_diagram_{self.circuit_fpath}.svg', 'w') as f:
            f.write(svg)

        # emit("partial_diagram", svg)
        
        return svg

    def _draw_module_box(self, svg, module):
        svg += f'<rect x="100" y="100" width="800" height="600" fill="none" stroke="black" />'
        svg += f'<text x="500" y="80" text-anchor="middle" font-weight="bold" font-family="monospace" fill="black">{module.get("name")}</text>'
        return svg

    def _draw_ports(self, svg, ports):
        input_y, output_y = 130, 130
        port_positions = {}
        for port in ports:
            name = port.get('name')
            direction = port.get('direction')
            if direction == 'input':
                svg += f'<line x1="90" y1="{input_y}" x2="100" y2="{input_y}" stroke="black" />'
                svg += f'<text x="85" y="{input_y+5}" text-anchor="end" font-size="12" font-family="monospace" fill="black">{name}</text>'
                port_positions[name] = (100, input_y)
                input_y += 30
            else:
                svg += f'<line x1="900" y1="{output_y}" x2="910" y2="{output_y}" stroke="black" />'
                svg += f'<text x="915" y="{output_y+5}" text-anchor="start" font-size="12" font-family="monospace" fill="black">{name}</text>'
                port_positions[name] = (900, output_y)
                output_y += 30
        return svg, port_positions

    def _draw_components(self, svg, components, connections):
        left_comp_x, left_comp_y = 150, 150
        right_comp_x, right_comp_y = 750, 150
        component_positions = {}
        state_machine = None

        connection_count = {comp.get('name'): {'input': 0, 'output': 0} for comp in components}
        for connection in connections:
            from_comp = connection.get('from').split('.')[0]
            to_comp = connection.get('to').split('.')[0]
            if from_comp in connection_count:
                connection_count[from_comp]['output'] += 1
            if to_comp in connection_count:
                connection_count[to_comp]['input'] += 1

        left_components = []
        right_components = []
        middle_components = []

        for component in components:
            if component.tag == 'state_machine':
                state_machine = component
                continue

            name = component.get('name')
            input_count = connection_count[name]['input']
            output_count = connection_count[name]['output']

            if input_count > output_count:
                left_components.append((component, input_count))
            elif output_count > input_count:
                right_components.append((component, output_count))
            else:
                middle_components.append(component)

        left_components.sort(key=lambda x: x[1], reverse=True)
        right_components.sort(key=lambda x: x[1], reverse=True)

        for component, _ in left_components:
            svg, left_comp_x, left_comp_y = self._draw_single_component(svg, component, left_comp_x, left_comp_y, component_positions)

        middle_comp_x = (left_comp_x + right_comp_x) / 2
        middle_comp_y = 150
        for component in middle_components:
            svg, middle_comp_x, middle_comp_y = self._draw_single_component(svg, component, middle_comp_x, middle_comp_y, component_positions)

        for component, _ in right_components:
            svg, right_comp_x, right_comp_y = self._draw_single_component(svg, component, right_comp_x, right_comp_y, component_positions)

        return svg, component_positions, state_machine

    def _draw_single_component(self, svg, component, comp_x, comp_y, component_positions):
        name = component.get('name') or component.tag
        width, height = 160, 80

        if comp_y + height > 650:
            comp_y = 150
            comp_x += width + 60

        svg += f'<rect x="{comp_x}" y="{comp_y}" width="{width}" height="{height}" fill="none" stroke="black" />'
        svg += f'<text x="{comp_x+width/2}" y="{comp_y+height/2}" text-anchor="middle" font-size="12" font-family="monospace" fill="black">{name}</text>'

        inputs = component.findall('input')
        outputs = component.findall('output')

        for i, input in enumerate(inputs):
            y = comp_y + (i + 1) * height / (len(inputs) + 1)
            svg += f'<line x1="{comp_x-10}" y1="{y}" x2="{comp_x}" y2="{y}" stroke="black" />'
            svg += f'<text x="{comp_x-15}" y="{y+5}" text-anchor="end" font-size="10" font-family="monospace" fill="black">{input.get("name")}</text>'

        for i, output in enumerate(outputs):
            y = comp_y + (i + 1) * height / (len(outputs) + 1)
            svg += f'<line x1="{comp_x+width}" y1="{y}" x2="{comp_x+width+10}" y2="{y}" stroke="black" />'
            svg += f'<text x="{comp_x+width+15}" y="{y+5}" text-anchor="start" font-size="10" font-family="monospace" fill="black">{output.get("name")}</text>'

        component_positions[name] = {
            'left': [(comp_x-10, comp_y+(i+1)*height/(len(inputs)+1)) for i in range(len(inputs))],
            'right': [(comp_x+width+10, comp_y+(i+1)*height/(len(outputs)+1)) for i in range(len(outputs))]
        }

        return svg, comp_x, comp_y + height + 60

    def _draw_state_machine(self, svg, state_machine):
        svg += '<g transform="translate(950, 100)">'
        svg += f'<rect x="50" y="50" width="300" height="400" fill="none" stroke="black" stroke-width="2" />'
        svg += f'<text x="200" y="30" text-anchor="middle" font-weight="bold" font-family="monospace" fill="black">{state_machine.get("name")}</text>'
        
        states = state_machine.findall('state')
        state_positions = {}
        for i, state in enumerate(states):
            x = 100 + (i % 2) * 150
            y = 100 + (i // 2) * 100
            svg += f'<circle cx="{x}" cy="{y}" r="30" fill="none" stroke="black" />'
            svg += f'<text x="{x}" y="{y}" text-anchor="middle" dominant-baseline="central" font-family="monospace" fill="black">{state.get("name")}</text>'
            state_positions[state.get("name")] = (x, y)
        
        for state in states:
            from_x, from_y = state_positions[state.get("name")]
            for transition in state.findall('transition'):
                to_state = transition.get("to")
                to_x, to_y = state_positions[to_state]
                condition = transition.get("condition")
                
                angle = math.atan2(to_y - from_y, to_x - from_x)
                
                start_x = from_x + 30 * math.cos(angle)
                start_y = from_y + 30 * math.sin(angle)
                end_x = to_x - 30 * math.cos(angle)
                end_y = to_y - 30 * math.sin(angle)
                
                control_x = (start_x + end_x) / 2 + 30 * math.sin(angle)
                control_y = (start_y + end_y) / 2 - 30 * math.cos(angle)
                svg += f'<path d="M{start_x},{start_y} Q{control_x},{control_y} {end_x},{end_y}" fill="none" stroke="black" stroke-width="2" marker-end="url(#arrowhead)" />'
                
                label_x = control_x + 10 * math.sin(angle)
                label_y = control_y - 10 * math.cos(angle)
                svg += f'<text x="{label_x}" y="{label_y}" text-anchor="middle" dominant-baseline="central" font-family="monospace" fill="black" font-size="10">{condition}</text>'
        
        svg += '</g>'
        return svg

    def _draw_connections(self, svg, connections, component_positions, port_positions):
        connection_paths = []
        for connection in connections:
            from_component = connection.get('from')
            to = connection.get('to')
            if '.' in from_component:
                from_component, from_port = from_component.split('.')
            else:
                from_port = None
            if '.' in to:
                to_component, to_port = to.split('.')
            else:
                to_component = to
                to_port = None

            start_x, start_y = None, None
            end_x, end_y = None, None

            if from_component in component_positions:
                if from_port and 'right' in component_positions[from_component] and component_positions[from_component]['right']:
                    port_index = next((i for i, port in enumerate(component_positions[from_component]['right']) if len(port) > 2 and port[2] == from_port), 0)
                    start_x, start_y = component_positions[from_component]['right'][port_index][:2]
                elif 'right' in component_positions[from_component] and component_positions[from_component]['right']:
                    start_x, start_y = component_positions[from_component]['right'][0][:2]
                else:
                    start_x, start_y = component_positions[from_component].get('center', (0, 0))
            elif from_component in port_positions:
                start_x, start_y = port_positions[from_component]

            if to_component in component_positions:
                if to_port and 'left' in component_positions[to_component] and component_positions[to_component]['left']:
                    port_index = next((i for i, port in enumerate(component_positions[to_component]['left']) if len(port) > 2 and port[2] == to_port), 0)
                    end_x, end_y = component_positions[to_component]['left'][port_index][:2]
                elif 'left' in component_positions[to_component] and component_positions[to_component]['left']:
                    end_x, end_y = component_positions[to_component]['left'][0][:2]
                else:
                    end_x, end_y = component_positions[to_component].get('center', (0, 0))
            elif to_component in port_positions:
                end_x, end_y = port_positions[to_component]

            if start_x is not None and start_y is not None and end_x is not None and end_y is not None:
                # Calculate control points for a curved path
                mid_x = (start_x + end_x) / 2
                mid_y = (start_y + end_y) / 2
                control_x = mid_x + (end_y - start_y) / 4
                control_y = mid_y - (end_x - start_x) / 4

                path = f'M{start_x},{start_y} Q{control_x},{control_y} {end_x},{end_y}'
                connection_paths.append(path)

        # Sort paths by length to draw longer paths first
        connection_paths.sort(key=lambda p: self._path_length(p), reverse=True)

        for path in connection_paths:
            svg += f'<path d="{path}" fill="none" stroke="blue" stroke-dasharray="5,5" />'
            # Add small circular dots at the beginning and endpoint of the connection
            # start_x, start_y = map(float, path.split()[1].split(','))
            # end_x, end_y = map(float, path.split()[-1].split(','))
            # svg += f'<circle cx="{start_x}" cy="{start_y}" r="3" fill="blue" />'
            # svg += f'<circle cx="{end_x}" cy="{end_y}" r="3" fill="blue" />'

        return svg

    def _path_length(self, path):
        # Estimate path length for sorting
        points = re.findall(r'[MQ]\s*(-?\d+\.?\d*),(-?\d+\.?\d*)', path)
        return sum(math.sqrt((float(x2)-float(x1))**2 + (float(y2)-float(y1))**2) for (x1, y1), (x2, y2) in zip(points, points[1:]))

    def to_svg(self) -> str:
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="800" style="background-color: white;">'
        svg += '<defs><marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" /></marker></defs>'
        
        module = ET.fromstring(self.circuit)
        
        svg = self._draw_module_box(svg, module)
        svg, port_positions = self._draw_ports(svg, module.find('ports'))
        
        all_components = []
        state_machine = None
        for component in module.find('components'):
            if component.tag == 'state_machine':
                state_machine = component
            else:
                all_components.append(component)
        
        svg, component_positions, _ = self._draw_components(svg, all_components, module.find('connections'))
        svg = self._draw_connections(svg, module.find('connections'), component_positions, port_positions)
        
        if state_machine is not None:
            svg = self._draw_state_machine(svg, state_machine)
        
        svg += '</svg>'

        svg_file_path = "states/circuit_diagram.svg"
        with open(svg_file_path, "w") as f:
            f.write(svg)
        print(f"Circuit diagram SVG saved to {svg_file_path}")
        return svg

    # def svg_to_png(self, svg_code: str):
    #     svg2png(bytestring=svg_code, write_to="states/circuit_diagram.png", background_color='white')
        
    def run(self):
        self.refresh_circuit(self.circuit_fpath)
        svg: str = self.to_svg()
        print(svg)
        # emit('circuit_diagram', svg)
        # self.svg_to_png(svg)

class StateMachineExtractor(Tool):
    def __init__(self, sv_code: str):
        super().__init__(
            "State Machine Extractor",
            "State Machine Extractor is a tool that extracts the state machine from a SystemVerilog module."
        )
        self.sv_code = sv_code
        self.states = []
        self.transitions = []
        self.outputs = {}

    def extract_states(self):
        enum_pattern = r'typedef enum.*?{(.*?)}\s*\w+;'
        enums_found = re.findall(enum_pattern, self.sv_code, re.DOTALL)
        for enum in enums_found:
            states = [state.strip() for state in enum.split(',')]
            self.states.extend(states)

    def extract_transitions(self):
        case_pattern = r'case\s*\((.*?)\)(.*?)endcase'
        case_blocks = re.findall(case_pattern, self.sv_code, re.DOTALL)
        
        for case_var, case_content in case_blocks:
            if 'state' in case_var.lower():
                state_transitions = re.findall(r'(\w+)\s*:(.*?)(?=\w+\s*:|$)', case_content, re.DOTALL)
                for from_state, transition in state_transitions:
                    next_state_match = re.search(r'next_state\s*=\s*(\w+)', transition)
                    if next_state_match:
                        to_state = next_state_match.group(1)
                        self.transitions.append({'from': from_state, 'to': to_state})

    def extract_outputs(self):
        always_comb_pattern = r'always_comb\s*begin(.*?)end'
        always_comb_blocks = re.findall(always_comb_pattern, self.sv_code, re.DOTALL)
        
        for block in always_comb_blocks:
            case_pattern = r'case\s*\((.*?)\)(.*?)endcase'
            case_blocks = re.findall(case_pattern, block, re.DOTALL)
            
            for case_var, case_content in case_blocks:
                if 'state' in case_var.lower():
                    state_outputs = re.findall(r'(\w+)\s*:(.*?)(?=\w+\s*:|$)', case_content, re.DOTALL)
                    for state, outputs in state_outputs:
                        output_assignments = re.findall(r'(\w+)\s*=\s*([^;]+)', outputs)
                        self.outputs[state] = {var: value.strip() for var, value in output_assignments}

    def to_json(self):
        return json.dumps({
            'states': self.states,
            'transitions': self.transitions,
            'outputs': self.outputs
        }, indent=2)

    def extract_state_machine(self):
        self.extract_states()
        self.extract_transitions()
        self.extract_outputs()
        return self.to_json()