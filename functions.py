from openai import OpenAI
import openai
import matlab.engine
import ast
from PIL import Image
import base64
import glob
import re
import time
import json
# from pydantic import BaseModel, Field
# from doc_agent import simulink_documentation_lookup
# from openai_function_call import openai_function
from openai_models import OpenAIMessage, OpenAIResponse
import os
from chain import Chain
from dotenv import load_dotenv
load_dotenv()

# Set OpenAI API key from environment variable or directly
openai.api_key = os.getenv("OPENAI_API_KEY")

def llm(
        chain: Chain,
        model: str = 'gpt-4o',
        temperature: float = 0.0,
) -> OpenAIResponse:
    client = OpenAI()
    response = client.chat.completions.create(
            model=model,
            messages=chain.serialize(),
            response_format={ "type": "json_object" },
            temperature=temperature,
        ).to_dict()
    

    return OpenAIResponse(
        id=response['id'],
        object=response['object'],
        created=response['created'],
        choices=response['choices'],
        usage=response['usage'],
    )

def checkJson(
        chain: Chain,
        model: str = 'gpt-4o',
        temperature: float = 0.0,
) -> OpenAIResponse:
    client = OpenAI()
    response = client.chat.completions.create(
            model=model,
            messages=chain.serialize(),
            response_format={ "type": "json_object" },
            temperature=temperature,
        ).to_dict()
    

    return OpenAIResponse(
        id=response['id'],
        object=response['object'],
        created=response['created'],
        choices=response['choices'],
        usage=response['usage'],
    )



def delete_existing_files(pattern):
    files = glob.glob(pattern)
    for file in files:
        os.remove(file)
    print(f"Deleted files: {files}")

def call_chatgpt(m_file_content, error_message):
    prompt = f"The following MATLAB script has an error:\n\n{m_file_content}\n\nError: {error_message}\n\nPlease provide only the corrected MATLAB script code without any explanation."
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a MATLAB expert."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.0
    )
    print("content: ")
    print(response.choices[0].message.content)
    
    return response.choices[0].message.content

def call_user_with_image_and_prompt(prompt, image_path):
    from PIL import Image

    # Open and display the image
    img = Image.open(image_path)
    img.show()

    # Ask the user if the image meets the expected conditions based on the given prompt
    user_response = input(f"Does the following image meet the expected conditions based on the given prompt?\nPrompt: {prompt}\nAnswer (yes/no): ")

    user_feedback = ""
    if user_response.lower() == "no":
        user_feedback = input("How is the graph wrong right now? Please provide detailed feedback: ")

    return user_response, user_feedback


# Function to call ChatGPT to fix the script based on user feedback
def call_chatgpt_to_fix_script(script_content, original_prompt, reason, interaction_history):
    interaction_history.append({"role": "user", "content": f"The end goal is to achieve the following: {original_prompt}"})
    interaction_history.append({"role": "user", "content": f"The following MATLAB script has an issue:\n\n{script_content}\n\nReason: {reason}"})
    
    chatgpt_prompt = {
        "role": "user",
        "content": "Please provide the corrected MATLAB script to achieve the end goal, without any additional explanation. Make sure to not change any of the following parameter values and ensure they appear just as they did in the original script: 'open_system', 'save_system', 'OpenAtSimulationStart', 'StopTime', 'SimulationCommand'."
    }
    
    interaction_history.append(chatgpt_prompt)

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=interaction_history,
        temperature=0.0,
    )

    fixed_script = response.choices[0].message.content.strip()
    print("Fixed MATLAB script: ", fixed_script)
    
    interaction_history.append({"role": "assistant", "content": fixed_script})
    return fixed_script

def clean_script_content(script_content):
    # Remove the ```matlab block delimiters if they exist
    script_content = re.sub(r'^```matlab\n', '', script_content)
    script_content = re.sub(r'\n```$', '', script_content)
    
    # Remove any non-ASCII characters
    script_content = re.sub(r'[^\x00-\x7F]+', '', script_content)
    return script_content

