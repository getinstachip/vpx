from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Set, Tuple, Callable
import os
import datetime
import re
from .agent import Agent
from enum import Enum, auto
from dataclasses import dataclass, field
from random import randint
import json
import tempfile
import subprocess
import random

# Core data structures for module hierarchy
@dataclass
class SubmodulePort:
    """Represents a port in a module"""
    name: str
    direction: str  # 'input' or 'output'
    width: int = 1
    description: str = ""

@dataclass
class SubmoduleConnection:
    """Represents a connection between module ports"""
    from_module: str
    from_port: str
    to_module: str
    to_port: str
    description: str = ""

@dataclass
class SubmoduleInfo:
    """Contains all information about a submodule"""
    name: str
    instance_name: str
    description: str = ""
    ports: List[SubmodulePort] = field(default_factory=list)
    connections: List[SubmoduleConnection] = field(default_factory=list)
    parent: Optional[str] = None
    specification: Optional[str] = None
    rtl: Optional[str] = None
    fsm_spec: Optional[str] = None

@dataclass
class ModuleHierarchy:
    """Manages the complete module hierarchy"""
    top_module: str
    submodules: Dict[str, SubmoduleInfo] = field(default_factory=dict)
    
    def add_submodule(self, name: str, instance_name: str, parent: Optional[str] = None) -> SubmoduleInfo:
        """Add a new submodule to the hierarchy"""
        if name not in self.submodules:
            self.submodules[name] = SubmoduleInfo(name=name, instance_name=instance_name, parent=parent)
        return self.submodules[name]
    
    def get_children(self, module_name: str) -> List[SubmoduleInfo]:
        """Get direct child modules"""
        return [m for m in self.submodules.values() if m.parent == module_name]
    
    def get_module_path(self, module_name: str) -> List[str]:
        """Get path from top module to given module"""
        path = []
        current = module_name
        while current:
            path.append(current)
            current = self.submodules[current].parent if current in self.submodules else None
        return list(reversed(path))

# Core data structures for design
@dataclass
class Requirements:
    module_interface: Optional[str] = None
    components: Optional[str] = None
    fsm: Optional[str] = None
    timing: Optional[str] = None
    hierarchy: Optional[ModuleHierarchy] = None

@dataclass
class TimingPlan:
    cycle_diagram: Optional[str] = None
    register_deps: Optional[str] = None
    critical_paths: Optional[str] = None

@dataclass
class FSMPlan:
    state_info: Optional[str] = None    
    output_logic: Optional[str] = None  

@dataclass 
class DesignContext:
    specification: str
    requirements: Optional[Requirements] = None
    fsm_plan: Optional[FSMPlan] = None
    timing_plan: Optional[TimingPlan] = None
    hierarchy: Optional[ModuleHierarchy] = None
    rtl: Optional[str] = None
    submodules: Dict[str, 'DesignContext'] = field(default_factory=dict)

