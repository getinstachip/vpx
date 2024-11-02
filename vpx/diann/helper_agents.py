from dataclasses import dataclass
from typing import Optional
import os
import datetime
import re
from .agent import Agent
from typing import List, Dict, Any, Optional


# Core data structures
@dataclass
class Requirements:
    module_interface: Optional[str] = None
    components: Optional[str] = None
    fsm: Optional[str] = None
    timing: Optional[str] = None

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
    rtl: Optional[str] = None

class DesignPlanner(Agent):
    def __init__(self, specification: str, verbose: bool = False):
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

    def _write_output(self, filename: str, content: str):
        if self.run_dir:
            filepath = os.path.join(self.run_dir, filename)
            with open(filepath, "w") as f:
                f.write(content)

    def _analyze_module_interface(self) -> str:
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
        self._write_output("module_interface.txt", response)
        return self._extract_answer(response)

    def _analyze_components(self) -> str:
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
        self._write_output("components.txt", response)
        return self._extract_answer(response)

    def _analyze_timing_requirements(self) -> str:
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
        self._write_output("timing_prerefined.txt", response)
        return self._extract_answer(response)

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
        return self._extract_answer(response)

    def _analyze_fsm_needs(self) -> str:
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
        return self._extract_answer(response)

    def _analyze_fsm_requirements(self) -> str:
        """Complete FSM analysis including requirements"""
        prompt = f"""<specification>
{self.context.specification}
</specification>

Analyze FSM requirements. Consider:
1. Required states and transitions
2. Input conditions governing transitions
3. Outputs needed in each state
4. Reset behavior and initialization
5. Special timing considerations

Place complete FSM requirements in <answer> tags."""

        response = self.chat(
            user_input=prompt,
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            streaming=True,
            temperature=0.3
        )
        return self._extract_answer(response)

    def _generate_fsm_structure(self, reqs: str) -> str:
        """Generate FSM structure based on requirements"""
        prompt = f"""<requirements>
{reqs}
</requirements>

Generate complete FSM structure including:
1. State enumeration
2. State register declaration
3. Next state logic
4. Output logic
5. Reset handling

Place FSM structure in <answer> tags."""

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
            
        self._write_output("fsm_final.txt", fsm)
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
        self._write_output("output_logic.txt", response)
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
        
        self._write_output("timing_final.txt", verified_timing)
        return verified_timing

    def analyze_requirements(self) -> DesignContext:
        self.context.requirements = Requirements()
        
        interface_response = self._analyze_module_interface()
        self.context.requirements.module_interface = interface_response
        
        components_response = self._analyze_components()
        self.context.requirements.components = components_response
        
        timing_response = self.analyze_timing()
        self.context.requirements.timing = timing_response
        
        fsm_needs_response = self._analyze_fsm_needs()
        if "FSM NEEDED: YES" in fsm_needs_response:
            self.needs_fsm = True
            fsm_response = self._analyze_fsm()
            self.context.requirements.fsm = fsm_response
        
        combined = "\n\n".join([
            self.self.context.requirements.module_interface,
            self.context.requirements.components,
            self.context.requirements.timing,
            self.context.requirements.fsm or ""
        ])
            
        self._write_output("requirements.txt", combined)
        return self.context

    def _extract_answer(self, response: str) -> str:
        start = response.find("<answer>")
        end = response.find("</answer>")
        if start != -1 and end != -1:
            return response[start + 8:end].strip()
        return response