def run_simulink_model(eng, model_name: str, scope_blocks: list, prompt: str, script_content: str, interaction_history=None):
    if interaction_history is None:
        interaction_history = []
    
    try:
        # Run the .m file
        eng.eval(f'run("{model_name}.m");', nargout=0)

        print(f".m file '{model_name}.m' executed successfully in MATLAB.")

        # Wait a few seconds for the scope to load
        time.sleep(20)  # Adjust the delay as needed

        # Call the function to interpret the plotted data
        print("Interpreting scope data...")
        for scope in scope_blocks:
            screenshot_path = scope_interpreter(eng, model_name, scope, prompt)
            if not screenshot_path:
                eng.quit()
                return {"answer": "No", "reason": "Scope data does not match prompt."}
            
            # Ask the user to evaluate the screenshot
            user_response, user_feedback = call_user_with_image_and_prompt(prompt, screenshot_path)
            interaction_history.append({"role": "user", "content": f"User response: {user_response}, User feedback: {user_feedback}"})
            if user_response.lower() == "yes":
                print("The graph matches the prompt.")
                # Keep MATLAB session open until the user decides to close it
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("User terminated the session.")
                    eng.quit()
                    return True
            else:
                print("The graph does not match the prompt.")
                print("User feedback on the graph:", user_feedback)
                eng.quit()  # Stop the current MATLAB session

                # Use ChatGPT to fix the script based on user feedback
                fixed_script = call_chatgpt_to_fix_script(script_content, prompt, user_feedback, interaction_history)

                # Clean the fixed script content
                fixed_script = clean_script_content(fixed_script)

                # Save the fixed script
                with open(f'{model_name}.m', 'w') as m_file:
                    m_file.write(fixed_script)

                # Delete existing .slx files
                delete_existing_files(f'{model_name}.slx')

                # Start a new MATLAB session to run the fixed script
                print(fixed_script)
                eng = matlab.engine.start_matlab()

                return run_simulink_model(eng, model_name, scope_blocks, prompt, fixed_script, interaction_history)

        print(f"Captured scope screenshot: {screenshot_path}")

        return {"answer": "No", "reason": "No screenshot captured."}
    except matlab.engine.MatlabExecutionError as matlab_err:
        error_message = str(matlab_err)
        print(f"An error occurred while executing the MATLAB script: {error_message}")
        eng.quit()
        interaction_history.append({"role": "user", "content": f"MATLAB Execution Error: {error_message}"})
        return False
    
def parse_value(value):
    try:
        parsed_value = ast.literal_eval(value)
        if isinstance(parsed_value, list):
            return f"[{' '.join(map(str, parsed_value))}]"
        elif isinstance(parsed_value, (int, float)):
            return str(parsed_value)
        else:
            return str(parsed_value)
    except (ValueError, SyntaxError):
        return value
    
def capture_scope_screenshot(eng, model_name, scope_name):
    screenshot_path = f"{scope_name}.png"
    print(f"Opening scope: {model_name}/{scope_name}")

    # Ensure the scope is open
    eng.open_system(f'{model_name}/{scope_name}', nargout=0)
    print(f"Scope {model_name}/{scope_name} opened")

    # Get the name of the Scope of interest
    scope_name_str = eng.get_param(f'{model_name}/{scope_name}', 'Name')
    print(f"Scope name: {scope_name_str}")

    # Find the Scope (which is really just a figure window)
    hs = eng.findall(eng.groot(), 'Type', 'figure', 'Name', scope_name_str)
    if not hs:
        print("Error: Scope window handle not found")
        return None

    # Create a new target figure
    try:
        scope_position = eng.get(hs, 'Position')
        print(f"Scope position: {scope_position}")
        hf = eng.figure('Position', scope_position, nargout=1)
        print(f"New figure created: {hf}")
    except Exception as e:
        print(f"Error accessing scope position or creating new figure: {e}")
        return None

    # Get the handle to the panel containing the plots
    try:
        hp = eng.findobj(hs, 'Tag', 'VisualizationPanel', nargout=1)
        if not hp:
            print("Error: Visualization panel handle not found")
            return None
        print(f"Found visualization panel handle: {hp}")

        # Copy the panel to the new figure
        eng.copyobj(hp, hf, nargout=0)
        print(f"Copied visualization panel to new figure")

        # Set the InvertHardCopy property to 'off' to preserve colors
        eng.set(hf, 'InvertHardCopy', 'off', nargout=0)
        print(f"InvertHardCopy set to off")

        # Save the new figure as an image
        eng.print(hf, '-dpng', screenshot_path, nargout=0)
        print(f"Screenshot captured: {screenshot_path}")
    except Exception as e:
        print(f"Error during panel handling or saving the figure: {e}")
        return None

    return screenshot_path
    