class DesignPlanner(Agent):
    def __init__(self, specification: str, verbose: bool = False, gui_callback = None):
        super().__init__(
            system_prompt="You are a digital design architect specializing in requirements analysis and design planning.",
            tools={},
            context="",
            verbose=verbose
        )
        self.context = DesignContext(specification=specification)
        self.needs_fsm = False
        self.output_dir = "outputs"
        self.run_dir = None
        self.gui_callback = gui_callback

    def _write_output(self, filename: str, content: str):
        if self.run_dir:
            filepath = os.path.join(self.run_dir, filename)
            with open(filepath, "w") as f:
                f.write(content)

    def _analyze_module_interface(self) -> str:
        if self.gui_callback:
            self.gui_callback("Module Interface Analysis", {
                "status": "Analyzing module interface requirements..."
            })

        prompt = f"""<specification>
{self.context.specification}
</specification>

Provide a module interface with:
- module name
- inputs
- outputs
- control signals
- bit widths

Example:
module TopModule (
    input  wire        clk,
    input  wire        reset,
    input  wire [31:0] in,
    output reg  [31:0] out
);

Output in <answer> tags. Give only the interface, no other text."""

        response = self.chat(
            user_input=prompt,
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            streaming=True,
            temperature=0.2
        )
        
        answer = self._extract_answer(response)
        if self.gui_callback:
            self.gui_callback("Module Interface Analysis", {
                "status": "Module interface analysis complete",
                "response": response,
                "result": answer
            })
        return answer

    def _analyze_components(self) -> str:
        if self.gui_callback:
            self.gui_callback("Component Analysis", {
                "status": "Analyzing required components..."
            })

        prompt = f"""<specification>
{self.context.specification}
</specification>

Think through this step-by-step:

1. What data must persist between clock cycles?
2. What is each storage element's purpose?
3. What values feed into what operations?
4. How do registers depend on each other?

Place reasoning in <thinking> tags and components in <answer> tags. Example:

STORAGE ELEMENTS:
- prev_in[31:0]: Holds input value from PREVIOUS clock cycle
- out[31:0]: Holds detected 1->0 transitions until reset

DETECTION RULES:
For each bit position:
1. We detect 1->0 when:
   * prev_in was 1 (previous cycle)
   * in is 0 (current cycle)
2. Once detected:
   * That bit stays 1 until reset

Do not implement the module and do not include any other text."""

        response = self.chat(
            user_input=prompt,
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            streaming=True,
            temperature=0.3
        )
        
        answer = self._extract_answer(response)
        if self.gui_callback:
            self.gui_callback("Component Analysis", {
                "status": "Component analysis complete",
                "response": response,
                "result": answer
            })
        return answer

    def _analyze_timing_requirements(self) -> str:
        if self.gui_callback:
            self.gui_callback("Timing Analysis", {
                "status": "Analyzing timing requirements..."
            })

        prompt = f"""<specification>
{self.context.specification}
</specification>

<module_interface>
{self.context.requirements.module_interface}
</module_interface>

<components>
{self.context.requirements.components}
</components>

Generate detailed timing analysis showing exactly this structure and format:

PARALLEL OPERATION EXAMPLE:
Clock     |‾|_|‾|_|‾|_|‾|_|
in[0]     |1|1|0|0|1|1|0|0|  <-- Bit 0 pattern
prev_in[0]|x|1|1|0|0|1|1|0|
out[0]    |0|0|1|1|1|1|1|1|

in[1]     |0|0|1|1|0|0|1|1|  <-- Bit 1 has different pattern!
prev_in[1]|x|0|0|1|1|0|0|1|  
out[1]    |0|0|0|0|1|1|1|1|

Each bit operates independently:
- Detects its own 1->0 transitions
- Maintains its own capture state
- All bits follow same rules but with different timing
- No interaction between bits

DETAILED TIMING SEQUENCE (one bit):
Clock     |‾|_|‾|_|‾|_|‾|_|
in        |1|1|0|0|1|1|0|0|  <-- Watch input changes!
prev_in   |x|1|1|0|0|1|1|0|  <-- One cycle delayed version of in
out       |0|0|1|1|1|1|1|1|  <-- Captures and holds transitions
         |A|B|C|D|E|F|G|H|

WHAT HAPPENS AT EACH CYCLE:
A: Reset done, start sampling
B: in=1 stored in prev_in
C: DETECTION! prev_in=1 and in=0 means 1->0 happened!
D: Keep out=1 (holds detection)
E: No detection (prev_in=0)
F: Sample new 1
G: Another detection! prev_in=1, in=0
H: Keep holding detection

CRITICAL TIMING RULES:
1. prev_in must hold OLD value while checking for transition
2. Update prev_in only AFTER using it
3. Detection formula: (prev_in & ~in) catches 1->0
4. Reset clears everything
5. Each bit position follows these rules independently

REGISTER UPDATE ORDER:
1. First: Check for transitions using current prev_in values
2. Then: Update out if transitions detected
3. Last: Update prev_in for next cycle
4. Same order applies to all 32 bits in parallel

Generate similar timing analysis for the given specification, maintaining exact same format and level of detail but specific to this design. Place in <answer> tags."""

        response = self.chat(
            user_input=prompt,
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            streaming=True,
            temperature=0.3
        )
        
        answer = self._extract_answer(response)
        
        if self.gui_callback:
            self.gui_callback("Timing Analysis", {
                "status": "Timing analysis complete",
                "response": response,
                "result": answer
            })
        return answer

    def _verify_timing_plan(self, timing: str) -> str:
        prompt = f"""<specification>
        {self.context.specification}
        </specification>

        <timing>
        {timing}
        </timing>

        Verify timing analysis by checking these common issues with examples:

        1. Transition Detection Check:
        BAD EXAMPLE (wrong detection):
        Clock     |‾|_|‾|_|‾|_|
        in        |1|1|0|0|1|1|
        prev_in   |x|1|1|0|0|1|
        out       |0|0|0|1|1|1|  <-- WRONG! Delayed detection

        GOOD EXAMPLE (correct detection):
        Clock     |‾|_|‾|_|‾|_|
        in        |1|1|0|0|1|1|
        prev_in   |x|1|1|0|0|1|
        out       |0|0|1|1|1|1|  <-- RIGHT! Immediate detection when prev_in=1 & in=0

        2. Register Update Order Check:
        BAD EXAMPLE (race condition):
        always @(posedge clk) begin
        prev_in <= in;           // WRONG! Updates too early
        out <= out | (prev_in & ~in);  // Uses new prev_in value

        GOOD EXAMPLE (correct order):
        always @(posedge clk) begin
        out <= out | (prev_in & ~in);  // Uses current prev_in first
        prev_in <= in;                 // Updates after use

        3. Reset Behavior Check:
        BAD EXAMPLE (incomplete reset):
        Clock     |‾|_|‾|_|‾|_|
        reset     |1|1|0|0|0|0|
        out       |0|0|1|1|1|1|  <-- WRONG! Sets during reset

        GOOD EXAMPLE (proper reset):
        Clock     |‾|_|‾|_|‾|_|
        reset     |1|1|0|0|0|0|
        out       |0|0|0|1|1|1|  <-- RIGHT! Stays 0 until reset done

        Check the provided timing against these examples and verify:
        1. Are transitions detected immediately when prev_in=1 and in=0?
        2. Is register update order clear and correct?
        3. Does reset behavior match specification?
        4. Are all bits shown operating independently?

        Keep existing sections but correct any timing or ordering issues found.

        Don't implement the module and don't include any other text.

        Place corrected timing in <answer> tags using exact same format."""

        response = self.chat(
            user_input=prompt,
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            streaming=True,
            temperature=0.2
        )
        
        answer = self._extract_answer(response)
        
        if self.gui_callback:
            self.gui_callback("Timing Analysis", {
                "status": "Timing analysis complete",
                "response": response,
                "result": answer
            })
        return answer

    def _analyze_fsm_needs(self) -> str:
        if self.gui_callback:
            self.gui_callback("Needs FSM?", {
                "status": "Analyzing FSM requirements..."
            })

        prompt = f"""<specification>
{self.context.specification}
</specification>

Think through this step-by-step and explain your reasoning:

1. What sequential behaviors are required?
2. Could these behaviors be implemented with simple registers?
3. Are there multiple operating modes or states needed?
4. Is there complex decision-making based on input conditions?
5. Are there timing or sequencing requirements?

Place your reasoning in <thinking> tags and the final FSM needs assessment in <answer> tags.
The <answer> should contain only:
FSM NEEDED: YES/NO
Requirements if YES:
- Requirement 1
- Requirement 2"""

        response = self.chat(
            user_input=prompt,
            provider="anthropic", 
            model="claude-3-5-sonnet-20241022",
            streaming=True,
            temperature=0.1
        )
        
        answer = self._extract_answer(response)

        return answer

    def _analyze_fsm_requirements(self) -> str:
        """Complete FSM analysis including requirements"""
        if self.gui_callback:
            self.gui_callback("FSM Analysis", {
                "status": "Analyzing FSM requirements..."
            })

        prompt = f"""<specification>
{self.context.specification}
</specification>

Analyze FSM requirements and provide them in EXACTLY this format:

STATES:
- STATE1: Description of state 1
- STATE2: Description of state 2
(list all states)

TRANSITIONS:
- STATE1 → STATE2: condition1
- STATE2 → STATE1: condition2
(list all transitions)

OUTPUTS:
STATE1:
- output1 = value1
- output2 = value2

STATE2:
- output1 = value3
- output2 = value4
(list outputs for each state)

RESET:
- Initial state: STATE1
- Reset type: Synchronous/Asynchronous
- Active: High/Low

Place response in <answer> tags. Follow this format exactly."""

        response = self.chat(
            user_input=prompt,
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            streaming=True,
            temperature=0.3
        )

        fsm_requirements = self._extract_answer(response)
        
        # Send to GUI for visualization
        if self.gui_callback:
            self.gui_callback("FSM Analysis", {
                "status": "FSM analysis complete",
                "result": fsm_requirements,
                "type": "fsm"  # Mark as FSM content for visualization
            })
        
        return fsm_requirements

    def _generate_fsm_structure(self, reqs: str) -> str:
        """Generate FSM structure based on requirements"""
        prompt = f"""
Please generate a complete Finite State Machine (FSM) implementation using SystemVerilog based on the following requirements:

<requirements>
{reqs}
</requirements>

Your FSM implementation must include ALL of the following components:

1. State Type Definition
   - Define states using an enumerated type
   - Use descriptive state names in UPPERCASE
   - Example: `typedef enum logic [1:0] {{IDLE, ACTIVE, ERROR}} state_t;`

2. State Register Declaration
   - Declare current_state and next_state as state_t type
   - Use SystemVerilog type definitions for improved readability
   - Example: `state_t current_state, next_state;`

3. Next State Logic
   - Define ALL possible state transitions
   - Use a SystemVerilog case statement
   - Cover every possible input combination
   - Include unique or priority to prevent inference of latches

4. Output Logic
   - Define outputs for EACH state
   - Specify whether Moore (state-based) or Mealy (state+input-based)
   - Use SystemVerilog always_comb blocks
   - Include all output signals and their values

5. Reset Handling
   - Define reset state
   - Specify synchronous or asynchronous reset
   - Include reset value for all outputs
   - Use always_ff for sequential logic

Please format your response using this structure:

```systemverilog
<FSM_IMPLEMENTATION>
// State Type Definition
typedef enum logic [STATE_WIDTH-1:0] {{
    IDLE,
    ACTIVE,
    ERROR
    // ... other states ...
}} state_t;

// State Registers
state_t current_state, next_state;

// Next State Logic
always_comb begin
    // Default assignment to prevent latches
    next_state = current_state;
    
    unique case (current_state)
        IDLE: begin
            if (condition) next_state = ACTIVE;
        end
        
        ACTIVE: begin
            if (condition) next_state = ERROR;
            else if (other_condition) next_state = IDLE;
        end
        
        // ... other states ...
        
        default: next_state = IDLE;
    endcase
end

// Output Logic
always_comb begin
    // Default outputs to prevent latches
    output_signal = 1'b0;
    
    unique case (current_state)
        IDLE: begin
            output_signal = 1'b1;
        end
        // ... other states ...
    endcase
end

// Sequential Logic
always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        current_state <= IDLE;
    end else begin
        current_state <= next_state;
    end
end
</FSM_IMPLEMENTATION>
```

Your implementation must follow these SystemVerilog best practices:
- Use enumerated types for state encoding
- Use always_comb for combinational logic
- Use always_ff for sequential logic
- Include default assignments to prevent latches
- Use unique case or priority case when appropriate
- Follow SystemVerilog naming conventions
- Include proper type definitions
- Include comments explaining complex transitions
- Ensure all states are reachable
- Avoid inferring latches
- Use consistent indentation
"""

        response = self.chat(
            user_input=prompt,
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            streaming=True,
            temperature=0.3
        )
        return self._extract_answer(response)

    def _verify_and_fix_fsm(self, fsm: str) -> str:
        """Verify and fix potential FSM issues"""
        prompt = f"""<fsm>
{fsm}
</fsm>

Verify FSM design for:
1. Completeness of state transitions
2. Reset behavior correctness
3. Output logic consistency
4. No unreachable states
5. No deadlock conditions

Fix any issues found. Place verified FSM in <answer> tags."""

        response = self.chat(
            user_input=prompt,
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            streaming=True,
            temperature=0.2
        )
        return self._extract_answer(response)

    def _analyze_fsm(self) -> str:
        reqs = self._analyze_fsm_requirements()
        fsm = self._generate_fsm_structure(reqs)
        
        if "<FiniteStateMachine>" in fsm:
            self.context.fsm_plan = FSMPlan()
            fsm = self._verify_and_fix_fsm(fsm)
            self.context.fsm_plan.state_info = fsm
            
        # self._write_output("fsm_final.txt", fsm)
        return fsm

    def _plan_output_logic(self) -> str:
        prompt = f"""<specification>
{self.context.specification}
</specification>

<fsm>
{self.context.fsm_plan.state_info}
</fsm>

Think through this step-by-step and explain your reasoning:

1. What outputs are needed in each state?
2. Are there any shared outputs between states?
3. How can the equations be optimized?
4. Are there any timing considerations?
5. How should output enables be handled?

Place your reasoning in <thinking> tags and the final output equations in <answer> tags.
The <answer> should contain only equations like:
output1 = (state == STATE1)
output2 = (state == STATE2 || state == STATE3)"""

        response = self.chat(
            user_input=prompt,
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            streaming=True,
            temperature=0.5
        )
        self.context.fsm_plan.output_logic = self._extract_answer(response)
        # self._write_output("output_logic.txt", response)
        return self._extract_answer(response)

    def analyze_timing(self) -> str:
        timing = self._analyze_timing_requirements()
        verified_timing = self._verify_timing_plan(timing)
        
        self.context.timing_plan = TimingPlan()
        
        sections = verified_timing.split("\n\n")
        if len(sections) >= 3:
            self.context.timing_plan.cycle_diagram = sections[0]
            self.context.timing_plan.register_deps = sections[1] 
            self.context.timing_plan.critical_paths = sections[2]
        
        # self._write_output("timing_final.txt", verified_timing)
        return verified_timing

    def _parse_hierarchy_response(self, response: str) -> ModuleHierarchy:
        """Parse the LLM response into a ModuleHierarchy object"""
        hierarchy_text = self._extract_answer(response)
        hierarchy = ModuleHierarchy(top_module="")
        
        current_module = None
        current_section = None
        
        for line in hierarchy_text.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('TOP_MODULE:'):
                hierarchy.top_module = line.split(':', 1)[1].strip()
                current_module = hierarchy.add_submodule(
                    hierarchy.top_module,
                    hierarchy.top_module
                )
                
            elif line.startswith('SUBMODULES:'):
                current_section = 'submodules'
                
            elif line.startswith('- ') and current_section == 'submodules':
                name = line[2:].split(':', 1)[0].strip()
                instance_name = f"{name}_inst"  # Default instance name
                current_module = hierarchy.add_submodule(
                    name, 
                    instance_name,
                    parent=hierarchy.top_module
                )
                
            elif line.startswith('  Purpose:') and current_module:
                current_module.description = line.split(':', 1)[1].strip()
                
            elif line.startswith('  Inputs:') and current_module:
                inputs = line.split(':', 1)[1].strip()[1:-1].split(',')  # Remove [] and split
                for input_name in inputs:
                    current_module.ports.append(SubmodulePort(
                        name=input_name.strip(),
                        direction='input'
                    ))
                    
            elif line.startswith('  Outputs:') and current_module:
                outputs = line.split(':', 1)[1].strip()[1:-1].split(',')
                for output_name in outputs:
                    current_module.ports.append(SubmodulePort(
                        name=output_name.strip(),
                        direction='output'
                    ))
                    
            elif line.startswith('CONNECTIONS:'):
                current_section = 'connections'
                
            elif line.startswith('- From:') and current_section == 'connections':
                from_parts = line.split(':', 1)[1].strip().split('.')
                next_line = next(l for l in hierarchy_text.split('\n') if 'To:' in l)
                to_parts = next_line.split(':', 1)[1].strip().split('.')
                
                # Add connection to appropriate module
                if len(from_parts) == 2 and len(to_parts) == 2:
                    from_module, from_port = from_parts
                    to_module, to_port = to_parts
                    
                    connection = SubmoduleConnection(
                        from_module=from_module,
                        from_port=from_port,
                        to_module=to_module,
                        to_port=to_port
                    )
                    
                    # Add to parent module's connections
                    parent_module = hierarchy.submodules[hierarchy.top_module]
                    parent_module.connections.append(connection)
        
        return hierarchy

    def _analyze_module_hierarchy(self) -> ModuleHierarchy:
        """Analyze if and how the design should be split into submodules"""
        if self.gui_callback:
            self.gui_callback("Module Hierarchy Analysis", {
                "status": "Analyzing module hierarchy needs..."
            })

        # First get the top module name from interface analysis
        interface_response = self._analyze_module_interface()
        module_match = re.search(r'module\s+(\w+)', interface_response)
        top_module_name = module_match.group(1) if module_match else "TopModule"

        # Update prompt to enforce strict format
        prompt = f"""<specification>
{self.context.specification}
</specification>

<top_module>
{top_module_name}
</top_module>

Analyze if this design should be split into submodules. Follow this EXACT format:

MODULE_HIERARCHY:
TOP_MODULE: {top_module_name}
DESCRIPTION: <brief description>
PORTS:
- input clk: clock signal
- input rst_n: active-low reset
[list all top-level ports]

SUBMODULES:
[If needed, list each submodule as:]
- NAME: <submodule_name>
  INSTANCE: <instance_name>
  DESCRIPTION: <purpose>
  PORTS:
  - input clk: clock signal
  - input rst_n: active-low reset
  [list all submodule ports]
  
  CONNECTIONS:
  - FROM: <source_module>.<port> TO: <dest_module>.<port>
  [list all connections for this submodule]

[If no submodules needed, state "No submodules required for this design"]

EXAMPLE FORMAT:
MODULE_HIERARCHY:
TOP_MODULE: traffic_light_controller
DESCRIPTION: Main traffic light control module
PORTS:
- input clk: system clock
- input rst_n: active-low reset
- output [1:0] north_south: north-south light state
- output [1:0] east_west: east-west light state

SUBMODULES:
- NAME: traffic_timer
  INSTANCE: timer_inst
  DESCRIPTION: Generates timing for light changes
  PORTS:
  - input clk: system clock
  - input rst_n: active-low reset
  - output timer_done: indicates timing complete
  
  CONNECTIONS:
  - FROM: traffic_timer.timer_done TO: traffic_fsm.timer_expired

- NAME: traffic_fsm
  INSTANCE: fsm_inst
  DESCRIPTION: Controls light state transitions
  PORTS:
  - input clk: system clock
  - input rst_n: active-low reset
  - input timer_expired: timing input
  - output [1:0] ns_state: north-south state
  - output [1:0] ew_state: east-west state
  
  CONNECTIONS:
  - FROM: traffic_fsm.ns_state TO: traffic_light_controller.north_south
  - FROM: traffic_fsm.ew_state TO: traffic_light_controller.east_west

Place response in <answer> tags. Follow this format exactly."""

        response = self.chat(
            user_input=prompt,
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            streaming=True,
            temperature=0.2
        )
        
        hierarchy = self._parse_hierarchy_response(response)
        
        # Create template files for each module immediately after analysis
        os.makedirs("vpx_outputs", exist_ok=True)
        
        # Create top module template
        top_filename = f"{hierarchy.top_module}.sv"
        top_filepath = os.path.join("vpx_outputs", top_filename)
        with open(top_filepath, "w") as f:
            f.write(interface_response)
        
        if self.gui_callback:
            self.gui_callback("Module Interface Analysis", {
                "status": f"Created template for top module: {hierarchy.top_module}",
                "file_generated": top_filepath,
                "module_name": hierarchy.top_module
            })
        
        # Create template files for submodules
        for name, submodule in hierarchy.submodules.items():
            if name != hierarchy.top_module:  # Skip top module as it's already created
                filename = f"{name}.sv"
                filepath = os.path.join("vpx_outputs", filename)
                
                # Generate interface for submodule
                submodule_interface = self._generate_submodule_interface(submodule)
                
                with open(filepath, "w") as f:
                    f.write(submodule_interface)
                
                if self.gui_callback:
                    self.gui_callback("Module Interface Analysis", {
                        "status": f"Created template for submodule: {name}",
                        "file_generated": filepath,
                        "module_name": name,
                        "result": submodule_interface
                    })
        
        return hierarchy

    def _generate_submodule_interface(self, submodule: SubmoduleInfo) -> str:
        """Generate SystemVerilog interface for a submodule"""
        ports = []
        for port in submodule.ports:
            width_str = f"[{port.width-1}:0] " if port.width > 1 else ""
            ports.append(f"    {port.direction} logic {width_str}{port.name}")
        
        interface = f"""module {submodule.name} (
{',\\n'.join(ports)}
);

// TODO: Implementation

endmodule"""
        
        return interface

    def _parse_hierarchy_response(self, response: str) -> ModuleHierarchy:
        """Parse the LLM response into a ModuleHierarchy object"""
        hierarchy_text = self._extract_answer(response)
        
        # Check if no submodules needed
        if "No submodules required for this design" in hierarchy_text:
            # Create simple hierarchy with just top module
            module_match = re.search(r'TOP_MODULE:\s*(\w+)', hierarchy_text)
            top_name = module_match.group(1) if module_match else "TopModule"
            return ModuleHierarchy(top_module=top_name)
        
        # Parse full hierarchy
        hierarchy = ModuleHierarchy(top_module="")
        
        current_module = None
        current_section = None
        
        for line in hierarchy_text.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('TOP_MODULE:'):
                hierarchy.top_module = line.split(':', 1)[1].strip()
                current_module = hierarchy.add_submodule(
                    hierarchy.top_module,
                    hierarchy.top_module
                )
                
            elif line.startswith('- NAME:'):
                name = line.split(':', 1)[1].strip()
                current_module = None
                
                # Look for instance name
                for next_line in hierarchy_text.split('\n'):
                    if 'INSTANCE:' in next_line:
                        instance_name = next_line.split(':', 1)[1].strip()
                        current_module = hierarchy.add_submodule(
                            name,
                            instance_name,
                            parent=hierarchy.top_module
                        )
                        break
                
                if not current_module:  # Fallback if no instance name found
                    current_module = hierarchy.add_submodule(
                        name,
                        f"{name}_inst",
                        parent=hierarchy.top_module
                    )
                
            elif line.startswith('  DESCRIPTION:') and current_module:
                current_module.description = line.split(':', 1)[1].strip()
                
            elif line.startswith('  PORTS:'):
                current_section = 'ports'
                
            elif line.startswith('  CONNECTIONS:'):
                current_section = 'connections'
                
            elif line.startswith('  - ') and current_section == 'ports' and current_module:
                port_line = line[4:].strip()
                direction = 'input' if 'input' in port_line else 'output'
                
                # Parse port width if present
                width_match = re.search(r'\[(\d+):0\]', port_line)
                width = int(width_match.group(1)) + 1 if width_match else 1
                # Get port name
                name_match = re.search(r'(?:\[[\d:]+\])?\s*(\w+)(?=\s*:|\s*$)', port_line)
                if name_match:
                    port_name = name_match.group(1)
                    description = port_line.split(':', 1)[1].strip() if ':' in port_line else ""
                    
                    current_module.ports.append(SubmodulePort(
                        name=port_name,
                        direction=direction,
                        width=width,
                        description=description
                    ))
                    
            elif line.startswith('  - FROM:') and current_section == 'connections' and current_module:
                # Parse connection
                from_line = line[4:].strip()
                to_line = next(l for l in hierarchy_text.split('\n') if 'TO:' in l)
                
                from_parts = from_line.split(':', 1)[1].strip().split('.')
                to_parts = to_line.split(':', 1)[1].strip().split('.')
                
                if len(from_parts) == 2 and len(to_parts) == 2:
                    current_module.connections.append(SubmoduleConnection(
                        from_module=from_parts[0].strip(),
                        from_port=from_parts[1].strip(),
                        to_module=to_parts[0].strip(),
                        to_port=to_parts[1].strip()
                    ))
        
        return hierarchy

    def _generate_submodule_spec(self, submodule: SubmoduleInfo) -> str:
        """Generate detailed specification for a submodule"""
        # Ensure proper module name is used in the file
        module_name = submodule.name
        if not module_name.islower() or ' ' in module_name:
            module_name = module_name.lower().replace(' ', '_')
            submodule.name = module_name

        prompt = f"""<specification>
{self.context.specification}
</specification>

<submodule>
Name: {module_name}
Description: {submodule.description}
Ports:
{chr(10).join(f'- {p.name}: {p.direction} [{p.width}] - {p.description}' for p in submodule.ports)}
</submodule>

Generate a focused specification for this submodule that includes:
1. Exact functionality required
2. Input/output behavior
3. Timing requirements
4. Any special considerations

The module must be named exactly '{module_name}'.
Keep the specification clear and focused on just this submodule's responsibilities.
Place specification in <answer> tags."""

        response = self.chat(
            user_input=prompt,
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            streaming=True,
            temperature=0.3
        )
        
        return self._extract_answer(response)

    def analyze_requirements(self) -> DesignContext:
        """Analyze requirements for both hierarchical and non-hierarchical designs"""
        if self.gui_callback:
            self.gui_callback("Requirements Analysis", {
                "status": "Starting requirements analysis..."
            })
        
        self.context.requirements = Requirements()
        
        # 1. Analyze module hierarchy first
        hierarchy = self._analyze_module_hierarchy()
        self.context.requirements.hierarchy = hierarchy
        
        # 2. Generate interfaces for all modules (including submodules) first
        if hierarchy and hierarchy.submodules:
            for name, submodule in hierarchy.submodules.items():
                if self.gui_callback:
                    self.gui_callback("Module Interface Analysis", {
                        "status": f"Analyzing interface for module: {name}",
                        "module_name": name
                    })
                
                interface_prompt = f"""Generate a clean SystemVerilog interface for this module:
Name: {name}
Description: {submodule.description}
Parent Module: {submodule.parent if submodule.parent else 'None (Top Module)'}

Consider:
1. All inputs needed for functionality
2. All outputs produced
3. Control signals (clock, reset, enables)
4. Proper bit widths for all ports

Follow standard SystemVerilog port declaration format.
Include only the module interface, no implementation.
Place interface in <answer> tags."""

                interface_response = self.chat(
                    user_input=interface_prompt,
                    provider="anthropic",
                    model="claude-3-5-sonnet-20241022",
                    streaming=True,
                    temperature=0.2
                )
                
                interface = self._extract_answer(interface_response)
                
                # Store interface in submodule info
                submodule.rtl = interface
                
                # Create empty file for this module
                filename = f"{name}.sv"
                filepath = os.path.join("vpx_outputs", filename)
                with open(filepath, "w") as f:
                    f.write(interface)
                
                if self.gui_callback:
                    self.gui_callback("Module Interface Analysis", {
                        "status": f"Generated interface for {name}",
                        "result": interface,
                        "file_generated": filepath
                    })
        
        # 3. Analyze top module components and timing
        components_response = self._analyze_components()
        self.context.requirements.components = components_response
        
        timing_response = self.analyze_timing()
        self.context.requirements.timing = timing_response
        
        # 4. FSM Analysis for each module that needs it
        fsm_needs_response = self._analyze_fsm_needs()
        if "FSM NEEDED: YES" in fsm_needs_response:
            self.needs_fsm = True
            fsm_response = self._analyze_fsm()
            self.context.requirements.fsm = fsm_response
        
        # 5. Analyze each submodule's specific requirements
        if hierarchy and hierarchy.submodules:
            for name, submodule in hierarchy.submodules.items():
                if self.gui_callback:
                    self.gui_callback("Submodule Analysis", {
                        "status": f"Analyzing requirements for: {name}",
                        "module_name": name
                    })
                
                # Generate detailed specification
                spec = self._generate_submodule_spec(submodule)
                submodule.specification = spec
                
                # Check if submodule needs FSM
                sub_fsm_needs = self._analyze_fsm_needs()
                if "FSM NEEDED: YES" in sub_fsm_needs:
                    sub_fsm = self._analyze_fsm()
                    submodule.fsm_spec = sub_fsm
        
        return self.context

    def _extract_answer(self, response: str) -> str:
        start = response.find("<answer>")
        end = response.find("</answer>")
        if start != -1 and end != -1:
            return response[start + 8:end].strip()
        return response

    def _get_hierarchy_prompt(self) -> str:
        """Generate prompt for analyzing module hierarchy"""
        return f"""<specification>
{self.context.specification}
</specification>

Analyze if this design needs to be split into submodules. Consider:
1. Functional blocks that can be isolated
2. Repeated functionality that could be reused
3. Complex operations that should be encapsulated

If submodules would help, describe them using this format:

TOP_MODULE: <name>
DESCRIPTION: <brief description>
PORTS:
- name: <port_name>
  direction: <input|output>
  width: <bit_width>
  description: <purpose>

SUBMODULES:
- name: <submodule_name>
  description: <purpose>
  ports:
    - <same format as above>
  instances:
    - name: <instance_name>
      connections:
        <port>: <signal>

CONNECTIONS:
- From: <module_name>.<port_name>
  To: <module_name>.<port_name>
  Purpose: <brief description>

Only suggest submodules if they significantly improve the design.
For simple designs like a half adder, no submodules are needed.
Place response in <answer> tags."""