class DesignCoder(Agent):
    def __init__(self, context: DesignContext, verbose: bool = False):
        super().__init__(
            system_prompt="You are a digital design engineer specializing in RTL code generation.",
            tools={},
            context="",
            verbose=verbose
        )
        self.context = context

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
  ```verilog
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
        prompt = f"""<specification>
{self.context.specification}
</specification>

<module_interface>
{self.context.requirements.module_interface}
</module_interface>

<components>
{self.context.requirements.components}
</components>

{f'''<fsm>
{self.context.fsm_plan.state_info}
{self.context.fsm_plan.output_logic}
</fsm>''' if self.context.fsm_plan else ''}

Think through each step carefully before implementing:

1. First analyze declarations:
  Read <module_interface> and <components> carefully.
  - What ports are needed and why?
  - What storage elements are needed and why?
  - What signal types & widths are needed and why?
  - What local signals might help and why?

2. Then plan sequential logic:
{'''  Study <fsm> state transitions and updates.
  - How should state register update?
  - When do storage elements update?
  - What happens on reset?
  - What is the update order?''' if self.context.fsm_plan else '''  Study storage element behavior.
  - When do storage elements update?
  - What happens on reset?
  - What is the update order?'''}

3. Next determine combinational logic:
{'''  Look at <fsm> outputs and conditions.
  - How is next state computed?
  - How are outputs generated?
  - What intermediate signals help?
  - Are defaults needed?''' if self.context.fsm_plan else '''  Study output generation.
  - How are outputs computed?
  - What intermediate signals help?
  - Are defaults needed?'''}

4. Finally consider synthesis:
  Review complete design choices.
  - Will logic synthesize cleanly?
  - Are there timing concerns?
  - Can code be optimized?
  - Would parameters help?

For each step above:
1. Think about requirements
2. Consider alternatives
3. Choose optimal approach 
4. Verify completeness

Document your step-by-step reasoning in <thinking> tags.
Then provide ONLY the complete SystemVerilog RTL in <answer> tags.
<answer> should contain properly organized synthesizable code with no additional text or explanations."""

        response = self.chat(
            user_input=prompt,
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            streaming=True,
            temperature=0.3
        )
        self.context.rtl = self._extract_answer(response)
        return self.context.rtl

    def _extract_answer(self, response: str) -> str:
        start = response.find("<answer>")
        end = response.find("</answer>")
        if start != -1 and end != -1:
            return response[start + 8:end].strip()
        return response

class DesignVerifier(Agent):
    def __init__(self, context: DesignContext, verbose: bool = False):
        super().__init__(
            system_prompt="You are a digital design verification engineer specializing in timing analysis and verification.",
            tools={},
            context="",
            verbose=verbose
        )
        self.context = context

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

class Diann(Agent):
    def __init__(self, specification: str, solution_folder: str, problem_name: str = "ProbXXX", verbose: bool = False):
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
        self.run_dir = os.path.join(self.output_dir, self.run_id)
        os.makedirs(self.run_dir, exist_ok=True)
        
        # Initialize subcomponents
        self.planner = DesignPlanner(specification, verbose)
        self.planner.run_dir = self.run_dir
        self.context = None
        self.coder = None
        self.verifier = None

    def run(self) -> str:
        # 1. Plan the design
        self.context = self.planner.analyze_requirements()
        
        # 2. Generate RTL
        self.coder = DesignCoder(self.context, self.verbose)
        rtl = self.coder.generate_rtl() if self.planner.needs_fsm else self.coder.call_zero_shot()
        self._write_output("rtl_preverified.sv", rtl)
        
        # 3. Verify the design
        self.verifier = DesignVerifier(self.context, self.verbose)
        final_rtl = self.verifier.verify_rtl_timing()
        
        # 4. Save the result
        self.save_rtl(final_rtl)
        return final_rtl

    def save_rtl(self, rtl: str) -> None:
        # Extract timing diagram for comments if available
        timing_comment = ""
        if self.context.timing_plan and self.context.timing_plan.cycle_diagram:
            timing_comment = f"// Timing Diagram:\n//{self.context.timing_plan.cycle_diagram.replace('\n', '\n//')}\n"
        
        # Clean up the RTL code
        rtl_code = rtl.strip()
        rtl_code = re.sub(r'^```\w*\n', '', rtl_code)
        rtl_code = re.sub(r'\n```$', '', rtl_code)
        
        # Save with timing comments
        os.makedirs("rtl", exist_ok=True)
        with open(os.path.join(self.solution_folder, "TopModule.sv"), "w") as f:
            f.write(timing_comment + rtl_code)

    def _write_output(self, filename: str, content: str) -> None:
        filepath = os.path.join(self.run_dir, filename)
        with open(filepath, "w") as f:
            f.write(content)

    def _extract_answer(self, response: str) -> str:
        start = response.find("<answer>")
        end = response.find("</answer>")
        if start != -1 and end != -1:
            return response[start + 8:end].strip()
        return response

    def save_rtl(self) -> None:
        with open(os.path.join(self.run_dir, "rtl.sv"), "r") as f:
            rtl_content = f.read()
            
        match = re.search(r'<answer>(.*?)</answer>', rtl_content, re.DOTALL)
        if match:
            rtl_code = match.group(1).strip()
            rtl_code = re.sub(r'^```\w*\n', '', rtl_code)
            rtl_code = re.sub(r'\n```$', '', rtl_code)
         
        if self.context.timing_plan and self.context.timing_plan.cycle_diagram:
            timing_comment = f"// Timing Diagram:\n//{self.context.timing_plan.cycle_diagram.replace('\n', '\n//')}\n"
            rtl_code = timing_comment + rtl_code
             
        os.makedirs("rtl", exist_ok=True)
        with open(os.path.join(self.solution_folder, "TopModule.sv"), "w") as f:
            f.write(rtl_code)
            
        
