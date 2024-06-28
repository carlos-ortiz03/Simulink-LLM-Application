from openai import OpenAI
import openai
import matlab.engine
import ast
import re
import glob
import time
# from pydantic import BaseModel, Field
# from doc_agent import simulink_documentation_lookup
# from openai_function_call import openai_function
from openai_models import OpenAIMessage, OpenAIResponse
import os
from chain import Chain
from dotenv import load_dotenv
load_dotenv()



# class ModelicaModel(BaseModel):
#     '''
# Modelica model definition. These models are used to simulate and plot real-life systems. Your model definition will be loaded into the OMEdit GUI, so make sure it includes annotations. PLEASE refer to the Modelica documentation (using the "modelica_documentation_lookup" tool) for more information or when otherwise uncertain.
#     '''

#     name: str = Field(
#         description='Name of the model. Example: Vehicle',
#     )

#     definition: str = Field(
#         description='''Complete Modelica model definition. DO NOT include any commentary. ALWAYS include "annotations" to ensure your model can be drawn in the OMEdit connection editor. Never use a "within" clause when defining a model.
# Bad Example (NEVER do this):
# within Modelica.Electrical.Analog.Examples.OpAmps;

# Example:
# model Vehicle
#     parameter Real m = 1000 "Mass of the vehicle";
#     parameter Real F = 3000 "Force applied to the vehicle";
#     Real v(start = 0) "Velocity of the vehicle";
#     Real a "Acceleration of the vehicle";
# equation
#     m * der(v) = F;
#     a = der(v);
# end Vehicle;'''
#     )

# #     parameters: list[str] = Field(
# #         description='''The parameters of the model object. All named variables or parameters MUST be defined here. DO NOT include any semicolons (;) or docstring comments. This is where ALL components (resistors, capacitors, ...), variables, inputs, etc must be declared!
# # Example: [parameter Modelica.Units.SI.Distance s = 100, parameter Modelica.Units.SI.Velocity v = 10, Real x(start = s, fixed = true)]''',
# #     )

# #     equations: list[str] = Field(
# #         description='''The equations relating the parameters of the model object. This section defines an ordinary differential equation governing the behavior of the model. It MUST NOT contain any component (resistors, capacitors, etc), variable, or input declarations!
# # Example: [der(x) = v, x = s + v * t] ''',
# #     )


# def dump_model(filename: str, model: str):
#     with open(filename, 'w') as f:
#         f.write(model)
#     return


# @openai_function
# def define_model(model_spec: ModelicaModel) -> str:
#     '''Define a Modelica model object'''
#     from pyparsing.exceptions import ParseException
#     try:
#         model = model_spec.definition
#         model = model.replace(';;', ';')
#         model = '\n'.join([
#             line for line in model.split('\n')
#             if not line.startswith('within')
#         ])

#         print(model)
#         output = om(model)
#         print(output)

#         if output.startswith('('):
#             valid = om(f'instantiateModel({model_spec.name})')
#             print(valid)
#         if 'Error:' in valid:
#             raise ParseException(valid)
#         dump_model(f'../llm_{model_spec.name}.mo', model)

#         return str(output)

#     except ParseException as e:
#         print('\nModel feedback > ', end='')
#         user_feedback = input().strip()
#         error_message = f'Parsing error: {str(e)}'
#         if len(user_feedback) > 1:
#             error_message += f'\nUser feedback: {user_feedback}'
#         return error_message
# #         return f'''
# # Parsing error: {str(e)}
# # User feedback (if any): {input().strip()}'''


# @openai_function
# def simulate(model_name: str, stopTime: float) -> str:
#     '''
#     Run a simulation on a given model object

#     model_name: Name of the model object to simulate
#     stopTime: Time (s) at which to stop the simulation
#     '''
#     print(om(f'list({model_name})'))
#     output = om(f'simulate({model_name}, stopTime={stopTime})')
#     print(output)
#     return str(output)


# @openai_function
# def plot(variable_list: str) -> str:
#     '''
#     Plot the results of a Modelica simulation.

#     variable_list: A comma-separated string representing the list of variables to plot. Example: x,der(x),v
#     '''
#     output = om('plot({' + variable_list + '})')
#     print(output)
#     return str(output)


# @openai_function
# def simulink_documentation(search_query: str) -> str:
#     '''
#     Consult the documentation for the Modelica Standard Library. Use keywords (like specific function or object names) to find examples and best practices.
#     '''
#     return simulink_documentation_lookup(search_query)