class DesignCoder(Agent):
    def __init__(self, context: DesignContext, verbose: bool = False, gui_callback = None):
        super().__init__(
            system_prompt="You are a digital design engineer specializing in RTL code generation.",
            tools={},
            context="",
            verbose=verbose
        )
        self.context = context
        self.gui_callback = gui_callback

    def call_zero_shot(self) -> str:
        prompt = f"""<specification>
{self.context.specification}
</specification>

<module_interface>
{self.context.requirements.module_interface}
</module_interface>

<components>
{self.context.requirements.components}
</components>

<timing>
{self.context.timing_plan.cycle_diagram if self.context.timing_plan else ""}

{self.context.timing_plan.register_deps if self.context.timing_plan else ""}

{self.context.timing_plan.critical_paths if self.context.timing_plan else ""}
</timing>

Think through implementation step-by-step:

1. Reset Behavior:
  - out must clear to zero
  - prev_in will get new input next cycle

2. Detection Logic:
  - prev_in & ~in catches 1->0 transition
  - OR with existing out to maintain detected bits

3. Register Updates:
  MUST BE IN THIS ORDER:
  ```systemverilog
  if (reset)
    out <= 0;
  else
    out <= out | (prev_in & ~in);  // Use prev_in FIRST
  prev_in <= in;                   // Update prev_in LAST

Provide synthesizable SystemVerilog in <answer> tags."""

        response = self.chat(
            user_input=prompt,
            provider="anthropic", 
            model="claude-3-5-sonnet-20241022",
            streaming=True,
            temperature=0.3
        )
        return self._extract_answer(response)

    def generate_rtl(self) -> str:
        """Generate RTL for hierarchical designs"""
        if (hasattr(self.context.requirements, 'hierarchy') and 
            self.context.requirements.hierarchy and 
            self.context.requirements.hierarchy.submodules):
            
            # Create vpx_outputs directory if it doesn't exist
            os.makedirs("vpx_outputs", exist_ok=True)
            
            # Get hierarchy information
            hierarchy = self.context.requirements.hierarchy
            
            # Build dependency graph
            dependencies = {}
            for name, submodule in hierarchy.submodules.items():
                dependencies[name] = set()
                for conn in submodule.connections:
                    if conn.from_module != name:
                        dependencies[name].add(conn.from_module)
            
            # Determine implementation order (bottom-up)
            implemented = set()
            implementation_order = []
            
            def can_implement(module_name):
                return all(dep in implemented for dep in dependencies[module_name])
            
            while len(implemented) < len(hierarchy.submodules):
                # Find modules that can be implemented
                ready_modules = [
                    name for name in hierarchy.submodules.keys()
                    if name not in implemented and can_implement(name)
                ]
                
                if not ready_modules:
                    raise Exception("Circular dependency detected in module hierarchy")
                
                implementation_order.extend(ready_modules)
                implemented.update(ready_modules)
            
            # Generate RTL in dependency order
            submodule_rtl = {}
            for module_name in implementation_order:
                if module_name == hierarchy.top_module:
                    continue  # Skip top module for now
                    
                submodule = hierarchy.submodules[module_name]
                
                if self.gui_callback:
                    self.gui_callback("RTL Generation", {
                        "status": f"Generating RTL for module: {module_name}"
                    })
                
                # Ensure proper module name
                module_name = module_name.lower().replace(' ', '_')
                
                # Create XML context including implemented dependencies
                submodule_context = f"""<submodule_info>
<name>{module_name}</name>
<description>{submodule.description}</description>
<specification>{submodule.specification}</specification>
<interface>
{submodule.rtl}
</interface>
<parent>{submodule.parent if submodule.parent else 'None'}</parent>
<connections>
{chr(10).join(str(conn) for conn in submodule.connections)}
</connections>
</submodule_info>

<implemented_modules>
{chr(10).join(f'''<module>
<name>{name}</name>
<rtl>{rtl}</rtl>
</module>''' for name, rtl in submodule_rtl.items())}
</implemented_modules>"""
                
                # Generate implementation
                module_prompt = f"""Generate SystemVerilog implementation for this module based on the following context:

{submodule_context}

Requirements:
1. Use EXACTLY the module name: {module_name}
2. Implement ONLY this module's functionality
3. Use ONLY the ports defined in the interface
4. Do not include any submodule instantiations
5. Focus on this module's specific responsibilities
6. Follow the module's specification exactly

Place complete RTL in <answer> tags."""

                response = self.chat(
                    user_input=module_prompt,
                    provider="anthropic",
                    model="claude-3-5-sonnet-20241022",
                    streaming=True,
                    temperature=0.3
                )
                
                rtl = self._extract_answer(response)
                submodule_rtl[module_name] = rtl
                
                # Save to file
                filename = f"{module_name}.sv"
                filepath = os.path.join("vpx_outputs", filename)
                with open(filepath, "w") as f:
                    f.write(rtl)
                
                if self.gui_callback:
                    self.gui_callback("RTL Generation", {
                        "status": f"Generated {filename}",
                        "file_generated": filepath,
                        "module_name": module_name
                    })
            
            # Finally, generate top module with all submodules implemented
            if self.gui_callback:
                self.gui_callback("RTL Generation", {
                    "status": "Generating top module..."
                })
            
            # Create XML context for top module with all implemented submodules
            top_context = f"""<design_hierarchy>
            <top_module>
            <name>{hierarchy.top_module}</name>
            <interface>
            {self.context.requirements.module_interface}
            </interface>
            </top_module>

            <implemented_submodules>
            {chr(10).join(f'''<submodule>
            <name>{name}</name>
            <instance>{info.instance_name}</instance>
            <rtl>{submodule_rtl[name]}</rtl>
            <connections>
            {chr(10).join(str(conn) for conn in info.connections)}
            </connections>
            </submodule>''' for name, info in hierarchy.submodules.items() if name != hierarchy.top_module)}
            </implemented_submodules>
            </design_hierarchy>"""
            
            top_prompt = f"""Generate SystemVerilog implementation for the top module using this hierarchy:

{top_context}

Requirements:
1. Use EXACTLY the module name from top_module
2. Instantiate all submodules with their exact instance names
3. Connect all ports according to the connection specifications
4. Use proper SystemVerilog instantiation syntax:
   module_name instance_name (
       .port1(signal1),
       .port2(signal2)
   );
5. Declare any needed internal signals for connections

Place complete RTL in <answer> tags."""

            response = self.chat(
                user_input=top_prompt,
                provider="anthropic",
                model="claude-3-5-sonnet-20241022",
                streaming=True,
                temperature=0.3
            )
            
            top_rtl = self._extract_answer(response)
            
            # Save top module
            top_filename = f"{hierarchy.top_module}.sv"
            top_filepath = os.path.join("vpx_outputs", top_filename)
            with open(top_filepath, "w") as f:
                f.write(top_rtl)
            
            if self.gui_callback:
                self.gui_callback("RTL Generation", {
                    "status": "RTL generation complete",
                    "file_generated": top_filepath,
                    "rtl": top_rtl,
                    "module_name": hierarchy.top_module
                })
            
            return top_rtl
            
        # Non-hierarchical design - use original method
        rtl = self.call_zero_shot()
        
        # Save to file
        if rtl:
            module_match = re.search(r'module\s+(\w+)', rtl)
            module_name = module_match.group(1) if module_match else "TopModule"
            filename = f"{module_name}.sv"
            
            os.makedirs("vpx_outputs", exist_ok=True)
            filepath = os.path.join("vpx_outputs", filename)
            
            with open(filepath, "w") as f:
                f.write(rtl)
                
            if self.gui_callback:
                self.gui_callback("RTL Generation", {
                    "status": "RTL generation complete",
                    "file_generated": filepath,
                    "rtl": rtl,
                    "module_name": module_name
                })
        
        return rtl

    def _extract_answer(self, response: str) -> str:
        start = response.find("<answer>")
        end = response.find("</answer>")
        if start != -1 and end != -1:
            return response[start + 8:end].strip()
        return response

class TestType(Enum):
    DIRECTED = auto()
    RANDOM = auto()
    BOUNDARY = auto()
    ERROR = auto()

@dataclass
class TestCase:
    name: str
    type: TestType
    inputs: Dict[str, Any]
    expected: Dict[str, Any]
    description: str = ""
    
@dataclass 
class Assertion:
    name: str
    condition: str
    severity: str = "error"
    message: str = ""