class WiringAgent(Agent):
    def __init__(self, module_a: Dict[str, Any], module_b: Dict[str, Any], context: str = "", verbose: bool = False):
        super().__init__(
            system_prompt="You are an expert at gluing SystemVerilog modules together.",
            tools={},
            context=context,
            verbose=verbose
        )
        self.module_a = module_a
        self.module_b = module_b

    def wire_modules(self, module_a: Dict[str, Any], module_b: Dict[str, Any]):
        prompt = read_prompt("wire_modules.txt").format(
            module_a=module_a,
            module_b=module_b
        )
        return self.chat(prompt, provider="anthropic", model="claude-3-5-sonnet-20241022")
    

class StandardizationAgent(Agent):
    def __init__(self, module: Dict[str, Any], context: str = "", verbose: bool = False):
        super().__init__(
            system_prompt="You are an expert at refactoring SystemVerilog module hierarchies to be consistent and standardized.",
            tools={},
            context=context,
            verbose=verbose
        )
        self.module = module


class DocumentationAgent(Agent):
    def __init__(self, module: Dict[str, Any], context: str = "", verbose: bool = False):
        super().__init__(
            system_prompt="You are an expert at documenting SystemVerilog module hierarchies.",
            tools={
                # "state_machine_extractor": StateMachineExtractor(module["code"])
            },
            context=context,
            verbose=verbose
        )
        self.module = module
    
    def document_module(self, module: Dict[str, Any]):
        prompt = read_prompt("document_module.txt").format(module=module)
        return self.chat(prompt, provider="openai", model="o1-mini")
    
    def document_state_machine(self, module: Dict[str, Any]):
        state_machine = self.tools["state_machine_extractor"].extract_state_machine(module["code"])
        return state_machine