def scope_interpreter(eng, model_name: str, scope_name: str, prompt: str):
    # Capture the scope screenshot
    scope_screenshot_path = capture_scope_screenshot(eng, model_name, scope_name)
    
    # Check if the result indicates a match
    if scope_screenshot_path:
        print("Scope data captured successfully.")
        return scope_screenshot_path
    else:
        print("The scope data does not match the prompt.")
        return None


def simulink(model_name: str, blocks: list, lines: list, prompt: str, chain: Chain):
    success = False
    attempt = 0
    scope_blocks = []

    # Start MATLAB engine
    eng = matlab.engine.start_matlab()

    while not success and attempt < 5:
        try:
            delete_existing_files('*.m')
            delete_existing_files('*.slx')

            m_file_content = ""
            with open(f'{model_name}.m', 'w') as m_file:
                m_file_content += f"new_system('{model_name}');\n"
                m_file_content += f"save_system('{model_name}');\n"

                for block in blocks:
                    block_type = block["type"]
                    if block_type == 'Inport':
                        block_location = 'simulink/Sources/In1'
                    elif block_type == 'Outport':
                        block_location = 'simulink/Sinks/Out1'
                    elif block_type == 'Scope':
                        block_location = 'simulink/Sinks/Scope'
                        scope_blocks.append(block["name"])
                    else:
                        block_location = block["location"][0].lower() + block["location"][1:] + "/" + block["type"]
                    
                    block_params = block["parameters"]
                    block_name = block["name"]

                    m_file_content += f"add_block('{block_location}', '{model_name}/{block_name}');\n"

                    if isinstance(block_params, dict):
                        for param, value in block_params.items():
                            if param != "Name":
                                parsed_value = parse_value(value)
                                m_file_content += f"set_param('{model_name}/{block_name}', '{param}', '{parsed_value}');\n"
                    elif isinstance(block_params, list):
                        for param_dict in block_params:
                            for param, value in param_dict.items():
                                if param != "Name":
                                    parsed_value = parse_value(value)
                                    m_file_content += f"set_param('{model_name}/{block_name}', '{param}', '{parsed_value}');\n"

                for line in lines:
                    source = line["source"]
                    target = line["target"]
                    m_file_content += f"add_line('{model_name}', '{source}', '{target}');\n"

                for scope in scope_blocks:
                    m_file_content += f"open_system('{model_name}/{scope}');\n"
                    m_file_content += f"set_param('{model_name}/{scope}', 'OpenAtSimulationStart', 'on');\n"

                m_file_content += f"save_system('{model_name}');\n"
                m_file_content += f"close_system('{model_name}', 0);\n"
                m_file_content += f"open_system('{model_name}');\n"
                if scope_blocks:
                    m_file_content += f"set_param('{model_name}', 'StopTime', '300');\n"
                    m_file_content += f"set_param('{model_name}', 'SimulationCommand', 'start');\n"

                m_file.write(m_file_content)
                print(f"\nGenerated MATLAB script ({model_name}.m):\n{m_file_content}")

            result = run_simulink_model(eng, model_name, scope_blocks, prompt, m_file_content)
            if result is True:
                success = True
            else:
                print("Rerunning the model, due to a matlab syntax error.")
                prompt_step(chain)
        except Exception as e:
            print(f"An error occurred: {e}")
            break

    if success:
        print("Model executed successfully.")

from dotenv import load_dotenv
import json
import pickle
import copy
load_dotenv()

import functions as f
import openai
from openai_models import OpenAIMessage, OpenAIResponse
from chain import Chain

def prompt_user(wrap_in_context: bool = False) -> OpenAIMessage:
    print('> ', end='')
    prompt = input()
    if wrap_in_context:
        prompt = Chain.wrap_prompt_in_context(prompt)
    return OpenAIMessage(
        role='user',
        content=prompt,
        name=None,
        function_call=None,
    )

def handle_response(
        response: OpenAIResponse,
        chain: Chain,
) -> tuple[Chain, str]:
    first_choice = response.choices[0]
    chain.add(first_choice.message)
    
    data = json.loads(first_choice.message.content)
    return (chain, data)

def gather_contexts_and_responses(data: str) -> tuple[str, str]:
    contexts = []
    responses = []

    for i, block in enumerate(data["blocks"], start=1):
        block_details = "The block_name: " + block["type"] + "\n" + "The block description: " + block["description"]
        currContext = Chain.wrap_prompt_in_context(block_details)
        contexts.append(f"Context {i}: {currContext}")
        json_response = check(currContext, block)
        responses.append(f"Response {i}: {json_response}")

    delimiter = "\n---\n"
    return delimiter.join(contexts), delimiter.join(responses)