class DesignVerifier(Agent):
    def __init__(self, context: Optional[Dict] = None, rtl: Optional[str] = None, verbose: bool = False):
        super().__init__(context)
        self.rtl = rtl
        self.verbose = verbose
        self.test_cases = {}  # Dict to store test cases by name

    def store_test_case(self, test: TestCase):
        """Store a test case for later retrieval"""
        self.test_cases[test.name] = test

    def get_test_case(self, test_name: str) -> Optional[TestCase]:
        """Retrieve a stored test case"""
        return self.test_cases.get(test_name)

    def _generate_random_tests(self, modules: List[Dict], num_tests: int) -> List[TestCase]:
        """Generate test cases based on LLM analysis of likely failure points"""
        tests = []
        
        for module in modules:
            # Get all input ports
            input_ports = {
                p['name']: p for p in module['ports'] 
                if p['direction'] == 'input'
            }
            
            # Create prompt for LLM
            prompt = f"""Analyze this RTL module and generate {num_tests} test cases targeting likely failure points.
Consider:
1. Corner cases
2. Edge conditions
3. Protocol violations
4. Race conditions
5. Timing issues

RTL Module:
{self.rtl}

Available input ports:
{json.dumps(input_ports, indent=2)}

Return test cases in this format:
<test_cases>
[
  {{
    "name": "test_name",
    "description": "what this test targets",
    "failure_point": "description of potential failure",
    "inputs": {{
      "port_name": value  // Include ALL input ports with specific values
    }},
    "expected": {{
      "port_name": value  // Expected output values
    }}
  }}
]
</test_cases>"""

            # Get LLM response
            response = self.chat(
                user_input=prompt,
                provider="anthropic",
                model="claude-3-5-sonnet-20241022",
                temperature=0.2
            )
            
            # Parse response
            try:
                start = response.find("<test_cases>")
                end = response.find("</test_cases>")
                if start != -1 and end != -1:
                    json_str = response[start + 12:end].strip()
                    test_vectors = json.loads(json_str)
                    
                    # Convert to TestCase objects
                    for vector in test_vectors:
                        # Ensure all input ports have values
                        inputs = {}
                        for port_name, port_info in input_ports.items():
                            if port_name in vector['inputs']:
                                inputs[port_name] = vector['inputs'][port_name]
                            else:
                                # Default values for missing ports
                                if port_name.lower() in ['clk', 'clock']:
                                    inputs[port_name] = 0
                                elif any(r in port_name.lower() for r in ['rst', 'reset']):
                                    inputs[port_name] = 1 if '_n' in port_name.lower() else 0
                                else:
                                    inputs[port_name] = 0
                        
                        test = TestCase(
                            name=vector['name'],
                            type=TestType.DIRECTED,
                            inputs=inputs,
                            expected=vector.get('expected', {}),
                            description=f"{vector['description']}\nFailure Point: {vector['failure_point']}"
                        )
                        tests.append(test)
                        self.store_test_case(test)
                        
                        if self.verbose:
                            print(f"\nGenerated test case:")
                            print(f"Name: {test.name}")
                            print(f"Description: {test.description}")
                            print(f"Inputs: {test.inputs}")
                            print(f"Expected: {test.expected}")
                            
            except Exception as e:
                if self.verbose:
                    print(f"Error parsing LLM response: {str(e)}")
                    print(f"Response: {response}")
        
        return tests

    def analyze_logic_cone(self, output_signal: str) -> Dict[str, Any]:
        """Analyze the logic cone for a given output signal/port in the RTL."""
        if not self.rtl:
            return self._empty_analysis_result()

        if self.verbose:
            print("\n=== Starting Logic Cone Analysis ===")
            print(f"Target Output: {output_signal}")

        # Parse and analyze the RTL code
        signals = self._identify_signals()
        if self.verbose:
            print("\n--- Identified Signals ---")
            for category, sigs in signals.items():
                print(f"{category.title()}: {sorted(sigs)}")

        ast_nodes = self._parse_rtl_to_nodes()
        dependency_graph = self._build_dependency_graph(ast_nodes, signals)
        cone_info = self._trace_logic_cone(output_signal, dependency_graph, signals)

        if self.verbose:
            print("\n=== Logic Cone Analysis Complete ===\n")

        return cone_info

    def _identify_signals(self) -> Dict[str, Set[str]]:
        """Identify inputs, outputs, and internal signals in the RTL"""
        signals = {
            'inputs': set(),
            'outputs': set(),
            'internal': set(),
            'constants': set(),
            'parameters': set()
        }

        # First remove comments to avoid false matches
        rtl_no_comments = re.sub(r'//.*$', '', self.rtl, flags=re.MULTILINE)
        rtl_no_comments = re.sub(r'/\*.*?\*/', '', rtl_no_comments, flags=re.DOTALL)

        # More comprehensive patterns for port declarations
        # Handles parameterized widths, logic type, and multiple ports per line
        input_pattern = r'\b(?:input)\s+(?:wire|reg|logic)?\s*(?:signed|unsigned)?\s*(?:\[(?:[^\]]+)\])?\s*(\w+(?:\s*,\s*\w+)*)\s*(?:,|;|$)'
        output_pattern = r'\b(?:output)\s+(?:wire|reg|logic)?\s*(?:signed|unsigned)?\s*(?:\[(?:[^\]]+)\])?\s*(\w+(?:\s*,\s*\w+)*)\s*(?:,|;|$)'
        wire_pattern = r'\bwire\s+(?:signed|unsigned)?\s*(?:\[(?:[^\]]+)\])?\s*(\w+(?:\s*,\s*\w+)*)\s*(?:,|;|$)'
        reg_pattern = r'\breg\s+(?:signed|unsigned)?\s*(?:\[(?:[^\]]+)\])?\s*(\w+(?:\s*,\s*\w+)*)\s*(?:,|;|$)'
        logic_pattern = r'\blogic\s+(?:signed|unsigned)?\s*(?:\[(?:[^\]]+)\])?\s*(\w+(?:\s*,\s*\w+)*)\s*(?:,|;|$)'
        constant_pattern = r'\bparameter\s+(?:\[(?:[^\]]+)\])?\s*(\w+)\s*='
        parameter_pattern = r'\bparameter\s+(?:\[(?:[^\]]+)\])?\s*(\w+)'

        # Helper function to find all matches and clean them
        def find_signals(pattern: str) -> Set[str]:
            matches = re.finditer(pattern, rtl_no_comments, re.MULTILINE)
            # Handle multiple ports per line and clean up signal names
            signals = set()
            for match in matches:
                port_list = match.group(1).strip()
                signals.update(name.strip() for name in port_list.split(','))
            return signals

        # Find all signals
        signals['inputs'].update(find_signals(input_pattern))
        signals['outputs'].update(find_signals(output_pattern))
        signals['internal'].update(find_signals(wire_pattern))
        signals['internal'].update(find_signals(reg_pattern))
        signals['internal'].update(find_signals(logic_pattern))
        signals['constants'].update(find_signals(constant_pattern))
        signals['parameters'].update(find_signals(parameter_pattern))

        # Find all signal references in assignments and always blocks
        assign_pattern = r'assign\s+(\w+)(?:\[.*?\])?\s*='
        signal_refs = re.finditer(assign_pattern, rtl_no_comments)
        for match in signal_refs:
            base_signal = match.group(1)
            if base_signal not in signals['inputs']:
                signals['internal'].add(base_signal)

        # Find signals used in expressions
        expr_pattern = r'\b(\w+)(?:\[.*?\])?\b'
        for match in re.finditer(expr_pattern, rtl_no_comments):
            signal = match.group(1)
            # Skip keywords and numbers
            if not signal.isdigit() and signal not in {
                'module', 'input', 'output', 'wire', 'reg', 'logic',
                'assign', 'begin', 'end', 'if', 'else', 'case', 'endcase',
                'always_ff', 'always_comb', 'parameter', 'signed', 'unsigned'
            }:
                if signal not in signals['inputs'] and signal not in signals['outputs']:
                    signals['internal'].add(signal)

        if self.verbose:
            print("\nIdentified signals after cleaning:")
            for category, sigs in signals.items():
                print(f"{category}: {sorted(sigs)}")

        return signals

    def _parse_rtl_to_nodes(self) -> List[Dict[str, Any]]:
        """Parse SystemVerilog RTL into AST-like nodes"""
        if self.verbose:
            print("\n=== Starting RTL to AST Node Parsing ===")
        
        nodes = []
        
        # Remove comments and clean up whitespace
        rtl_clean = re.sub(r'//.*$', '', self.rtl, flags=re.MULTILINE)
        rtl_clean = re.sub(r'/\*.*?\*/', '', rtl_clean, flags=re.DOTALL)
        
        if self.verbose:
            print("\nCleaned RTL:")
            print(rtl_clean)
        
        # Split into module blocks
        module_matches = re.finditer(
            r'\bmodule\s+(\w+)\s*(?:#\s*\(.*?\))?\s*\((.*?)\);(.*?)endmodule',
            rtl_clean,
            re.DOTALL
        )
        
        for module_match in module_matches:
            if self.verbose:
                print(f"\nProcessing module: {module_match.group(1)}")
                
            module_body = module_match.group(3)
            
            # Parse continuous assignments
            assign_pattern = r'assign\s+([^=]+?)\s*=\s*([^;]+);'
            assignments = re.finditer(assign_pattern, module_body)
            for assign in assignments:
                if self.verbose:
                    print(f"\nFound continuous assignment:")
                    print(f"  Target: {assign.group(1).strip()}")
                    print(f"  Value: {assign.group(2).strip()}")
                
                nodes.append({
                    'type': 'continuous_assignment',
                    'target': assign.group(1).strip(),
                    'value': assign.group(2).strip(),
                    'module': module_match.group(1)
                })

            # Parse always_ff blocks with fixed pattern
            if self.verbose:
                print("\nParsing always_ff blocks...")
                
            # New pattern that properly handles nested blocks
            always_ff_pattern = r'always_ff\s*@\s*\((.*?)\)\s*begin\s*((?:(?!end\s*(?:else|case|if|begin)\b)(?!end\b).|[\r\n])*?end\b)'
            always_ff_blocks = re.finditer(always_ff_pattern, module_body, re.DOTALL)
            
            for always_ff in always_ff_blocks:
                sensitivity = always_ff.group(1).strip()
                block_content = always_ff.group(2).strip()
                
                if self.verbose:
                    print(f"\nFound always_ff block:")
                    print(f"  Sensitivity: {sensitivity}")
                    print(f"  Raw Content: {block_content}")
                
                # Parse the block content into statements
                statements = self._parse_always_block(block_content)
                
                if self.verbose:
                    print(f"  Parsed Statements:")
                    for stmt in statements:
                        print(f"    {stmt}")
                
                nodes.append({
                    'type': 'always_ff',
                    'sensitivity': sensitivity,
                    'statements': statements,
                    'module': module_match.group(1)
                })

            # Parse always_comb blocks with similar pattern
            if self.verbose:
                print("\nParsing always_comb blocks...")
                
            always_comb_pattern = r'always_comb\s*begin\s*((?:(?!end\s*(?:else|case|if|begin)\b)(?!end\b).|[\r\n])*?end\b)'
            always_comb_blocks = re.finditer(always_comb_pattern, module_body, re.DOTALL)
            
            for always_comb in always_comb_blocks:
                block_content = always_comb.group(1).strip()
                
                if self.verbose:
                    print(f"\nFound always_comb block:")
                    print(f"  Raw Content: {block_content}")
                
                statements = self._parse_always_block(block_content)
                
                if self.verbose:
                    print(f"  Parsed Statements:")
                    for stmt in statements:
                        print(f"    {stmt}")
                
                nodes.append({
                    'type': 'always_comb',
                    'statements': statements,
                    'module': module_match.group(1)
                })

        if self.verbose:
            print("\n=== Completed RTL to AST Node Parsing ===")
            print(f"Total nodes generated: {len(nodes)}")
            for i, node in enumerate(nodes):
                print(f"\nNode {i+1}:")
                self._print_node(node)
        
        return nodes

    def _print_node(self, node: Dict[str, Any], indent: int = 2):
        """Helper method to print node information"""
        indent_str = " " * indent
        print(f"{indent_str}Type: {node['type']}")
        print(f"{indent_str}Module: {node['module']}")
        
        if 'target' in node:
            print(f"{indent_str}Target: {node['target']}")
        if 'value' in node:
            print(f"{indent_str}Value: {node['value']}")
        if 'sensitivity' in node:
            print(f"{indent_str}Sensitivity: {node['sensitivity']}")
        if 'statements' in node:
            print(f"{indent_str}Statements ({len(node['statements'])}):")
            for stmt in node['statements']:
                print(f"{indent_str}  Statement:")
                for k, v in stmt.items():
                    print(f"{indent_str}    {k}: {v}")

    def _parse_always_block(self, block_content: str) -> List[Dict[str, Any]]:
        """Parse the contents of an always block with SystemVerilog constructs"""
        statements = []
        
        # Remove extra whitespace and split into lines
        lines = [line.strip() for line in block_content.split(';') if line.strip()]
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Handle if-else blocks
            if line.startswith('if'):
                if_result = self._parse_if_block(lines[i:])
                statements.append(if_result['node'])
                i += if_result['lines_consumed']
                
            # Handle case blocks (including unique and priority cases)
            elif any(line.startswith(keyword) for keyword in ['case', 'unique case', 'priority case']):
                case_result = self._parse_case_block(lines[i:])
                statements.append(case_result['node'])
                i += case_result['lines_consumed']
                
            # Handle assignments
            elif '=' in line:
                target, value = line.split('=', 1)
                statements.append({
                    'type': 'nonblocking' if '<=' in line else 'blocking',
                    'target': target.replace('<=', '').replace('=', '').strip(),
                    'value': value.strip()
                })
                i += 1
                
            else:
                i += 1
                
        return statements
    
    def _parse_case_block(self, lines: List[str]) -> Dict[str, Any]:
        """Parse a SystemVerilog case block and return the node and number of lines consumed"""
        first_line = lines[0]
        case_type = 'case'
        if first_line.startswith('unique case'):
            case_type = 'unique_case'
        elif first_line.startswith('priority case'):
            case_type = 'priority_case'
            
        expression = re.search(r'case\s*\((.*?)\)', first_line).group(1)
        
        cases = []
        lines_consumed = 1
        
        while lines_consumed < len(lines):
            line = lines[lines_consumed].strip()
            
            if line == 'endcase':
                lines_consumed += 1
                break
                
            # Handle case item
            if ':' in line:
                label, statements = line.split(':', 1)
                label = label.strip()
                
                if 'begin' in statements:
                    # Multi-line case item
                    begin_count = 1
                    case_statements = []
                    lines_consumed += 1
                    
                    while begin_count > 0 and lines_consumed < len(lines):
                        if 'begin' in lines[lines_consumed]:
                            begin_count += 1
                        elif 'end' in lines[lines_consumed]:
                            begin_count -= 1
                        
                        if begin_count > 0:
                            case_statements.append(lines[lines_consumed])
                        lines_consumed += 1
                    
                    cases.append({
                        'label': label,
                        'statements': self._parse_always_block('\n'.join(case_statements))
                    })
                else:
                    # Single-line case item
                    cases.append({
                        'label': label,
                        'statements': self._parse_always_block(statements)
                    })
                    lines_consumed += 1
            else:
                lines_consumed += 1
                
        return {
            'node': {
                'type': case_type,
                'expression': expression,
                'cases': cases
            },
            'lines_consumed': lines_consumed
        }
    
    def _parse_if_block(self, lines: List[str]) -> Dict[str, Any]:
        """Parse an if-else block and return the node and number of lines consumed"""
        first_line = lines[0]
        condition = re.search(r'if\s*\((.*?)\)', first_line).group(1)
        
        true_branch = []
        false_branch = []
        lines_consumed = 1
        
        # Find matching begin/end for true branch
        if 'begin' in lines[lines_consumed]:
            begin_count = 1
            lines_consumed += 1
            
            while begin_count > 0 and lines_consumed < len(lines):
                if 'begin' in lines[lines_consumed]:
                    begin_count += 1
                elif 'end' in lines[lines_consumed]:
                    begin_count -= 1
                
                if begin_count > 0:
                    true_branch.append(lines[lines_consumed])
                lines_consumed += 1
                
        else:
            true_branch.append(lines[lines_consumed])
            lines_consumed += 1
            
        # Check for else
        if lines_consumed < len(lines) and 'else' in lines[lines_consumed]:
            lines_consumed += 1
            
            if lines_consumed < len(lines):
                if 'begin' in lines[lines_consumed]:
                    begin_count = 1
                    lines_consumed += 1
                    
                    while begin_count > 0 and lines_consumed < len(lines):
                        if 'begin' in lines[lines_consumed]:
                            begin_count += 1
                        elif 'end' in lines[lines_consumed]:
                            begin_count -= 1
                        
                        if begin_count > 0:
                            false_branch.append(lines[lines_consumed])
                        lines_consumed += 1
                else:
                    false_branch.append(lines[lines_consumed])
                    lines_consumed += 1
                    
        return {
            'node': {
                'type': 'if_statement',
                'condition': condition,
                'true_branch': self._parse_always_block('\n'.join(true_branch)),
                'false_branch': self._parse_always_block('\n'.join(false_branch))
            },
            'lines_consumed': lines_consumed
        }

    def _parse_block_statements(self, block_content: str) -> List[Dict[str, Any]]:
        """Parse statements within a block"""
        statements = []
        lines = block_content.strip().split(';')
        for line in lines:
            line = line.strip()
            if line:
                if '=' in line:
                    target, value = line.split('=', 1)
                    statements.append({
                        'type': 'blocking' if '=' in line else 'nonblocking',
                        'target': target.strip(),
                        'value': value.strip()
                    })
                elif line.startswith('if'):
                    # Simple if statement parsing (not handling nested ifs or else)
                    condition = re.search(r'if\s*\((.*?)\)', line).group(1)
                    statements.append({
                        'type': 'if_statement',
                        'condition': condition,
                        'true_branch': [],  # Simplified, not parsing the true branch
                        'false_branch': []  # Simplified, not parsing the false branch
                    })
        return statements

    def _print_statements(self, statements: List[Dict[str, Any]], indent: int = 0):
        """Helper to print statement structures"""
        indent_str = " " * indent
        for stmt in statements:
            if stmt['type'] == 'if_statement':
                print(f"{indent_str}If: {stmt['condition']}")
                print(f"{indent_str}Then:")
                self._print_statements(stmt['true_branch'], indent + 2)
                if stmt['false_branch']:
                    print(f"{indent_str}Else:")
                    self._print_statements(stmt['false_branch'], indent + 2)
            elif stmt['type'] == 'case_statement':
                print(f"{indent_str}Case: {stmt['expression']}")
                for item in stmt.get('items', []):
                    print(f"{indent_str} {item}")
            else:
                print(f"{indent_str}{stmt['type']}: {stmt['target']} = {stmt['value']}")

    def _build_dependency_graph(self, nodes: List[Dict[str, Any]], signals: Dict[str, Set[str]]) -> Dict[str, Dict[str, Any]]:
        """Build dependency graph from AST nodes with SystemVerilog support"""
        if self.verbose:
            print("\n=== Building Dependency Graph ===")
        
        # Initialize graph with base signals and their types
        graph = {signal: {
            'deps': set(),
            'type': 'input' if signal in signals['inputs']
                   else 'output' if signal in signals['outputs']
                   else 'parameter' if signal in signals['parameters']
                   else 'constant' if signal in signals['constants']
                   else 'internal',
            'nature': 'combinational',  # Default to combinational unless proven sequential
            'vector_deps': set(),  # Track specific vector bits/ranges used
            'clk_deps': set(),    # Track clock dependencies
            'rst_deps': set()     # Track reset dependencies
        } for signal_list in signals.values() for signal in signal_list}
        
        def extract_base_signal(signal_ref: str) -> Tuple[str, Optional[str]]:
            """Extract base signal name and any vector indexing"""
            match = re.match(r'(\w+)(?:\[(.*?)\])?', signal_ref.strip())
            if match:
                return match.group(1), match.group(2)
            return signal_ref.strip(), None
        
        def extract_dependencies(expression: str) -> Set[Tuple[str, Optional[str]]]:
            """Extract signal names and their vector references from a SystemVerilog expression"""
            if self.verbose:
                print(f"\nExtracting dependencies from expression: {expression}")
                
            # Find all signal references with potential vector indices
            signal_refs = re.finditer(r'\b(\w+)(?:\[(.*?)\])?', expression)
            deps = set()
            
            for match in signal_refs:
                signal = match.group(1)
                vector_ref = match.group(2) if match.group(2) else None
                
                # Skip keywords, numbers, and common operators
                if not signal.isdigit() and signal not in {
                    'begin', 'end', 'if', 'else', 'case', 'endcase',
                    'and', 'or', 'xor', 'not', '&&', '||', '!', '^'
                }:
                    deps.add((signal, vector_ref))
                        
            if self.verbose:
                print(f"Dependencies found: {sorted(deps)}")
            return deps

        # Process nodes to build dependency graph
        for node in nodes:
            if node['type'] == 'continuous_assignment':
                target, target_idx = extract_base_signal(node['target'])
                deps = extract_dependencies(node['value'])
                
                if self.verbose:
                    print(f"\nProcessing continuous assignment to {target}")
                    print(f"Vector index: {target_idx}")
                    print(f"Dependencies: {deps}")
                
                # Add dependencies with vector information
                for dep, vector_ref in deps:
                    graph[target]['deps'].add(dep)
                    if vector_ref:
                        graph[target]['vector_deps'].add((dep, vector_ref))
                    
            elif node['type'] in ['always_ff', 'always_comb']:
                # Process sensitivity list for sequential logic
                if node['type'] == 'always_ff' and 'sensitivity' in node:
                    sens_deps = extract_dependencies(node['sensitivity'])
                    
                    # Identify clock and reset signals
                    for dep, _ in sens_deps:
                        if 'clk' in dep.lower() or 'clock' in dep.lower():
                            if self.verbose:
                                print(f"Found clock: {dep}")
                            for stmt in node.get('statements', []):
                                if stmt['type'] in ['blocking', 'nonblocking']:
                                    target, _ = extract_base_signal(stmt['target'])
                                    graph[target]['clk_deps'].add(dep)
                                    graph[target]['nature'] = 'sequential'
                    
                    if 'rst' in dep.lower() or 'reset' in dep.lower():
                        if self.verbose:
                            print(f"Found reset: {dep}")
                        for stmt in node.get('statements', []):
                            if stmt['type'] in ['blocking', 'nonblocking']:
                                target, _ = extract_base_signal(stmt['target'])
                                graph[target]['rst_deps'].add(dep)
                                graph[target]['nature'] = 'sequential'
                
                # Process statements
                for stmt in node.get('statements', []):
                    if stmt['type'] in ['blocking', 'nonblocking']:
                        target, target_idx = extract_base_signal(stmt['target'])
                        deps = extract_dependencies(stmt['value'])
                        
                        if self.verbose:
                            print(f"\nProcessing {stmt['type']} assignment to {target}")
                            print(f"Vector index: {target_idx}")
                            print(f"Dependencies: {deps}")
                        
                        # Add dependencies with vector information
                        for dep, vector_ref in deps:
                            graph[target]['deps'].add(dep)
                            if vector_ref:
                                graph[target]['vector_deps'].add((dep, vector_ref))

        if self.verbose:
            print("\n=== Final Dependency Graph ===")
            for signal, info in sorted(graph.items()):
                if info['deps']:
                    print(f"\n{signal} ({info['type']}, {info['nature']}):")
                    print(f"  Dependencies: {sorted(info['deps'])}")
                    if info['vector_deps']:
                        print(f"  Vector dependencies: {sorted(info['vector_deps'])}")
                    if info['clk_deps']:
                        print(f"  Clock dependencies: {sorted(info['clk_deps'])}")
                    if info['rst_deps']:
                        print(f"  Reset dependencies: {sorted(info['rst_deps'])}")
                        
        return graph

    def _trace_logic_cone(self, output_signal: str, dependency_graph: Dict[str, Dict[str, Any]], signals: Dict[str, Set[str]]) -> Dict[str, Any]:
        """Trace logic cone with improved vector and sequential/combinational handling"""
        if self.verbose:
            print(f"\n=== Starting Logic Cone Trace for {output_signal} ===")
        
        result = self._empty_analysis_result()
        
        if output_signal not in dependency_graph:
            if self.verbose:
                print(f"Warning: Signal {output_signal} not found in dependency graph")
            return result
        
        visited = set()
        to_visit = {output_signal}
        paths = {output_signal: [[output_signal]]}
        
        while to_visit:
            current = to_visit.pop()
            if current in visited:
                continue
                
            visited.add(current)
            current_info = dependency_graph[current]
            
            # Add clock and reset dependencies for sequential logic
            if current_info['nature'] == 'sequential':
                for clk in current_info['clk_deps']:
                    result['inputs']['clocks'].append(clk)
                for rst in current_info['rst_deps']:
                    result['inputs']['resets'].append(rst)
            
            # Process regular and vector dependencies
            deps_to_process = set()
            deps_to_process.update(current_info['deps'])
            
            # Add specific vector dependencies
            vector_deps = {dep: idx for dep, idx in current_info.get('vector_deps', set())}
            result['trace']['vector_dependencies'].update(vector_deps)
            
            for dep in deps_to_process:
                if dep in dependency_graph:
                    dep_info = dependency_graph[dep]
                    
                    # Create new paths including this dependency
                    current_paths = paths.get(current, [[current]])
                    new_paths = [path + [dep] for path in current_paths]
                    paths[dep] = paths.get(dep, []) + new_paths
                    
                    # Categorize dependency
                    if dep_info['type'] == 'input':
                        if dep in vector_deps:
                            result['inputs']['primary'].append(f"{dep}[{vector_deps[dep]}]")
                        else:
                            result['inputs']['primary'].append(dep)
                    elif dep_info['type'] == 'parameter':
                        result['inputs']['parameters'].append(dep)
                    elif dep_info['type'] == 'constant':
                        result['inputs']['constants'].append(dep)
                    elif dep_info['nature'] == 'sequential':
                        result['inputs']['flops'].append(dep)
                        result['trace']['sequential_elements'].append(dep)
                    elif dep_info['nature'] == 'combinational':
                        result['trace']['combinational_elements'].append(dep)
                    
                    if dep not in visited:
                        to_visit.add(dep)
        
        # Clean up and sort results
        for category in result['inputs']:
            result['inputs'][category] = sorted(set(result['inputs'][category]))
        
        result['trace']['signal_flow'] = sorted(visited)
        
        # Build combinational paths (excluding clock/reset signals)
        result['trace']['combinational_paths'] = [
            path for path in paths.values()
            if path and path[0] == output_signal and 
               path[-1] in result['inputs']['primary'] and
               not any(sig in result['inputs']['clocks'] or sig in result['inputs']['resets'] 
                      for sig in path)
        ]
        
        # Find critical path
        if result['trace']['combinational_paths']:
            result['propagation']['critical_path'] = max(
                result['trace']['combinational_paths'],
                key=len
            )
            result['timing']['levels'] = len(result['propagation']['critical_path']) - 1
        
        # Enhanced dependency information
        result['propagation']['dependencies'] = {
            signal: {
                'deps': sorted(info['deps']),
                'type': info['type'],
                'nature': info['nature'],
                'vector_deps': sorted(info['vector_deps']),
                'clk_deps': sorted(info['clk_deps']),
                'rst_deps': sorted(info['rst_deps'])
            }
            for signal, info in dependency_graph.items() 
            if signal in visited
        }
        
        return result

    def _empty_analysis_result(self) -> Dict[str, Any]:
        """Create an empty analysis result structure"""
        return {
            'inputs': {
                'primary': [],
                'flops': [],
                'constants': [],
                'parameters': [],
                'clocks': [],
                'resets': []
            },
            'trace': {
                'signal_flow': [],
                'combinational_paths': [],
                'sequential_elements': [],
                'combinational_elements': [],
                'vector_dependencies': {}
            },
            'propagation': {
                'critical_path': [],
                'dependencies': {}
            },
            'timing': {
                'levels': 0
            }
        }

    def generate_test_vectors(self, n: int) -> List[Dict[str, Any]]:
        """Generate n random test vectors based on RTL interface ports"""
        import random
        
        port_info = self._extract_port_info()
        test_vectors = []
        
        for _ in range(n):
            vector = {}
            for name, info in port_info.items():
                if info['direction'] == 'input':
                    width = info['width']
                    if width == 1:
                        vector[name] = random.randint(0, 1)
                    else:
                        vector[name] = random.randint(0, (1 << width) - 1)
            test_vectors.append(vector)

        return test_vectors

    def generate_testbench(self, test: TestCase) -> str:
        """Generate a SystemVerilog testbench with LLM-generated self-checking"""
        try:
            # Get cached module info
            module_info = self._get_cached_module_info()
            module_name = module_info['name']
            ports = module_info['ports']
            output_ports = module_info['output_ports']
            clock_ports = module_info['clock_ports']
            reset_ports = module_info['reset_ports']

            # Rest of the method remains the same but uses module_info...

            # First get expected outputs from LLM
            expected_prompt = f"""Given this RTL module and test inputs, predict the expected output values.
You must provide a value for EVERY output port.

RTL Module:
{self.rtl}

Test Case:
Name: {test.name}
Description: {test.description}
Inputs: {test.inputs}

Available output ports:
{json.dumps(output_ports, indent=2)}

Return expected outputs in this format:
<expected>
{{
    // You must include ALL of these output ports with values:
    {', '.join(f'"{p["name"]}": value' for p in output_ports)}
}}
</expected>"""

            # Get expected outputs
            expected_response = self.chat(
                user_input=expected_prompt,
                provider="anthropic",
                model="claude-3-5-sonnet-20241022",
                temperature=0.2
            )

            # Parse expected outputs
            try:
                start = expected_response.find("<expected>")
                end = expected_response.find("</expected>")
                if start != -1 and end != -1:
                    json_str = expected_response[start + 10:end].strip()
                    # Clean up JSON string
                    json_str = re.sub(r"//.*$", "", json_str, flags=re.MULTILINE)  # Remove comments
                    json_str = re.sub(r"(\w+):", r'"\1":', json_str)  # Add quotes around keys
                    json_str = re.sub(r",\s*}", "}", json_str)  # Remove trailing commas
                    json_str = re.sub(r",\s*]", "]", json_str)  # Remove trailing commas in arrays
                    
                    # Try to parse the JSON
                    try:
                        expected_outputs = json.loads(json_str)
                        
                        # Validate that all output ports have values
                        missing_ports = [p['name'] for p in output_ports if p['name'] not in expected_outputs]
                        if missing_ports:
                            if self.verbose:
                                print(f"Missing expected values for ports: {missing_ports}")
                                print("Using default value 0 for missing ports")
                            for port in missing_ports:
                                expected_outputs[port] = 0
                        
                        # Update test case with expected outputs
                        test.expected.update(expected_outputs)
                        
                    except json.JSONDecodeError as e:
                        print(f"JSON parsing error: {str(e)}")
                        print(f"Problematic JSON string: {json_str}")
                        expected_outputs = {p['name']: 0 for p in output_ports}  # Default all to 0
                        test.expected.update(expected_outputs)
                        
            except Exception as e:
                if self.verbose:
                    print(f"Error parsing expected outputs: {str(e)}")
                    print(f"Raw response: {expected_response}")
                # Set default values
                expected_outputs = {p['name']: 0 for p in output_ports}
                test.expected.update(expected_outputs)

            # Use cached module info
            if not hasattr(self, '_cached_module_info'):
                module_match = re.search(r'module\s+(\w+)', self.rtl)
                if not module_match:
                    raise ValueError("Could not find module name in RTL")
                
                modules = self._parse_rtl_modules()
                if not modules:
                    raise ValueError("Could not parse module ports")
                
                self._cached_module_info = {
                    'name': module_match.group(1),
                    'ports': modules[0]['ports']
                }
            
            module_name = self._cached_module_info['name']
            ports = self._cached_module_info['ports']

            # Get intelligent assertions from LLM