# functions = {
#     'define_model': define_model,
#     'simulate': simulate,
#     'plot': plot,
#     'simulink_documentation': simulink_documentation,
# }

# schemas = [f.openai_schema for f in functions.values()]


# def dispatch_function(
#         response: OpenAIResponse,
# ) -> OpenAIMessage:
#     name, response = response.prepare_for_function_call()
#     result = functions[name].from_response(response)
#     return OpenAIMessage(
#         role='function',
#         name=name,
#         content=result,
#     )


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


# def simulink(model_name: str, blocks: list, lines: list):
#     def parse_value(value):
#         try:
#             # Try to evaluate the string to a Python literal
#             parsed_value = ast.literal_eval(value)
#             if isinstance(parsed_value, list):
#                 # If it's a list, convert it to a MATLAB array format as a string
#                 return f"[{' '.join(map(str, parsed_value))}]"
#             elif isinstance(parsed_value, (int, float)):
#                 # If it's a number, return it as a string
#                 return str(parsed_value)
#             else:
#                 # Otherwise, return the evaluated value as a string
#                 return str(parsed_value)
#         except (ValueError, SyntaxError):
#             # If evaluation fails, return the original string
#             return value

#     try:
#         # Start MATLAB engine
#         eng = matlab.engine.start_matlab()

#         # Create a new Simulink model
#         eng.new_system(model_name)
#         eng.save_system(model_name)  # Save the new system before making modifications

#         # Add blocks to the model
#         for block in blocks:
#             block_type = block["type"]
#             block_location = block["location"][0].lower() + block["location"][1:] + "/" + block["type"]
#             block_params = block["parameters"]
            
#             # Handling the block name
#             if isinstance(block_params, dict):
#                 block_name = block_params.get("Name", f"{block_type}_{blocks.index(block) + 1}")  # Generate a name if not provided
#             elif isinstance(block_params, list):
#                 name_dict = next((item for item in block_params if "Name" in item), {})
#                 block_name = name_dict.get("Name", f"{block_type}_{blocks.index(block) + 1}")

#             # Add block to the model
#             eng.add_block(f'{block_location}', f'{model_name}/{block_name}')

#             # Set block parameters (commented out)
#             # if isinstance(block_params, dict):
#             #     for param, value in block_params.items():
#             #         if param != "Name":  # 'Name' parameter is used for the block name
#             #             parsed_value = parse_value(value)
#             #             print(f"Setting parameter {param} for block {model_name}/{block_name} with value {parsed_value}")
#             #             eng.set_param(f'{model_name}/{block_name}', param, parsed_value)
#             # elif isinstance(block_params, list):
#             #     for param_dict in block_params:
#             #         for param, value in param_dict.items():
#             #             if param != "Name":  # 'Name' parameter is used for the block name
#             #                 parsed_value = parse_value(value)
#             #                 print(f"Setting parameter {param} for block {model_name}/{block_name} with value {parsed_value}")
#             #                 eng.set_param(f'{model_name}/{block_name}', param, parsed_value)
#             print("\n")

#         # Add lines (connections) to the model
#         for line in lines:
#             source = line["source"]
#             target = line["target"]
#             eng.add_line(model_name, source, target)

#         # Save the model (but do not close it)
#         eng.save_system(model_name)
        
#         print("Simulink model is open. Press Ctrl+C to close and quit.")
        
#         # Keep the script running to keep Simulink open
#         while True:
#             pass

#     except KeyboardInterrupt:
#         print("Keyboard interrupt received. Closing Simulink model and quitting.")
#         # Save and close the model
#         eng.save_system(model_name)
#         eng.close_system(model_name, save=True)
#         # Stop MATLAB engine
#         eng.quit()



def delete_existing_files(pattern):
    files = glob.glob(pattern)
    for file in files:
        os.remove(file)
    print(f"Deleted files: {files}")

def call_chatgpt(m_file_content, error_message):
    prompt = f"The following MATLAB script has an error:\n\n{m_file_content}\n\nError: {error_message}\n\nPlease provide only the corrected MATLAB script code without any explanation."
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a MATLAB expert."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )

    print("content: ")
    print(response.choices[0].message.content)
    
    return response.choices[0].message.content

