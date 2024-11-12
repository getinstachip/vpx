from typing import List, Dict, Any, Callable, Union
from openai import OpenAI
import anthropic
import json
from .utility import strip_code_tags, add_braces
from .tools import Tool, CircuitVisualizer
import xml.etree.ElementTree as ET
from io import StringIO
from dotenv import load_dotenv
from vpx.secretload import get_openai_key, get_anthropic_key

class Agent:
    def __init__(self, system_prompt: str = "", tools: Dict[str, Tool] = {}, context: str = "", verbose: bool = False, log_history: bool = False):
        try:
            self.openai_client = OpenAI(api_key=get_openai_key())
            self.anthropic_client = anthropic.Anthropic(api_key=get_anthropic_key())
        except Exception as e:
            raise ValueError(f"Failed to initialize API clients: {str(e)}")
        
        self.system_prompt = system_prompt
        self.tools = tools
        self.context = context
        self.messages = []
        self.verbose = verbose
        self.log_history = log_history
        self.function_map: Dict[str, Callable] = {}
        self.condition_map: Dict[str, Callable] = {}
        self.property_map__self: Dict[str, Callable] = {}
        self._initialize_messages()
        self._initialize_tools()
        # if self.verbose:
            # print(f"System Prompt:\n{self.system_prompt}")

    def _initialize_tools(self):
        for tool in self.tools.values():
            self._add_message("user", f"You have expertise in: {tool.name} - {tool.description}")

    def _initialize_messages(self):
        self.messages = []
        if self.context:
            self.messages.append({"role": "user", "content": self.context})

    def _add_message(self, role: str, content: str):
        if self.log_history:
            self.messages.append({"role": role, "content": content})
        # if self.verbose:
            # self._print_message(role, content)

    def _print_message(self, role: str, content: str):
        print("-" * 80)
        print(f"{role.capitalize()}:\n{content}")
        print("-" * 80)

    def _get_response(
        self,
        temperature: float = 0.7,
        provider: str = "openai",
        model: str = "o1-mini",
        message: Dict[str, str] = None,
        k: int = 1,
        streaming: bool = False,
        xml_tag: str = None,
        prefill: List[Dict[str, str]] = None
    ) -> Union[str, List[str]]:
        if provider == "openai":
            return self._get_openai_response(temperature, model, message, k)
        elif provider == "anthropic":
            return self._get_anthropic_response(temperature, model, message, k, streaming, xml_tag, prefill)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def _get_openai_response(self, temperature: float, model: str, message: Dict[str, str], k: int) -> Union[str, List[str]]:
        response = self.openai_client.chat.completions.create(
            model=model,
            messages=[message] if message else (self.messages if self.log_history else [self.messages[-1]]),
            temperature=temperature,
            n=k
        )
        return response.choices[0].message.content if k == 1 else [choice.message.content for choice in response.choices]

    def _get_anthropic_response(self, temperature: float, model: str, message: Dict[str, str], k: int, streaming: bool, xml_tag: str = None, prefill: List[Dict[str, str]] = None) -> Union[str, List[str]]:
        base_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in ([message] if message else (self.messages if self.log_history else [self.messages[-1]]))
        ]
        
        # If prefill is provided, create a new conversation with Claude using prefill messages
        if prefill:
            prefill_response = self.anthropic_client.messages.create(
                model=model,
                messages=prefill,
                system=self.system_prompt,
                temperature=temperature,
                max_tokens=8192
            )
            # Add the prefilled context to the base messages
            base_messages = prefill + base_messages
            
        if k == 1:
            if streaming:
                return self._get_anthropic_streaming_response(model, base_messages, temperature, xml_tag)
            else:
                response = self.anthropic_client.messages.create(
                    model=model,
                    messages=base_messages,
                    system=self.system_prompt,
                    temperature=temperature,
                    max_tokens=8192
                )
                return response.content[0].text
        
        responses = []
        for _ in range(k):
            response = self.anthropic_client.messages.create(
                model=model,
                messages=base_messages,
                system=self.system_prompt,
                temperature=temperature,
                max_tokens=8192
            )
            responses.append(response.content[0].text)
        return responses

    def _get_anthropic_streaming_response(self, model: str, messages: List[Dict[str, str]], temperature: float, xml_tag: str = None) -> str:
        if xml_tag:
            buffer = StringIO()
            
        with self.anthropic_client.messages.stream(
            model=model,
            messages=messages,
            system=self.system_prompt,
            temperature=temperature,
            max_tokens=8192
        ) as stream:
            response = ""
            for text in stream.text_stream:
                response += text
                
                # Process XML tags only if xml_tag is specified
                if xml_tag:
                    buffer.write(text)
                    current_text = buffer.getvalue()
                    
                    # Look for complete XML tags
                    start_tag = f"<{xml_tag}>"
                    end_tag = f"</{xml_tag}>"
                    
                    while True:
                        start = current_text.find(start_tag)
                        if start == -1:
                            break
                            
                        end = current_text.find(end_tag, start)
                        if end == -1:
                            break
                            
                        # Extract the complete XML fragment
                        end += len(end_tag)
                        xml_fragment = current_text[start:end]
                        
                        try:
                            # Validate the XML fragment
                            ET.fromstring(xml_fragment)
                            
                            # Write valid XML fragment to file
                            with open('extracted_tags.xml', 'a') as f:
                                f.write(xml_fragment + '\n')

                            circuit_diagram_tool = CircuitVisualizer("")
                            circuit_diagram_tool.render_diagram(xml_fragment)
                                
                            # Remove processed fragment from buffer
                            current_text = current_text[end:]
                            buffer = StringIO(current_text)
                        except ET.ParseError:
                            # If parsing fails, move past the start tag
                            current_text = current_text[start + len(start_tag):]
                            buffer = StringIO(current_text)
                
                # Original output handling
                print(text, end="", flush=True)
                if self.output_file:
                    with open(self.output_file, 'a') as f:
                        f.write(text)
                        
            print()
            return response
    
    def chat(
        self,
        user_input: str,
        provider: str = "openai",
        model: str = "o1-mini",
        temperature: float = 1.0,
    ) -> str:
        """Simple chat interface that returns a string response"""
        try:
            if provider == "openai":
                response = self.openai_client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": user_input}],
                    temperature=temperature
                )
                return response.choices[0].message.content
                
            elif provider == "anthropic":
                response = self.anthropic_client.messages.create(
                    model=model,
                    messages=[{"role": "user", "content": user_input}],
                    temperature=temperature,
                    max_tokens=8192
                )
                return response.content[0].text
                
            else:
                raise ValueError(f"Unsupported provider: {provider}")
                
        except Exception as e:
            if self.verbose:
                print(f"Error in chat: {str(e)}")
            return ""

    def _process_single_response(self, response: str, json_response: bool, xml_response: bool, output_file: str) -> str:
        cleaned_response = self._clean_response(response, json_response)
        self._add_message("assistant", cleaned_response)
        if json_response or xml_response:
            return self._process_structured_response(cleaned_response, json_response, xml_response, output_file)
        else:
            if output_file and not self.output_file:  # Only write if not already written during streaming
                with open(output_file, 'w') as f:
                    f.write(cleaned_response)
            return cleaned_response

    def _process_multiple_responses(self, responses: List[str], json_response: bool, xml_response: bool, output_file: str) -> List[str]:
        cleaned_responses = [self._clean_response(r, json_response) for r in responses]
        if json_response or xml_response:
            return [self._process_structured_response(r, json_response, xml_response, None) for r in cleaned_responses]
        else:
            if output_file:
                with open(output_file, 'w') as f:
                    f.write("\n".join(cleaned_responses))
            return cleaned_responses

    def _clean_response(self, response: str, is_json: bool) -> str:
        cleaned = response
        if is_json:
            cleaned = add_braces(cleaned)
            print("Cleaned response:\n", cleaned)
        return cleaned

    def _process_structured_response(self, cleaned_response: str, is_json: bool, is_xml: bool, output_file: str) -> str:
        if is_json:
            return self._process_json_response(cleaned_response, output_file)
        elif is_xml:
            return self._process_xml_response(cleaned_response, output_file)

    def _process_json_response(self, cleaned_response: str, output_file: str) -> str:
        try:
            json_data = json.loads(cleaned_response)
            if output_file:
                with open(output_file, 'w') as f:
                    json.dump(json_data, f, indent=4)
            return json_data
        except json.JSONDecodeError as e:
            error_message = f"Failed to parse JSON response: {str(e)}\nResponse content: {cleaned_response}"
            print(error_message)
            raise ValueError(error_message)

    def _process_xml_response(self, cleaned_response: str, output_file: str) -> str:
        if output_file:
            with open(output_file, 'w') as f:
                f.write(cleaned_response)
        return cleaned_response

    def reset_conversation(self):
        self._initialize_messages()

    def structure_module_hierarchy(self, input_json: Dict[str, Any], output_schema: Dict[str, Any]) -> Dict[str, Any]:
        schema_str = json.dumps(output_schema, indent=2)
        response = self.openai_client.chat.completions.create(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "user", "content": f"""
                Convert the following JSON to the specified output format. 
                Extract the relevant information and structure it according to the output schema.
                Provide the result as a valid JSON string.

                Input JSON:
                {json.dumps(input_json, indent=2)}

                Output Schema:
                {schema_str}

                Please provide the structured JSON output that conforms to the given schema.
                """}
            ],
            temperature=0,
        )
        
        content = strip_code_tags(response.choices[0].message.content)
        print(content)
        
        try:
            structured_json = json.loads(content)
            return structured_json
        except json.JSONDecodeError:
            return {"error": "Failed to parse the generated JSON"}

    def get_conversation_history(self) -> List[Dict[str, str]]:
        return self.messages if self.log_history else []

    def execute_step(self, step):
        if step["type"] == "action":
            self._execute_action_step(step)
        elif step["type"] == "conditional":
            self._execute_conditional_step(step)

    def _execute_action_step(self, step):
        function_name = step["function"]
        arguments = step.get("arguments", {})
        
        mapped_arguments = self._map_arguments(arguments)
        
        if function_name in self.function_map:
            self._execute_function_with_retry(function_name, mapped_arguments)
        else:
            print(f"Warning: Function '{function_name}' not found in function_map")

    def _map_arguments(self, arguments):
        mapped_arguments = {}
        for key, value in arguments.items():
            if isinstance(value, str) and value.startswith("self."):
                mapped_arguments[key] = self._get_property_value(value)
            else:
                mapped_arguments[key] = value
        return mapped_arguments

    def _get_property_value(self, property_name):
        if property_name in self.property_map__self:
            return self.property_map__self[property_name]
        else:
            print(f"Warning: Property '{property_name}' not found in property_map__self")
            return property_name

    def _execute_function_with_retry(self, function_name, arguments):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return self.function_map[function_name](**arguments)
            except Exception as e:
                self._handle_execution_error(function_name, e, attempt, max_retries)

    def _handle_execution_error(self, function_name, error, attempt, max_retries):
        print(f"Error executing function '{function_name}': {str(error)}")
        if attempt < max_retries - 1:
            print(f"Retrying... (Attempt {attempt + 2}/{max_retries})")
        else:
            print(f"Max retries reached. Function '{function_name}' failed to execute.")

    def _execute_conditional_step(self, step):
        condition = step["condition"]
        if self._check_condition(condition):
            self.execute_steps(step.get("if_true", []))
        else:
            self.execute_steps(step.get("if_false", []))

    def execute_steps(self, steps):
        for step in steps:
            self.execute_step(step)

    def _check_condition(self, condition):
        if condition in self.condition_map:
            print(f"Checking condition: {condition}")
            return self.condition_map[condition]
        else:
            print(f"Warning: Condition '{condition}' not found in condition_map")
            return False

    def run_workflow(self, workflow):
        self.execute_steps(workflow["workflow"]["steps"])