#             assertion_prompt = f"""Generate SystemVerilog assertions for this test case.
# Use EXACTLY this format for each assertion:

#     // Assertion name and description
#     property p_name;
#         @(posedge clk) disable iff (!rst_b)
#         CONDITION;
#     endproperty
    
#     assert property(p_name)
#         else $error("ERROR_MESSAGE");

# Example:
#     // Check IDLE state when not enabled
#     property p_idle_when_disabled;
#         @(posedge clk) disable iff (!rst_b)
#         !bist_wr_en |-> state == 4'h0;
#     endproperty
    
#     assert property(p_idle_when_disabled)
#         else $error("State should be IDLE when disabled");

# RTL Module:
# {self.rtl}

# Test Case:
# Name: {test.name}
# Inputs: {test.inputs}
# Expected: {test.expected}

# Format response as:
# <assertions>
# [
#     {{
#         "name": "assertion_name",
#         "type": "protocol|timing|data",
#         "assertion": "complete_assertion_block",  // Include full property and assert statements
#         "message": "failure_message"
#     }}
# ]
# </assertions>"""

#             assertions_response = self.chat(
#                 user_input=assertion_prompt,
#                 provider="anthropic",
#                 model="claude-3-5-sonnet-20241022",
#                 temperature=0.2
#             )

#             # Parse assertions
#             try:
#                 start = assertions_response.find("<assertions>")
#                 end = assertions_response.find("</assertions>")
#                 if start != -1 and end != -1:
#                     json_str = assertions_response[start + 12:end].strip()
                    
#                     # Clean up JSON string
#                     json_str = re.sub(r"//.*$", "", json_str, flags=re.MULTILINE)  # Remove comments
#                     json_str = re.sub(r"[\n\r\t]", " ", json_str)  # Replace newlines and tabs with spaces
#                     json_str = re.sub(r"\s+", " ", json_str)  # Normalize whitespace
#                     json_str = re.sub(r';\s*endproperty', "; endproperty", json_str)  # Fix property endings
#                     json_str = re.sub(r'property\s+', "property ", json_str)  # Fix property starts
#                     json_str = re.sub(r'assert\s+property', "assert property", json_str)  # Fix assert property
#                     json_str = re.sub(r',\s*}', "}", json_str)  # Remove trailing commas
#                     json_str = re.sub(r',\s*]', "]", json_str)  # Remove trailing commas in arrays
#                     json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)  # Remove control characters
#                     json_str = re.sub(r'0b[01]+', lambda m: str(int(m.group(0)[2:], 2)), json_str)  # Convert binary to decimal
                    
#                     if self.verbose:
#                         print(f"Cleaned assertion JSON: {json_str}")
                    
#                     assertions = json.loads(json_str)
                    
#                     # Format assertions for SystemVerilog
#                     formatted_assertions = []
#                     for assertion in assertions:
#                         if isinstance(assertion, dict) and 'assertion' in assertion:
#                             # Format the assertion text with proper indentation and newlines
#                             assertion_text = assertion['assertion']
#                             assertion_text = re.sub(r'\s+', ' ', assertion_text)  # Normalize whitespace
#                             assertion_text = assertion_text.replace('property ', 'property\n        ')
#                             assertion_text = assertion_text.replace('@(posedge', '\n        @(posedge')
#                             assertion_text = assertion_text.replace('|-> ', '\n        |-> ')
#                             assertion_text = assertion_text.replace('endproperty', '\n    endproperty')
#                             assertion_text = assertion_text.replace('assert property', '\n    assert property')
#                             assertion_text = assertion_text.replace('else', '\n        else')
#                             assertion['assertion'] = assertion_text
#                             formatted_assertions.append(assertion)
                    
#                     assertions = formatted_assertions
                    
#                 else:
#                     assertions = []
                    