class DebuggerAgent(Agent):
    def __init__(self, module: Dict[str, Any], context: str = "", verbose: bool = False):
        super().__init__(
            system_prompt="You are an expert at debugging SystemVerilog module hierarchies.",
            tools={ "iverilog": IcarusVerilog() },
            context=context,
            verbose=verbose
        )
        self.module = module

    def timing_diagram(self, module: Dict[str, Any]):
        prompt = read_prompt("timing_diagram.txt").format(
            module=module,
            wavedrom_example=json.loads(open("examples/wavedrom.json").read())
        )
        wavedrom_json = self.chat(prompt, json_response=True, provider="openai", model="o1-mini")
        # Read the wavedrom_json and display graphically using wavedrom
        try:
            svg = wavedrom.render(wavedrom_json)
            svg.savefig(f"generated_rtl/{module['name']}_timing_diagram.svg")
            print(f"Timing diagram saved as generated_rtl/{module['name']}_timing_diagram.svg")
        except ImportError:
            print("Warning: wavedrom package not installed. Unable to generate graphical timing diagram.")
            print("Returning the JSON representation of the timing diagram instead.")
        return wavedrom_json
    
    def _update_module_in_hierarchy(self, hierarchy, module_to_update):
        """
        Update the specific module in the implemented hierarchy with the new information.
        """
        if hierarchy['instance_name'] == module_to_update['instance_name']:
            hierarchy.update(module_to_update)
        else:
            for submodule in hierarchy.get('submodules', []):
                self._update_module_in_hierarchy(submodule, module_to_update)

    def write_testbench(self, module: Dict[str, Any]):
        pass

    def _fix_module__compile_errors(self, module: Dict[str, Any], error: Dict[str, Any]):
        error_type = error.get("type", "Unknown")

        # Prepare submodule information
        submodules_info = []
        for submodule in module.get("submodules", []):
            submodule_info = {
                "name": submodule.get("name", "Unnamed"),
                "ports": submodule.get("ports", [])
            }
            submodules_info.append(submodule_info)

        # Construct module information
        module_info = {
            "name": module.get("name", "Unnamed Module"),
            "ports": module.get("ports", []),
            "submodules": submodules_info,
            "connections": module.get("connections", []),
            "systemverilog_code": module.get("code", "")
        }

        prompt = read_prompt("fix_module__compile_errors.txt").format(
            module_info=json.dumps(module_info, indent=2),
            error=error if error_type != "Unknown" else error["message"]
        )

        fixed_module_code = self.chat(prompt, provider="anthropic", model="claude-3-5-sonnet-20241022")
        module["code"] = fixed_module_code

        with open("states/module_hierarchy.json", "r+") as f:
            module_hierarchy = json.load(f)
            # self._update_module_in_hierarchy(module_hierarchy, module)
            f.seek(0)
            json.dump(module_hierarchy, f, indent=2)
            f.truncate()

        return fixed_module_code

    def _fix_module__sim_errors(self, module: Dict[str, Any]):
        pass

    def _debug_compilation_errors(self, module: Dict[str, Any]):
        print("Debugging compilation errors for module: ", module.get('name', 'Unnamed Module'))
        output, passed = self.tools["iverilog"].compile_files(
            f"generated_rtl/{module['name']}",
            [f"generated_rtl/{module['name']}.sv"] + 
            [f"generated_rtl/{submodule['name']}.sv" for submodule in module.get("submodules", [])]
        )

        if passed:
            return True
        
        compile_errors = self.tools["iverilog"].get_compile_errors()

        for error in compile_errors:
            print(f"Fixing compile-time error: {error}")
            module["code"] = self._fix_module__compile_errors(module, error)

        output, passed = self.tools["iverilog"].compile_files(
            f"generated_rtl/{module['name']}",
            [f"generated_rtl/{module['name']}.sv"] + 
            [f"generated_rtl/{submodule['name']}.sv" for submodule in module.get("submodules", [])]
        )

        return passed

    def _debug_simulation_errors(self, module: Dict[str, Any]):
        pass

    def fix_module(self, module, test_compile: bool = False, test_sim: bool = False):
        """
        Test a module for compilation and simulation errors.
        """
        print("Fixing module: ", module.get('name', 'Unnamed Module'))
        module_name = module.get('name', 'Unnamed Module')
        if test_compile:
            print("Testing compilation errors for module: ", module_name)
            passed_compilation = self._debug_compilation_errors(module)
            if not passed_compilation:
                raise Exception(f"{module_name} failed compilation due to a fundamental error.")

            # if test_sim:
            #     passed_simulation = self._debug_simulation_errors(module['code'])
            #     if not passed_simulation:
            #         raise Exception(f"{module_name} failed simulation.")

            print(f"{module_name} passed all tests")
        else:
            print(f"{module_name} skipped testing")