def generate_new_json(chain: Chain, data:str) -> Chain:
    contexts, responses = gather_contexts_and_responses(data)
    chain.add(OpenAIMessage(
        role='assistant',
        content=contexts,
    ))
    chain.add(OpenAIMessage(
        role='assistant',
        content=responses,
    ))
    return chain

def check(context, currJson) -> str:
    context = context[0]
    description = context["description"]
    
    extracted_details = ""
    if description:
        validation_response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "Extract the key validation points for parameters from the following block description."
                },
                {
                    "role": "user",
                    "content": description
                }
            ]
        )
        extracted_details = validation_response.choices[0].message.content
    
    updated_context = copy.deepcopy(context)
    updated_context['description'] = extracted_details
    block_type = updated_context["block_type"]

    if block_type in ['Inport', 'Outport']:
        print("Preserving parameters for Inport and Outport block types")
        parameters = currJson.get('parameters', [])
    else:
        parameters = []

    if parameters:
        updated_context['parameters'] = parameters

    messages = [
        {
            "role": "assistant",
            "content": "context:\n" + json.dumps(updated_context, indent=4) + "\n\n" + "currjson:\n" + json.dumps(currJson, indent=4),
        },
        {
            "role": "user",
            "content": """Given the most recent `context` variable and `currJson` data, generate a new JSON object based on the `context`. Ensure the following structure:
            {
                "type": "String of the block type found in the `context` in the `block_type` section",
                "name": "String of the block name found in the `currJson` data. Make sure to only reference `currJson` and not `context`",
                "location": "String of the block location found in the `context` in the libraries section",
                "parameters": [
                    {
                        "param_name": "param_value"  // `param_name` and `param_value` are placeholders. Replace them with the actual parameter name and value.
                    },
                    // Add as many parameters as needed
                ] 
            }
            
            Important guidelines:
            1. Ensure block `name` is sourced strictly from `currJson`. Derive block `type` and `location` strictly from the `context`.
            2. **Include only the parameters specified in `currJson` that exist in the `context`.** Do not include additional parameters from the `context`.
            3. **Values from `currJson`, if valid, are the most preferred.** Validate that parameters make sense for the block type. Use the other key-value pairs (`type`, `values`, and `default`) in the specific parameter as well as the `description` in the `context` for conceptual guidance when determining if it is valid, and for providing valid parameters.
            4. Avoid syntax errors when constructing matrices or lists in MATLAB/Simulink. Ensure correct use of brackets.
            5. Ensure that the generated code does not expect any further user input or external variables. All parameters must be filled in appropriately within the generated MATLAB code.
            6. `param_name` and `param_value` are placeholders and must be replaced with actual valid parameter names and values. They should never appear in the generated `.m` file.
            7. **It is okay to have no parameters if the `context` does not contain any `parameters` (also known as the list of lists is empty).**
            8. **Validate that parameter names and values are correct and applicable for the block type. Use the context and provided parameters for guidance.**
            """
        }
    ]

    json_response = openai.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        response_format={"type": "json_object"},
    )

    return json_response.choices[0].message.content

def parse_responses(content: str) -> list:
    delimiter = "\n---\n"
    responses = content.split(delimiter)
    parsed_responses = []

    for response in responses:
        try:
            start_index = response.index("{")
            end_index = response.rindex("}") + 1
            json_str = response[start_index:end_index]
            parsed_responses.append(json.loads(json_str))
        except (ValueError, json.JSONDecodeError):
            continue

    return parsed_responses

def prompt_step(chain: Chain) -> Chain:
    chain.reload_context()

    response = f.llm(
        chain,
        temperature=0,
    )
    arr = handle_response(response, chain)
    name = arr[1]["simulink_model_name"]
    lines = arr[1]["lines"]
    chain = generate_new_json(arr[0], arr[1])
    function_call = json.loads(chain.serialize()[-3]["content"]).get("function")
    responses_content = chain.serialize()[-1]["content"]
    blocks = parse_responses(responses_content)
    prompt = chain.serialize()[1]["content"]

    if function_call == "simulink":
        f.simulink(name, blocks, lines, prompt, chain)
    return chain