#             except Exception as e:
#                 if self.verbose:
#                     print(f"Error parsing assertions: {str(e)}")
#                     print(f"Raw response: {assertions_response}")

            assertions = []

            # Generate testbench
            tb = []
            
            # Add module header
            tb.extend([
                "`timescale 1ns/1ps",
                "",
                f"module {module_name}_tb;",
                "",
                "    // Testbench signals"
            ])
            
            # Declare all ports as logic
            for port in ports:
                width_str = f"[{port['width']-1}:0] " if isinstance(port['width'], int) and port['width'] > 1 else ""
                tb.append(f"    logic {width_str}{port['name']};")
            
            # Add clock generation for any clock signals
            clock_ports = [p for p in ports if p['name'].lower() in ['clk', 'clock']]
            for clock in clock_ports:
                tb.extend([
                    "",
                    f"    // {clock['name']} generation",
                    f"    initial begin",
                    f"        {clock['name']} = 0;",
                    f"        forever #5 {clock['name']} = ~{clock['name']};",
                    f"    end"
                ])
            
            # Add reset generation for any reset signals
            reset_ports = [p for p in ports if any(r in p['name'].lower() for r in ['rst', 'reset'])]
            for reset in reset_ports:
                active_low = any(s in reset['name'].lower() for s in ['_n', 'b'])
                init_val = '1' if active_low else '0'
                final_val = '0' if active_low else '1'
                tb.extend([
                    "",
                    f"    // {reset['name']} generation",
                    f"    task reset_dut();",
                    f"        {reset['name']} = {init_val};",
                    "        // Initialize all inputs",
                ])
                
                # Initialize all inputs to 0
                for port in ports:
                    if port['direction'] == 'input' and port['name'] not in [p['name'] for p in clock_ports + reset_ports]:
                        tb.append(f"        {port['name']} = 0;")
                
                tb.extend([
                    "        #100;",
                    f"        {reset['name']} = {final_val};",
                    "        #100;",
                    "    endtask"
                ])

            # Add DUT instance
            tb.extend([
                "",
                "    // DUT instance",
                f"    {module_name} dut (",
                ",\n".join(f"        .{p['name']}({p['name']})" for p in ports),
                "    );"
            ])

            # Add assertions with proper SystemVerilog syntax
            if assertions:
                tb.extend(["", "    // Assertions"])
                for assertion in assertions:
                    tb.extend([
                        f"    // {assertion['name']}: {assertion['type']} check",
                        f"{assertion['assertion']}"  # Already properly formatted from LLM
                    ])

            # Add test stimulus
            tb.extend([
                "",
                "    // Test stimulus",
                "    initial begin",
                "        // Initialize and reset",
                "        reset_dut();",
                "",
                f"        // Test vector: {test.name}",
                # f"        // Description: {test.description}",
                "",
                "        // Apply test inputs"
            ])

            # Apply test inputs directly from test case
            for port_name, value in test.inputs.items():
                # Find port info
                port = next((p for p in ports if p['name'] == port_name), None)
                if port:
                    width = port['width']
                    if isinstance(width, int) and width > 1:
                        tb.append(f"        {port_name} = {width}'h{value:x};")
                    else:
                        tb.append(f"        {port_name} = {value};")

            # Add delay for outputs to stabilize
            tb.append("        #100;  // Wait for outputs to stabilize")

            # Add output checking with expected values
            tb.extend([
                "",
                "        // Wait for outputs to stabilize",
                "        #100;",
                "",
                "        // Check outputs",
                f"        // Expected behavior: {test.expected.get('expected_behavior', '')}"
            ])

            # Add output checking
            for port in ports:
                if port['direction'] == 'output' and port['name'] in test.expected:
                    expected = test.expected[port['name']]
                    width = port['width']
                    if isinstance(width, int) and width > 1:
                        tb.extend([
                            f"        // Check {port['name']}",
                            f"        if ({port['name']} !== {width}'h{expected:x}) begin",
                            f'            $display("Error: {port["name"]} = %h, expected %h at time %t", {port["name"]}, {width}\'h{expected:x}, $time);',
                            f'            $display("Test failed: Output {port["name"]} mismatch");',
                            "            $finish;",
                            "        end else begin",
                            f'            $display("Output {port["name"]} check passed");',
                            "        end"
                        ])
                    else:
                        tb.extend([
                            f"        // Check {port['name']}",
                            f"        if ({port['name']} !== {expected}) begin",
                            f'            $display("Error: {port["name"]} = %b, expected %b at time %t", {port["name"]}, {expected}, $time);',
                            f'            $display("Test failed: Output {port["name"]} mismatch");',
                            "            $finish;",
                            "        end else begin",
                            f'            $display("Output {port["name"]} check passed");',
                            "        end"
                        ])

            # Add test completion
            tb.extend([
                "",
                "        // All checks passed",
                f'        $display("All output checks passed for test: {test.name}");',
                # f'        $display("Test description: {test.description}");',
                "        $finish;",
                "    end",
                "",
                "    // Waveform dumping",
                "    initial begin",
                '        $dumpfile("dump.vcd");',
                f"        $dumpvars(0, {module_name}_tb);",
                "    end",
                "",
                "endmodule"
            ])

            # Create final testbench string
            testbench = "\n".join(tb)
            
            # Save testbench and compile log
            try:
                os.makedirs("vpx_outputs", exist_ok=True)
                
                # Save testbench
                tb_file = os.path.join("vpx_outputs", f"{test.name}_tb.sv")
                with open(tb_file, 'w') as f:
                    f.write(testbench)
                
                # Save RTL temporarily
                rtl_file = os.path.join("vpx_outputs", "temp_dut.sv")
                with open(rtl_file, 'w') as f:
                    f.write(self.rtl)
                
                # Run compilation to get log
                compile_cmd = f"iverilog -g2012 -Y .sv -o /dev/null {rtl_file} {tb_file}"
                compile_result = subprocess.run(compile_cmd, shell=True, capture_output=True, text=True)
                
                # Save compile log
                log_file = os.path.join("vpx_outputs", f"{test.name}_compile.log")
                with open(log_file, 'w') as f:
                    f.write("=== Compilation Command ===\n")
                    f.write(f"{compile_cmd}\n\n")
                    f.write("=== Stdout ===\n")
                    f.write(compile_result.stdout)
                    f.write("\n=== Stderr ===\n")
                    f.write(compile_result.stderr)
                
                # Clean up temporary RTL file
                os.remove(rtl_file)
                
                if self.verbose:
                    print(f"Saved testbench to: {tb_file}")
                    print(f"Saved compile log to: {log_file}")
                
            except Exception as e:
                if self.verbose:
                    print(f"Error saving testbench and log: {str(e)}")
            
            return testbench
        
        except Exception as e:
            if self.verbose:
                print(f"Error generating testbench: {str(e)}")
            return ""

    def _refine_timing_analysis(self, timing: str) -> str:
        prompt = f"""<timing>
    {timing}
    </timing>

    Review and enhance this timing analysis to be crystal clear for RTL generation:

    1. Verify the timing diagram:
    - Are all critical transitions shown?
    - Are cycle labels clear and complete?
    - Is the sequence long enough to show all cases?

    2. Check cycle explanations:
    - Is each transition fully explained?
    - Are detection points emphasized?
    - Is causality clear?

    3. Review timing rules:
    - Are register dependencies explicit?
    - Is update ordering unambiguous?
    - Are race conditions addressed?

    Make the timing analysis more explicit and clearer. Return in <answer> tags using exact same format but with improvements."""

        response = self.chat(
            user_input=prompt,
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            streaming=True,
            temperature=0.2
        )
        return self._extract_answer(response)

    def verify_rtl_timing(self) -> str:
        prompt = f"""<systemverilog>
{self.context.rtl}
</systemverilog>

Verify that the SystemVerilog code meets the timing requirements:

1. REVIEW REQUIREMENTS
---------------------
1.1 EXPECTED TIMING:
    <timing_diagram>
    {self.context.timing_plan.cycle_diagram}
    </timing_diagram>

1.2 REGISTER DEPENDENCIES (TIMING-CRITICAL):
    <dependencies>
    {self.context.timing_plan.register_deps}
    </dependencies>

2. CHECK AGAINST COMMON BUGS
---------------------------
2.1 EDGE DETECTION LOGIC
    a) WITH CORRECT LOGIC:
       [Reference timing diagram shows proper detection]

    b) WITH WRONG LOGIC:
       [Same timing points but wrong output transitions]
       ```systemverilog
       // Example Wrong:
       out <= out | (~in & prev_in);  // Wrong order
       // Should match edge specified in requirements
       ```

2.2 REGISTER UPDATE ORDER
    a) WITH CORRECT ORDER:
       [Reference timing shows value used then updated]
    
    b) WITH WRONG ORDER:
       [Shows race condition impact on timing]
       ```systemverilog
       // Example Wrong:
       always_ff @(posedge clk) begin
           prev_value <= new_value;  // Updates too early
           out <= out | (prev_value & condition);
       end
       ```

2.3 STATE PRESERVATION
    a) WITH CORRECT PRESERVATION:
       [Reference timing shows maintained state]
    
    b) WITH WRONG PRESERVATION:
       [Shows state lost between cycles]
       ```systemverilog
       // Example Wrong:
       out <= (condition_met);  // Loses previous state
       // Should maintain state as specified
       ```

2.4 RESET BEHAVIOR
    a) WITH CORRECT RESET:
       [Reference timing shows proper reset sequence]
    
    b) WITH WRONG RESET:
       [Shows incorrect reset timing]
       ```systemverilog
       // Example Wrong:
       always_ff @(posedge clk or posedge rst)  // Async
       // Should match reset type specified
       ```

3. VERIFY IMPLEMENTATION
-----------------------
3.1 CHECK SEQUENCE:
    a) Find all edge detection logic
       - Compare against specified edge type
       - Check operation order matches timing

    b) Review register updates
       - Compare against <dependencies>
       - Verify values used before updated
       - Check update order matches timing

    c) Verify state handling
       - Check states maintained as specified
       - Verify reset behavior correct
       - Confirm timing diagram matched

    d) Look for timing violations
       - Race conditions
       - Update order issues
       - Reset timing problems

4. PROVIDE ANALYSIS
------------------
4.1 Place analysis in <thinking> tags
4.2 List any timing violations found
4.3 Reference specific parts of timing diagram
4.4 Map issues to specification requirements

5. CORRECTIONS
-------------
5.1 Fix any timing violations
5.2 Maintain specified behavior
5.3 Follow reference timing diagram
5.5 Respect register dependencies

6. KEY POINTS TO CHECK
-----------------------------------
□ Edge detection matches specification
□ Register updates in correct order
□ State preserved as required
□ Reset behavior matches spec
□ All timing requirements met

Place your step-by-step reasoning in <thinking> tags and the final RTL in <answer> tags.
The <answer> should contain only the SystemVerilog code with no other text."""

        response = self.chat(
            user_input=prompt,
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            streaming=True,
            temperature=0.2
        )
        return self._extract_answer(response)

    def _extract_answer(self, response: str) -> str:
        start = response.find("<answer>")
        end = response.find("</answer>")
        if start != -1 and end != -1:
            return response[start + 8:end].strip()
        return response

    def _generate_intelligent_test_vectors(self, modules: List[Dict], num_tests: int) -> List[TestCase]:
        """Generate intelligent test vectors using LLM analysis"""
        if self.verbose:
            print("\n=== Generating Intelligent Test Vectors ===")
            print(f"Requesting {num_tests} test vectors")
        
        tests = []
        
        # Get all input ports from module
        input_ports = {}
        for module in modules:
            for port in module['ports']:
                if port['direction'] == 'input':
                    input_ports[port['name']] = port
                    if self.verbose:
                        print(f"Input port: {port['name']}, width={port['width']}")
        
        # Create prompt for LLM
        prompt = f"""You are a hardware verification expert. Generate {num_tests} test vectors for this RTL module.
Return ONLY the test vectors in the exact format shown, with no additional text or explanation.

RTL Module:
{self.rtl}

Return test vectors in this exact format:
<test_vectors>
[
  {{
    "name": "test_name",
    "description": "what this test targets",
    "failure_point": "description of potential failure",
    "inputs": {{
      "clk": 0,
      "rst_b": 1,
      "busy": 0,
      "reg_din": 0,
      "reg_bwe": 0,
      "bist_wr_en": 0,
      "dinv": 0,
      "start_add": 0,
      "stop_add": 0,
      "inc_addr": 0
    }},
    "expected": {{
      "state": 0,
      "done": 0,
      "we": 0
    }}
  }}
]
</test_vectors>

Include ALL input ports shown above in each test vector's inputs dictionary."""

        # if self.verbose:
            # print("\nSending prompt to LLM...")
        
        # Get LLM response
        response = self.chat(
            user_input=prompt,
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            temperature=0.2
        )
        
        if self.verbose:
            print("\nReceived LLM response:")
            print(response)
        
        # Parse response
        try:
            # First verify we got the tags and extract JSON carefully
            start = response.find("<test_vectors>")
            end = response.find("</test_vectors>")
            if start == -1 or end == -1:
                if self.verbose:
                    print("\nError: Could not find test_vectors tags in response")
                    print(f"Response content: {response}")
                return tests
                
            # Extract JSON string, skipping the XML tag completely
            json_str = response[start + len("<test_vectors>"):end].strip()
            
            if self.verbose:
                print("\nExtracted JSON string:")
                print(json_str)
            
            # Clean up JSON string
            # First convert Verilog-style numbers to decimal
            def convert_verilog_number(match):
                width = int(match.group(1))
                base = match.group(2)
                value = match.group(3).replace('_', '')
                
                if base == 'h':
                    return str(int(value, 16))
                elif base == 'b':
                    return str(int(value, 2))
                elif base == 'd':
                    return value
                return '0'
            
            # Replace Verilog-style numbers with decimal values
            json_str = re.sub(r"(\d+)'([hbd])([0-9a-fA-F_]+)", convert_verilog_number, json_str)
            
            # Clean up other JSON formatting
            json_str = re.sub(r"//.*$", "", json_str, flags=re.MULTILINE)  # Remove comments
            json_str = re.sub(r",\s*}", "}", json_str)  # Remove trailing commas
            json_str = re.sub(r",\s*]", "]", json_str)  # Remove trailing commas in arrays
            json_str = re.sub(r'[\n\r\t]', ' ', json_str)  # Replace newlines with spaces
            json_str = re.sub(r'\s+', ' ', json_str)  # Normalize whitespace
            
            if self.verbose:
                print("\nCleaned JSON string:")
                print(json_str)
            
            # Parse JSON
            try:
                test_vectors = json.loads(json_str)
                if not isinstance(test_vectors, list):
                    raise ValueError("Parsed JSON is not a list")
            except json.JSONDecodeError as e:
                if self.verbose:
                    print(f"\nJSON parsing error: {str(e)}")
                    print(f"Position: {e.pos}")
                    print(f"Line: {e.lineno}, Column: {e.colno}")
                    print(f"Document: {e.doc}")
                return tests
            
            if self.verbose:
                print(f"\nSuccessfully parsed {len(test_vectors)} test vectors")
            
            # Convert to TestCase objects
            for i, vector in enumerate(test_vectors):
                if self.verbose:
                    print(f"\nProcessing test vector {i}:")
                    print(f"Name: {vector.get('name', 'unnamed')}")
                    print(f"Description: {vector.get('description', 'no description')}")
                    print(f"Failure point: {vector.get('failure_point', 'no failure point')}")
                    print("Input values:")
                
                # Ensure all input ports have values
                inputs = {}
                for port_name, port_info in input_ports.items():
                    if port_name in vector['inputs']:
                        inputs[port_name] = vector['inputs'][port_name]
                        if self.verbose:
                            print(f"  {port_name} = {vector['inputs'][port_name]} (from LLM)")
                    else:
                        # Default values for missing ports
                        if port_name.lower() in ['clk', 'clock']:
                            inputs[port_name] = 0
                        elif any(r in port_name.lower() for r in ['rst', 'reset']):
                            inputs[port_name] = 1 if '_n' in port_name.lower() else 0
                        else:
                            inputs[port_name] = 0
                        if self.verbose:
                            print(f"  {port_name} = {inputs[port_name]} (default value)")
                
                test = TestCase(
                    name=f"llm_test_{i}_{vector['name']}",
                    type=TestType.DIRECTED,
                    inputs=inputs,
                    expected=vector.get('expected', {}),
                    description=f"{vector['description']}\nFailure Point: {vector['failure_point']}"
                )
                tests.append(test)
                self.store_test_case(test)
                
                if self.verbose:
                    print(f"\nCreated test case:")
                    print(f"Name: {test.name}")
                    print(f"Type: {test.type}")
                    print(f"Inputs: {test.inputs}")
                    print(f"Expected: {test.expected}")
                    print(f"Description: {test.description}")
        
        except Exception as e:
            if self.verbose:
                print(f"\nError parsing LLM response: {str(e)}")
                print(f"Response: {response}")
                import traceback
                print("Traceback:")
                traceback.print_exc()
        
        if self.verbose:
            print(f"\nGenerated {len(tests)} intelligent test vectors")
            print("=== Test Vector Generation Complete ===\n")
        
        return tests

    def run_verification(self, test_dir: Optional[str] = None, gui_callback: Optional[Callable] = None) -> Dict:
        """Run comprehensive verification flow"""
        results = {
            'test_cases': [],
            'assertions': [],
            'coverage': {}
        }
        
        # 1. Parse and analyze RTL
        modules = self._parse_rtl_modules()
        
        # 2. Generate test cases
        test_cases = []
        
        # 2.1 Load directed test cases from test_dir if provided
        if test_dir:
            test_cases.extend(self._load_test_cases(test_dir))
            
        # 2.2 Generate intelligent test vectors using LLM first (increased to 20)
        llm_tests = self._generate_intelligent_test_vectors(modules, num_tests=5)
        test_cases.extend(llm_tests)
        
        # 2.3 Generate boundary test cases (keep at 20)
        # boundary_tests = self._generate_boundary_tests(modules)
        # test_cases.extend(boundary_tests)
        
        # 3. Generate assertions
        assertions = self._generate_assertions(modules)
        
        # 4. Run simulation for each test case
        if gui_callback:
            # Notify GUI of total test count
            gui_callback("Starting Tests", {
                "status": f"Starting {len(test_cases)} tests...",
                "total_tests": len(test_cases),
                "action": "init_tests"
            })
        
        for test in test_cases:
            if gui_callback:
                gui_callback("Running Test", {
                    "status": f"Running test: {test.name}",
                    "test": test,
                    "action": "start_test"
                })
                
            result = self._run_test_case(test, assertions)
            results['test_cases'].append(result)
            
            # Notify GUI of test completion
            if gui_callback:
                gui_callback("Test Complete", {
                    "status": f"Test complete: {test.name}",
                    "test": test,
                    "result": result,
                    "action": "test_complete"
                })
        
        # 5. Calculate coverage
        results['coverage'] = self._calculate_coverage(modules, results['test_cases'])
        
        # 6. Analyze assertion results
        results['assertions'] = self._analyze_assertions(assertions)
        
        return results
        
    def _parse_rtl_modules(self) -> List[Dict]:
        """Parse RTL into module definitions"""
        modules = []
        
        # Updated pattern to better handle parameterized modules and port lists
        module_pattern = (
            r'module\s+(\w+)'  # Module name
            r'\s*(?:#\s*\(\s*((?:[^()]|\([^()]*\))*)\s*\))?\s*'  # Optional parameters
            r'\s*\(\s*((?:[^()]|\([^()]*\))*)\s*\)\s*;'  # Port list
            r'\s*((?:(?!endmodule).)*?)'  # Module body
            r'endmodule'  # End of module
        )
        
        if self.verbose:
            print("\nParsing RTL content:")
            print("-" * 40)
            print(f"RTL length: {len(self.rtl)} characters")
            print("\nFirst 200 chars of RTL:")
            print("-" * 40)
            print(self.rtl[:200])
            
        # Try to find all module matches
        matches = list(re.finditer(module_pattern, self.rtl, re.DOTALL))
        
        if self.verbose:
            print(f"\nFound {len(matches)} module matches")
            
            if not matches:
                print("\nTrying to debug pattern match failure:")
                print(f"Pattern used: {module_pattern}")
                # Try simpler patterns to isolate the issue
                simple_matches = re.findall(r'module\s+(\w+)', self.rtl)
                print(f"Found {len(simple_matches)} basic module names: {simple_matches}")
                
                # Try to find module boundaries
                starts = [m.start() for m in re.finditer(r'module\s+', self.rtl)]
                ends = [m.start() for m in re.finditer(r'endmodule', self.rtl)]
                print(f"Found {len(starts)} module starts at positions: {starts}")
                print(f"Found {len(ends)} module ends at positions: {ends}")
        
        for i, match in enumerate(matches):
            try:
                name = match.group(1)
                params_text = match.group(2) if match.group(2) else ""
                ports_text = match.group(3)
                body = match.group(4)
                
                if self.verbose:
                    print(f"\nProcessing module {i+1}: {name}")
                    print(f"Match groups:")
                    print(f"  1 (name): {name}")
                    print(f"  2 (params): {params_text[:100] + '...' if len(params_text) > 100 else params_text}")
                    print(f"  3 (ports): {ports_text[:100] + '...' if len(ports_text) > 100 else ports_text}")
                    print(f"  4 (body): {body[:100] + '...' if len(body) > 100 else body}")
                
                # Parse parameters
                parameters = []
                if params_text:
                    param_declarations = [p.strip() for p in params_text.split(',') if p.strip()]
                    for decl in param_declarations:
                        param = {'name': '', 'type': '', 'default': None}
                        parts = decl.split('=')
                        
                        # Parse parameter name and type
                        type_name = parts[0].strip().split()
                        if len(type_name) > 1:
                            param['type'] = type_name[0]
                            param['name'] = type_name[1]
                        else:
                            param['name'] = type_name[0]
                        
                        # Parse default value if present
                        if len(parts) > 1:
                            param['default'] = parts[1].strip()
                        
                        parameters.append(param)
                        
                        if self.verbose:
                            print(f"Added parameter: {param}")
                
                # Parse ports
                ports = []
                # Split on commas but handle multi-line declarations
                port_declarations = [p.strip() for p in re.split(r',\s*(?=(?:[^()]*\([^()]*\))*[^()]*$)', ports_text) if p.strip()]
                
                if self.verbose:
                    print(f"Found {len(port_declarations)} port declarations")
                    for decl in port_declarations:
                        print(f"  Port declaration: {decl}")
                
                for decl in port_declarations:
                    # Initialize port info
                    port = {'direction': '', 'width': 1, 'name': '', 'type': 'wire'}
                    
                    # Clean up declaration
                    decl = re.sub(r'\s+', ' ', decl.strip())
                    parts = decl.split()
                    
                    for i, part in enumerate(parts):
                        if part in ['input', 'output', 'inout']:
                            port['direction'] = part
                        elif part in ['wire', 'reg', 'logic']:
                            port['type'] = part
                        elif '[' in part and ']' in part:
                            # Parse vector width - handle parameterized widths
                            width_match = re.search(r'\[(.*?):(.*?)\]', part)
                            if width_match:
                                high = width_match.group(1).strip()
                                low = width_match.group(2).strip()
                                # If numeric, calculate width
                                if high.isdigit() and low.isdigit():
                                    port['width'] = int(high) - int(low) + 1
                                else:
                                    # Store expression for parameterized width
                                    port['width'] = f"{high}:{low}"
                        elif i == len(parts) - 1:  # Last part is always the name
                            port['name'] = part.rstrip(';')
                    
                    if port['direction'] and port['name']:
                        ports.append(port)
                        if self.verbose:
                            print(f"Added port: {port}")
                
                # Extract signals from body
                signals = self._extract_signals(body)
                
                # Create module info
                module_info = {
                    'name': name,
                    'parameters': parameters,
                    'ports': ports,
                    'body': body,
                    'signals': signals
                }
                
                modules.append(module_info)
                
                if self.verbose:
                    print(f"\nModule {name} parsed successfully")
                    print(f"Found {len(parameters)} parameters")
                    print(f"Found {len(ports)} ports")
                    print(f"Body length: {len(body)}")
                    
            except Exception as e:
                if self.verbose:
                    print(f"Error parsing module {i+1}:")
                    print(f"Exception: {str(e)}")
                    print("Match groups:")
                    for j, group in enumerate(match.groups()):
                        print(f"  Group {j}: {group[:100] + '...' if group and len(group) > 100 else group}")
        
        if self.verbose:
            print(f"\nFinal results:")
            print(f"Total modules found: {len(modules)}")
            for module in modules:
                print(f"\nModule: {module['name']}")
                print(f"Parameters: {len(module['parameters'])}")
                print(f"Ports: {len(module['ports'])}")
                print(f"Body length: {len(module['body'])}")
        
        return modules
        
    def _generate_boundary_tests(self, modules: List[Dict]) -> List[TestCase]:
        """Generate test cases for boundary conditions"""
        tests = []
        
        for module in modules:
            # First, collect all input ports and their info
            input_ports = {
                p['name']: p for p in module['ports'] 
                if p['direction'] == 'input'
            }
            
            # Generate base input dictionary with all inputs set to 0
            base_inputs = {name: 0 for name in input_ports.keys()}
            
            # Now generate boundary tests for each input port
            for port_name, port in input_ports.items():
                # Test minimum value (all inputs 0, current port at min)
                min_inputs = base_inputs.copy()  # All inputs start at 0
                tests.append(TestCase(
                    name=f"{module['name']}_{port_name}_min",
                    type=TestType.BOUNDARY,
                    inputs=min_inputs,
                    expected={},
                    description=f"Test minimum value for {port_name}"
                ))
                
                # Test maximum value (all inputs 0, current port at max)
                max_inputs = base_inputs.copy()
                width = port['width']
                if isinstance(width, int) and width > 1:
                    max_inputs[port_name] = (1 << width) - 1
                else:
                    max_inputs[port_name] = 1
                
                tests.append(TestCase(
                    name=f"{module['name']}_{port_name}_max",
                    type=TestType.BOUNDARY,
                    inputs=max_inputs,
                    expected={},
                    description=f"Test maximum value for {port_name}"
                ))
                
                if self.verbose:
                    print(f"\nGenerated boundary tests for {port_name}:")
                    print(f"Min test inputs: {min_inputs}")
                    print(f"Max test inputs: {max_inputs}")
        
        return tests
        
    def _generate_random_tests(self, modules: List[Dict], num_tests: int) -> List[TestCase]:
        """Generate random test cases"""
        tests = []
        
        for module in modules:
            # Collect all input ports and their info
            input_ports = {
                p['name']: p for p in module['ports'] 
                if p['direction'] == 'input'
            }
            
            # Generate random tests
            for i in range(num_tests):
                # Generate random values for all inputs
                inputs = {}
                for port_name, port in input_ports.items():
                    width = port['width']
                    if isinstance(width, int) and width > 1:
                        inputs[port_name] = random.randint(0, (1 << width) - 1)
                    else:
                        inputs[port_name] = random.randint(0, 1)
                
                tests.append(TestCase(
                    name=f"{module['name']}_random_{i}",
                    type=TestType.RANDOM,
                    inputs=inputs,
                    expected={},
                    description=f"Random test vector {i}"
                ))
                
                if self.verbose:
                    print(f"\nGenerated random test {i}:")
                    print(f"Inputs: {inputs}")
        
        return tests
        
    def _generate_assertions(self, modules: List[Dict]) -> List[Assertion]:
        """Generate assertions for design verification"""
        assertions = []
        
        for module in modules:
            # Protocol assertions
            for port in module['ports']:
                if 'valid' in port['name'].lower():
                    # Add handshake assertion
                    ready_port = next(
                        (p for p in module['ports'] if 'ready' in p['name'].lower()),
                        None
                    )
                    if ready_port:
                        assertions.append(Assertion(
                            name=f"{module['name']}_handshake",
                            condition=f"@(posedge clk) {port['name']} && !{ready_port['name']} |=> {port['name']}"
                        ))
            
            # Data integrity assertions
            data_ports = [p for p in module['ports'] if 'data' in p['name'].lower()]
            for port in data_ports:
                assertions.append(Assertion(
                    name=f"{module['name']}_{port['name']}_stable",
                    condition=f"@(posedge clk) {port['name']} == $past({port['name']})"
                ))
                
        return assertions
        
    def _run_test_case(self, test: TestCase, assertions: List[Assertion]) -> Dict:
        """Run a single test case with assertions"""
        try:
            # Initialize result
            result = {
                'name': test.name,
                'passed': False,
                'error': None,
                'coverage': {},
                'assertion_results': []
            }
            
            # Create temporary directory for test files
            with tempfile.TemporaryDirectory() as tmpdir:
                # Save RTL to file
                rtl_file = os.path.join(tmpdir, "dut.sv")
                with open(rtl_file, "w") as f:
                    f.write(self.rtl)
                
                # Generate and save testbench
                tb = self.generate_testbench(test)
                tb_file = os.path.join(tmpdir, "testbench.sv")
                with open(tb_file, "w") as f:
                    f.write(tb)
                
                # Create vpx_outputs directory
                os.makedirs("vpx_outputs", exist_ok=True)
                
                # Set VCD file path in vpx_outputs
                vcd_file = os.path.join("vpx_outputs", f"{test.name}.vcd")
                
                # Modify testbench to use correct VCD path
                tb = tb.replace('$dumpfile("dump.vcd")', f'$dumpfile("{vcd_file}")')
                with open(tb_file, "w") as f:
                    f.write(tb)
                
                # Compile with iverilog
                output_file = os.path.join(tmpdir, "sim.vvp")
                compile_cmd = f"iverilog -g2012 -Y .sv -o {output_file} {rtl_file} {tb_file}"
                compile_result = subprocess.run(compile_cmd, shell=True, capture_output=True, text=True)
                
                if compile_result.returncode != 0:
                    result['error'] = f"Compilation failed: {compile_result.stderr}"
                    return result
                
                # Run simulation
                sim_cmd = f"vvp {output_file}"
                sim_result = subprocess.run(sim_cmd, shell=True, capture_output=True, text=True)
                
                # Check simulation output
                if "Test passed!" in sim_result.stdout:
                    result['passed'] = True
                else:
                    result['error'] = f"Simulation failed: {sim_result.stdout}\n{sim_result.stderr}"
                    
                
                # Parse VCD file for coverage if it exists
                if os.path.exists(vcd_file):
                    try:
                        def parse_vcd(vcd_file) -> Dict:
                            """Parse VCD file into format compatible with coverage calculation"""
                            signals = {}
                            current_time = 0
                            scope = None
                            var_map = {}  # Maps VCD IDs to signal names
                            
                            with open(vcd_file, 'r') as f:
                                for line in f:
                                    line = line.strip()
                                    
                                    # Parse timestamp
                                    if line.startswith('#'):
                                        current_time = int(line[1:])
                                        continue
                                        
                                    # Parse scope
                                    if line.startswith('$scope'):
                                        scope = line.split()[2]
                                        continue
                                        
                                    # Parse variable definitions
                                    if line.startswith('$var'):
                                        parts = line.split()
                                        if len(parts) >= 5:
                                            var_type = parts[1]
                                            width = int(parts[2])
                                            id_code = parts[3]
                                            name = parts[4]
                                            
                                            # Store signal info
                                            full_name = f"{scope}.{name}" if scope else name
                                            signals[full_name] = {
                                                'name': full_name,
                                                'type': var_type,
                                                'width': width,
                                                'values': []
                                            }
                                            var_map[id_code] = full_name
                                        continue
                                        
                                    # Parse signal values
                                    if line and line[0] in '01xz':
                                        value = line[0]
                                        id_code = line[1:].strip()
                                        if id_code in var_map:
                                            signal_name = var_map[id_code]
                                            signals[signal_name]['values'].append((current_time, value))
                                            
                            return signals
                        
                        # Parse VCD and calculate coverage
                        vcd_data = parse_vcd(vcd_file)
                        result['coverage'] = self._calculate_coverage_from_vcd(vcd_data)
                        
                    except Exception as e:
                        if self.verbose:
                            print(f"Error parsing VCD file: {str(e)}")
                
                # Check assertions
                for assertion in assertions:
                    assertion_passed = self._check_assertion(assertion, result)
                    result['assertion_results'].append({
                        'name': assertion.name,
                        'passed': assertion_passed
                    })
                
                return result
        
        except Exception as e:
            return {
                'name': test.name,
                'passed': False,
                'error': str(e)
            }
            
    def _calculate_coverage(self, modules: List[Dict], test_results: List[Dict]) -> Dict:
        """Calculate various coverage metrics"""
        return {
            'line': self._calculate_line_coverage(modules, test_results),
            'branch': self._calculate_branch_coverage(modules, test_results),
            'fsm': self._calculate_fsm_coverage(modules, test_results)
        }

    # Add these methods to the DesignVerifier class

    def _calculate_line_coverage(self, modules: List[Dict], test_results: List[Dict]) -> float:
        """Calculate line coverage percentage"""
        try:
            total_lines = 0
            covered_lines = 0
            
            for module in modules:
                # Get all executable lines
                lines = self._get_executable_lines(module['body'])
                total_lines += len(lines)
                
                # Check which lines were covered by tests
                covered = set()
                for result in test_results:
                    if result.get('coverage', {}).get('lines'):
                        covered.update(result['coverage']['lines'])
                
                covered_lines += len(covered)
            
            return round((covered_lines / total_lines * 100) if total_lines > 0 else 0, 2)
        
        except Exception as e:
            if self.verbose:
                print(f"Error calculating line coverage: {str(e)}")
            return 0.0

    def _calculate_branch_coverage(self, modules: List[Dict], test_results: List[Dict]) -> float:
        """Calculate branch coverage percentage"""
        try:
            total_branches = 0
            covered_branches = 0
            
            for module in modules:
                # Get all branches (if/else, case statements)
                branches = self._get_branches(module['body'])
                total_branches += len(branches)
                
                # Check which branches were covered by tests
                covered = set()
                for result in test_results:
                    if result.get('coverage', {}).get('branches'):
                        covered.update(result['coverage']['branches'])
                
                covered_branches += len(covered)
            
            return round((covered_branches / total_branches * 100) if total_branches > 0 else 0, 2)
        
        except Exception as e:
            if self.verbose:
                print(f"Error calculating branch coverage: {str(e)}")
            return 0.0

    def _calculate_fsm_coverage(self, modules: List[Dict], test_results: List[Dict]) -> float:
        """Calculate FSM state/transition coverage percentage"""
        try:
            total_states = 0
            total_transitions = 0
            covered_states = set()
            covered_transitions = set()
            
            for module in modules:
                # Extract FSM information
                states, transitions = self._extract_fsm_info(module['body'])
                total_states += len(states)
                total_transitions += len(transitions)
                
                # Check coverage from test results
                for result in test_results:
                    if result.get('coverage', {}).get('fsm'):
                        fsm_coverage = result['coverage']['fsm']
                        covered_states.update(fsm_coverage.get('states', []))
                        covered_transitions.update(fsm_coverage.get('transitions', []))
            
            # Calculate combined FSM coverage
            state_coverage = len(covered_states) / total_states if total_states > 0 else 0
            trans_coverage = len(covered_transitions) / total_transitions if total_transitions > 0 else 0
            
            # Weight state and transition coverage equally
            return round(((state_coverage + trans_coverage) / 2 * 100), 2)
        
        except Exception as e:
            if self.verbose:
                print(f"Error calculating FSM coverage: {str(e)}")
            return 0.0

    def _get_executable_lines(self, rtl_body: str) -> Set[int]:
        """Extract executable lines from RTL"""
        lines = set()
        line_num = 0
        
        # Remove comments
        rtl_clean = re.sub(r'//.*$', '', rtl_body, flags=re.MULTILINE)
        rtl_clean = re.sub(r'/\*.*?\*/', '', rtl_clean, flags=re.DOTALL)
        
        for line in rtl_clean.split('\n'):
            line_num += 1
            line = line.strip()
            
            # Skip empty lines and pure structural lines
            if not line or line in {'begin', 'end', 'endmodule', 'endcase'}:
                continue
                
            # Include lines with actual logic
            if any(keyword in line for keyword in [
                'assign', '<=', '=', 'if', 'else', 'case', 'default'
            ]):
                lines.add(line_num)
            
        return lines

    def _get_branches(self, rtl_body: str) -> List[Dict]:
        """Extract branch information from RTL"""
        branches = []
        
        # Find if/else branches
        if_pattern = r'if\s*\((.*?)\)(.*?)(?:else(.*?))?(?=(?:if|end|else|endmodule))'
        for match in re.finditer(if_pattern, rtl_body, re.DOTALL):
            condition = match.group(1)
            true_branch = match.group(2)
            false_branch = match.group(3)
            
            branches.append({
                'type': 'if',
                'condition': condition,
                'true_branch': true_branch,
                'false_branch': false_branch
            })
        
        # Find case branches
        case_pattern = r'case\s*\((.*?)\)(.*?)endcase'
        for match in re.finditer(case_pattern, rtl_body, re.DOTALL):
            expression = match.group(1)
            cases = match.group(2)
            
            # Parse individual case items
            case_items = re.finditer(r'(\w+)\s*:(.*?)(?=\w+\s*:|endcase)', cases, re.DOTALL)
            
            branches.append({
                'type': 'case',
                'expression': expression,
                'items': [{'value': m.group(1), 'code': m.group(2)} for m in case_items]
            })
        
        return branches

    def _extract_fsm_info(self, rtl_body: str) -> Tuple[Set[str], Set[Tuple[str, str, str]]]:
        """Extract FSM states and transitions"""
        states = set()
        transitions = set()
        
        # Look for state type definition
        state_pattern = r'typedef\s+enum\s*.*?\{(.*?)\}'
        state_match = re.search(state_pattern, rtl_body, re.DOTALL)
        if state_match:
            # Extract states from enum
            for state in re.finditer(r'\b(\w+)\b', state_match.group(1)):
                states.add(state.group(1))
        
        # Look for state transitions in case statements
        case_pattern = r'case\s*\(\s*current_state\s*\)(.*?)endcase'
        case_match = re.search(case_pattern, rtl_body, re.DOTALL)
        if case_match:
            case_body = case_match.group(1)
            
            # Find transitions
            for state in states:
                # Fix: Use raw string for state pattern
                state_pattern = fr'{state}\s*:(.*?)(?={"|".join(states)}|endcase)'
                state_match = re.search(state_pattern, case_body, re.DOTALL)
                if state_match:
                    # Find next state assignments
                    next_state_pattern = r'next_state\s*=\s*(\w+)'
                    for match in re.finditer(next_state_pattern, state_match.group(1)):
                        next_state = match.group(1)
                        if next_state in states:
                            transitions.add((state, next_state, ''))
        
        return states, transitions

    def _analyze_assertions(self, assertions: List[Assertion]) -> List[Dict]:
        """Analyze assertion results from simulation"""
        results = []
        
        for assertion in assertions:
            try:
                # Initialize result
                result = {
                    'name': assertion.name,
                    'passed': True,
                    'failure_point': None,
                    'severity': assertion.severity
                }
                
                # Parse assertion condition
                timing_match = re.match(r'@\((.*?)\)\s*(.*)', assertion.condition)
                if timing_match:
                    timing = timing_match.group(1)
                    condition = timing_match.group(2)
                    
                    # Check if this is an implication (|=>)
                    if '|=>' in condition:
                        antecedent, consequent = condition.split('|=>')
                        result['type'] = 'implication'
                        result['antecedent'] = antecedent.strip()
                        result['consequent'] = consequent.strip()
                    else:
                        result['type'] = 'simple'
                        result['condition'] = condition.strip()
                    
                    result['timing'] = timing.strip()
                else:
                    # Simple boolean condition
                    result['type'] = 'simple'
                    result['condition'] = assertion.condition
                
                # Add to results
                results.append(result)
                
            except Exception as e:
                # If assertion analysis fails, mark it as failed
                results.append({
                    'name': assertion.name,
                    'passed': False,
                    'failure_point': str(e),
                    'severity': assertion.severity
                })
        
        return results

    def _check_assertion(self, assertion: Assertion, sim_results: Dict) -> bool:
        """Check if an assertion passed during simulation"""
        try:
            # Parse assertion condition
            timing_match = re.match(r'@\((.*?)\)\s*(.*)', assertion.condition)
            if not timing_match:
                return True  # Skip assertions without timing
            
            timing = timing_match.group(1)
            condition = timing_match.group(2)
            
            # Check timing points
            for time_point in sim_results.get('timing', []):
                if time_point.get('type') == 'clock' and time_point.get('edge') in timing:
                    # Evaluate condition at this time point
                    if not self._evaluate_condition(condition, time_point, sim_results):
                        return False
            
            return True
            
        except Exception as e:
            if self.verbose:
                print(f"Assertion check error: {str(e)}")
            return False

    def _evaluate_condition(self, condition: str, time_point: Dict, sim_results: Dict) -> bool:
        """Evaluate a condition at a specific time point"""
        try:
            # Handle implications (|=>)
            if '|=>' in condition:
                antecedent, consequent = condition.split('|=>')
                if self._evaluate_simple_condition(antecedent.strip(), time_point, sim_results):
                    # Check consequent at next time point
                    next_time = time_point['time'] + 1
                    next_point = next((t for t in sim_results['timing'] if t['time'] == next_time), None)
                    if next_point:
                        return self._evaluate_simple_condition(consequent.strip(), next_point, sim_results)
                return True  # If antecedent is false, implication is true
            
            # Simple condition
            return self._evaluate_simple_condition(condition, time_point, sim_results)
            
        except Exception as e:
            if self.verbose:
                print(f"Condition evaluation error: {str(e)}")
            return False

    def _evaluate_simple_condition(self, condition: str, time_point: Dict, sim_results: Dict) -> bool:
        """Evaluate a simple boolean condition"""
        try:
            # Replace signal names with their values
            for signal, value in sim_results.get('outputs', {}).items():
                condition = condition.replace(signal, str(value))
            
            # Handle $past() function
            past_pattern = r'\$past\((.*?)\)'
            for match in re.finditer(past_pattern, condition):
                signal = match.group(1)
                prev_time = time_point['time'] - 1
                prev_point = next((t for t in sim_results['timing'] 
                                if t['time'] == prev_time and t['signal'] == signal), None)
                if prev_point:
                    condition = condition.replace(match.group(0), str(prev_point['value']))
            
            # Evaluate the condition
            return eval(condition, {"__builtins__": {}}, {})  # Restricted eval
            
        except Exception as e:
            if self.verbose:
                print(f"Simple condition evaluation error: {str(e)}")
            return False

    def _extract_signals(self, rtl_body: str) -> Dict[str, Set[str]]:
        """Extract all signals from module body"""
        signals = {
            'wires': set(),
            'regs': set(),
            'params': set(),
            'constants': set()
        }
        
        # Remove comments
        rtl_clean = re.sub(r'//.*$', '', rtl_body, flags=re.MULTILINE)
        rtl_clean = re.sub(r'/\*.*?\*/', '', rtl_clean, flags=re.DOTALL)
        
        # Find wire declarations
        wire_pattern = r'wire\s+(?:\[.*?\])?\s*(\w+)'
        signals['wires'].update(re.findall(wire_pattern, rtl_clean))
        
        # Find reg declarations
        reg_pattern = r'reg\s+(?:\[.*?\])?\s*(\w+)'
        signals['regs'].update(re.findall(reg_pattern, rtl_clean))
        
        # Find parameters
        param_pattern = r'parameter\s+(\w+)'
        signals['params'].update(re.findall(param_pattern, rtl_clean))
        
        # Find localparams
        localparam_pattern = r'localparam\s+(\w+)'
        signals['constants'].update(re.findall(localparam_pattern, rtl_clean))
        
        return signals

    def _load_test_cases(self, test_dir: str) -> List[TestCase]:
        """Load directed test cases from test directory"""
        test_cases = []
        
        try:
            # Look for .sv or .v test files
            for file in os.listdir(test_dir):
                if not file.endswith(('.sv', '.v')):
                    continue
                    
                with open(os.path.join(test_dir, file), 'r') as f:
                    content = f.read()
                    
                # Parse test case
                test_name = os.path.splitext(file)[0]
                
                # Extract input values
                input_pattern = r'//\s*inputs:\s*{(.*?)}'
                input_match = re.search(input_pattern, content, re.DOTALL)
                inputs = {}
                if input_match:
                    input_str = input_match.group(1)
                    for pair in input_str.split(','):
                        if ':' in pair:
                            name, value = pair.split(':')
                            inputs[name.strip()] = int(value.strip())
                            
                # Extract expected outputs
                output_pattern = r'//\s*outputs:\s*{(.*?)}'
                output_match = re.search(output_pattern, content, re.DOTALL)
                expected = {}
                if output_match:
                    output_str = output_match.group(1)
                    for pair in output_str.split(','):
                        if ':' in pair:
                            name, value = pair.split(':')
                            expected[name.strip()] = int(value.strip())
                            
                # Extract description
                desc_pattern = r'//\s*description:\s*(.*?)(?:\n|$)'
                desc_match = re.search(desc_pattern, content)
                description = desc_match.group(1) if desc_match else ""
                
                test_cases.append(TestCase(
                    name=test_name,
                    type=TestType.DIRECTED,
                    inputs=inputs,
                    expected=expected,
                    description=description
                ))
                
        except Exception as e:
            if self.verbose:
                print(f"Error loading test cases: {str(e)}")
            
        return test_cases

    def _parse_statements(self, body: str) -> List[Dict]:
        """Parse SystemVerilog statements from block body"""
        statements = []
        
        # Clean up body
        body = re.sub(r'\s+', ' ', body.strip())
        
        # Split into statements (handling begin/end blocks)
        current_pos = 0
        in_block = 0
        statement_start = 0
        
        while current_pos < len(body):
            if body[current_pos:].startswith('begin'):
                in_block += 1
                current_pos += 5
            elif body[current_pos:].startswith('end'):
                in_block -= 1
                current_pos += 3
                if in_block == 0:
                    # End of block - parse its contents
                    block_content = body[statement_start:current_pos].strip()
                    if block_content.startswith('begin'):
                        block_content = block_content[5:].strip()
                    if block_content.endswith('end'):
                        block_content = block_content[:-3].strip()
                        
                        # Parse block statements recursively
                        statements.extend(self._parse_statements(block_content))
                        statement_start = current_pos
            elif body[current_pos] == ';' and in_block == 0:
                # End of statement outside block
                stmt = body[statement_start:current_pos].strip()
                if stmt:
                    statements.append(self._parse_single_statement(stmt))
                statement_start = current_pos + 1
                
            current_pos += 1
        
        # Handle any remaining statement
        if statement_start < len(body):
            stmt = body[statement_start:].strip()
            if stmt and not stmt.endswith(('begin', 'end')):
                statements.append(self._parse_single_statement(stmt))
        
        return statements

    def _parse_single_statement(self, stmt: str) -> Dict:
        """Parse a single SystemVerilog statement"""
        stmt = stmt.strip()
        
        # Handle if-else statements
        if stmt.startswith('if'):
            condition_match = re.match(r'if\s*\((.*?)\)(.*?)(?:else(.*?))?$', stmt, re.DOTALL)
            if condition_match:
                return {
                    'type': 'if',
                    'condition': condition_match.group(1).strip(),
                    'true_branch': self._parse_statements(condition_match.group(2).strip()),
                    'false_branch': self._parse_statements(condition_match.group(3).strip()) if condition_match.group(3) else []
                }
        
        # Handle case statements
        elif stmt.startswith('case'):
            case_match = re.match(r'case\s*\((.*?)\)(.*?)endcase', stmt, re.DOTALL)
            if case_match:
                expression = case_match.group(1).strip()
                cases_text = case_match.group(2).strip()
                
                # Parse individual case items
                cases = []
                for case_item in re.finditer(r'(\w+)\s*:(.*?)(?=\w+\s*:|$)', cases_text, re.DOTALL):
                    cases.append({
                        'value': case_item.group(1).strip(),
                        'statements': self._parse_statements(case_item.group(2).strip())
                    })
                
                return {
                    'type': 'case',
                    'expression': expression,
                    'cases': cases
                }
        
        # Handle assignments
        elif '<=' in stmt or '=' in stmt:
            is_nonblocking = '<=' in stmt
            parts = stmt.split('<=' if is_nonblocking else '=', 1)
            return {
                'type': 'nonblocking' if is_nonblocking else 'blocking',
                'target': parts[0].strip(),
                'value': parts[1].strip()
            }
        
        # Handle other statements (e.g., function calls)
        else:
            return {
                'type': 'other',
                'text': stmt
            }

    def _execute_statements(self, statements: List[Dict], state: Dict):
        """Execute a list of statements"""
        for stmt in statements:
            if stmt['type'] == 'if':
                # Evaluate condition
                if self._evaluate_expression(stmt['condition'], state):
                    self._execute_statements(stmt['true_branch'], state)
                elif stmt.get('false_branch'):
                    self._execute_statements(stmt['false_branch'], state)
                
            elif stmt['type'] == 'case':
                # Evaluate case expression
                value = self._evaluate_expression(stmt['expression'], state)
                # Find matching case
                for case in stmt['cases']:
                    if str(value) == case['value'] or case['value'] == 'default':
                        self._execute_statements(case['statements'], state)
                        break
                    
            elif stmt['type'] in ['blocking', 'nonblocking']:
                # Evaluate and assign
                value = self._evaluate_expression(stmt['value'], state)
                if stmt['type'] == 'blocking':
                    state['outputs'][stmt['target']] = value
                else:
                    # Store nonblocking assignments to apply later
                    if 'nonblocking_updates' not in state:
                        state['nonblocking_updates'] = {}
                    state['nonblocking_updates'][stmt['target']] = value
                
            elif stmt['type'] == 'other':
                # Handle other statement types if needed
                pass
            
        # Apply nonblocking updates after all statements
        if 'nonblocking_updates' in state:
            for target, value in state['nonblocking_updates'].items():
                state['outputs'][target] = value
            del state['nonblocking_updates']

    def _calculate_coverage_from_vcd(self, vcd_data: Dict) -> Dict:
        """Calculate coverage metrics from VCD data"""
        coverage = {
            'line': 0,
            'branch': 0,
            'fsm': 0,
            'toggle': 0
        }
        
        try:
            if not vcd_data:
                return coverage
                
            # Calculate toggle coverage
            total_toggles = 0
            possible_toggles = 0
            
            for signal_id, signal_info in vcd_data.items():
                values = signal_info['values']
                if len(values) > 1:
                    toggles = 0
                    prev_value = values[0][1]
                    for _, value in values[1:]:
                        if value != prev_value:
                            toggles += 1
                        prev_value = value
                        
                    total_toggles += toggles
                    possible_toggles += signal_info['width'] * 2  # Each bit can toggle both ways
                    
            if possible_toggles > 0:
                coverage['toggle'] = (total_toggles / possible_toggles) * 100
                
            # Estimate FSM coverage from state signal
            state_signals = [s for s in vcd_data.values() if 'state' in s['name'].lower()]
            if state_signals:
                state_signal = state_signals[0]
                unique_states = len(set(value for _, value in state_signal['values']))
                # Assume 8 possible states as typical FSM size
                coverage['fsm'] = (unique_states / 8) * 100
                
            # Estimate line coverage from signal activity
            active_signals = len([s for s in vcd_data.values() if len(s['values']) > 1])
            total_signals = len(vcd_data)
            if total_signals > 0:
                coverage['line'] = (active_signals / total_signals) * 100
                
            # Estimate branch coverage from conditional signals
            cond_signals = [s for s in vcd_data.values() if any(x in s['name'].lower() for x in ['sel', 'en', 'valid'])]
            if cond_signals:
                branches_taken = 0
                total_branches = 0
                for signal in cond_signals:
                    values = set(value for _, value in signal['values'])
                    branches_taken += len(values)
                    total_branches += 2  # Assume binary conditions
                    
                coverage['branch'] = (branches_taken / total_branches) * 100
                
        except Exception as e:
            if self.verbose:
                print(f"Error calculating coverage: {str(e)}")
                
        return coverage

    def _get_cached_module_info(self) -> Dict:
        """Get or create cached module info"""
        if not hasattr(self, '_cached_module_info'):
            # Parse module name
            module_match = re.search(r'module\s+(\w+)', self.rtl)
            if not module_match:
                raise ValueError("Could not find module name in RTL")
            
            # Parse module ports
            modules = self._parse_rtl_modules()
            if not modules:
                raise ValueError("Could not parse module ports")
            
            # Cache the info
            self._cached_module_info = {
                'name': module_match.group(1),
                'ports': modules[0]['ports'],
                'input_ports': [p for p in modules[0]['ports'] if p['direction'] == 'input'],
                'output_ports': [p for p in modules[0]['ports'] if p['direction'] == 'output'],
                'clock_ports': [p for p in modules[0]['ports'] if p['name'].lower() in ['clk', 'clock']],
                'reset_ports': [p for p in modules[0]['ports'] if any(r in p['name'].lower() for r in ['rst', 'reset'])]
            }
            
            if self.verbose:
                print("\nCached module info:")
                print(f"Module name: {self._cached_module_info['name']}")
                print(f"Total ports: {len(self._cached_module_info['ports'])}")
                print(f"Input ports: {len(self._cached_module_info['input_ports'])}")
                print(f"Output ports: {len(self._cached_module_info['output_ports'])}")
                print(f"Clock ports: {len(self._cached_module_info['clock_ports'])}")
                print(f"Reset ports: {len(self._cached_module_info['reset_ports'])}")
        
        return self._cached_module_info