def run_simulink_model(model_name: str):
    try:
        # Start MATLAB engine
        eng = matlab.engine.start_matlab()

        # Run the .m file
        eng.run(f'{model_name}', nargout=0)

        print(f".m file '{model_name}.m' executed successfully in MATLAB.")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Terminating...")
            eng.quit()
            return True
    except matlab.engine.MatlabExecutionError as matlab_err:
        error_message = str(matlab_err)
        print(f"An error occurred while executing the MATLAB script: {error_message}")
        eng.quit()
        return error_message

def simulink(model_name: str, blocks: list, lines: list):
    def parse_value(value):
        try:
            # Try to evaluate the string to a Python literal
            parsed_value = ast.literal_eval(value)
            if isinstance(parsed_value, list):
                # If it's a list, convert it to a MATLAB array format as a string
                return f"[{' '.join(map(str, parsed_value))}]"
            elif isinstance(parsed_value, (int, float)):
                # If it's a number, return it as a string
                return str(parsed_value)
            else:
                # Otherwise, return the evaluated value as a string
                return str(parsed_value)
        except (ValueError, SyntaxError):
            # If evaluation fails, return the original string
            return value

    success = False
    attempt = 0

    while not success and attempt < 5:  # Limit the number of attempts to avoid infinite loops
        try:
            # Delete existing .m and .slx files in the directory
            delete_existing_files('*.m')
            delete_existing_files('*.slx')

            # Create and open the .m file for writing
            m_file_content = ""
            with open(f'{model_name}.m', 'w') as m_file:
                # Write the MATLAB commands to create and save the new system
                m_file_content += f"new_system('{model_name}');\n"
                m_file_content += f"save_system('{model_name}');\n"

                # Add blocks to the model
                for block in blocks:
                    block_type = block["type"]
                    if block_type == 'Inport':
                        block_location = 'simulink/Sources/In1'
                        print("Inport block detected. Press Enter to continue...")
                        input()
                    elif block_type == 'Outport':
                        block_location = 'simulink/Sinks/Out1'
                        print("Outport block detected. Press Enter to continue...")
                        input()
                    else:
                        block_location = block["location"][0].lower() + block["location"][1:] + "/" + block["type"]
                    block_params = block["parameters"]
                    block_name = block["name"]

                    # # Handling the block name
                    # if isinstance(block_params, dict):
                    #     block_name = block_params.get("Name", f"{block_type}_{blocks.index(block) + 1}")  # Generate a name if not provided
                    # elif isinstance(block_params, list):
                    #     name_dict = next((item for item in block_params if "Name" in item), {})
                    #     block_name = name_dict.get("Name", f"{block_type}_{blocks.index(block) + 1}")

                    # Add block to the model
                    m_file_content += f"add_block('{block_location}', '{model_name}/{block_name}');\n"

                    # Set block parameters
                    if isinstance(block_params, dict):
                        for param, value in block_params.items():
                            if param != "Name":  # 'Name' parameter is used for the block name
                                parsed_value = parse_value(value)
                                m_file_content += f"set_param('{model_name}/{block_name}', '{param}', '{parsed_value}');\n"
                    elif isinstance(block_params, list):
                        for param_dict in block_params:
                            for param, value in param_dict.items():
                                if param != "Name":  # 'Name' parameter is used for the block name
                                    parsed_value = parse_value(value)
                                    m_file_content += f"set_param('{model_name}/{block_name}', '{param}', '{parsed_value}');\n"

                # Add lines (connections) to the model
                for line in lines:
                    source = line["source"]
                    target = line["target"]
                    m_file_content += f"add_line('{model_name}', '{source}', '{target}');\n"

                # Save the model
                m_file_content += f"save_system('{model_name}');\n"
                m_file_content += f"open_system('{model_name}');\n"
                m_file.write(m_file_content)

            # Print the .m file content before running it
            print(f"\nGenerated MATLAB script ({model_name}.m):\n")
            print(m_file_content)
            
            print(f"\n.m file '{model_name}.m' created successfully.")
            
            # Try running the model
            result = run_simulink_model(model_name)
            if result is True:
                success = True
            else:
                attempt += 1
                print(f"Attempt {attempt}: Fixing script and retrying...")
                m_file_content = call_chatgpt(m_file_content, result)
                with open(f'{model_name}.m', 'w') as m_file:
                    m_file.write(m_file_content)

        except Exception as e:
            print(f"An error occurred: {e}")
            break

    if success:
        print("Model executed successfully.")
    else:
        print("Failed to execute the model after several attempts.")