class Diann(Agent):
    def __init__(self, specification: str, solution_folder: str, 
                 problem_name: str = "ProbXXX", verbose: bool = False,
                 gui_callback = None):
        super().__init__(
            system_prompt="You are a digital design project manager coordinating the design process.",
            tools={},
            context="",
            verbose=verbose
        )
        self.specification = specification
        self.solution_folder = solution_folder
        self.output_dir = "outputs"
        self.run_id = problem_name[4:] + "__" + str(int(datetime.datetime.now().timestamp()))
        
        # Create all necessary directories
        self.run_dir = os.path.join(self.output_dir, self.run_id)
        os.makedirs(self.run_dir, exist_ok=True)
        os.makedirs("vpx_outputs", exist_ok=True)  # Create vpx_outputs directory
        
        # Initialize subcomponents with GUI callback
        self.planner = DesignPlanner(specification, verbose, gui_callback)
        self.planner.run_dir = self.run_dir
        self.context = None
        self.coder = None
        self.verifier = None
        self.gui_callback = gui_callback

    def run(self) -> str:
        if self.gui_callback:
            self.gui_callback("Starting Implementation", {
                "message": f"Implementing design for specification:\n{self.specification}"
            })

        # 1. Plan the design
        self.context = self.planner.analyze_requirements()
        
        # 2. Generate RTL
        self.coder = DesignCoder(self.context, self.verbose, self.gui_callback)
        rtl = self.coder.generate_rtl() if self.planner.needs_fsm else self.coder.call_zero_shot()
        
        # Remove markdown code block markers if present
        final_rtl = rtl.replace('```systemverilog\n', '').replace('```', '')
        
        # 3. Save the result
        self.save_rtl(final_rtl)
        
        if self.gui_callback:
            self.gui_callback("Implementation Complete", {
                "status": "Design implementation completed successfully",
                "final_rtl": final_rtl
            })
        
        return final_rtl

    def save_rtl(self, rtl_code: str = None) -> None:             
        if not rtl_code:
            return
            
        # Extract module name
        match = re.search(r'module\s+(\w+)', rtl_code)
        module_name = match.group(1) if match else "TopModule"
            
        # Ensure vpx_outputs directory exists
        os.makedirs("vpx_outputs", exist_ok=True)
            
        # Save to vpx_outputs directory
        output_path = os.path.join("vpx_outputs", f"{module_name}.sv")
        with open(output_path, "w") as f:
            f.write(rtl_code)

    def _parse_ports(self, port_list: str) -> List[Dict]:
        """Parse port declarations into structured format"""
        ports = []
        
        # Split port declarations
        declarations = [d.strip() for d in port_list.split(',') if d.strip()]
        
        for decl in declarations:
            # Parse direction, type, width and name
            parts = decl.strip().split()
            if not parts:
                continue
                
            port = {'direction': '', 'width': 1, 'name': '', 'type': 'wire'}
            
            for part in parts:
                if part in ['input', 'output', 'inout']:
                    port['direction'] = part
                elif part in ['wire', 'reg', 'logic']:
                    port['type'] = part
                elif '[' in part and ']' in part:
                    # Parse vector width
                    width_match = re.search(r'\[(\d+):(\d+)\]', part)
                    if width_match:
                        high = int(width_match.group(1))
                        low = int(width_match.group(2))
                        port['width'] = high - low + 1
                elif not part.startswith('['):
                    # Last non-bracket part is the name
                    port['name'] = part.rstrip(';')
                    
            if port['direction'] and port['name']:
                ports.append(port)
                
        return ports