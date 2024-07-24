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
        # Convert the block JSON data to a formatted string
        block_details = "The block_name: " + block["type"] + "\n" + "The block description: " + block["description"]
        
        # Include detailed JSON data in the context
        currContext = Chain.wrap_prompt_in_context(block_details)

        contexts.append(f"Context {i}: {currContext}")
        
        # Pass the detailed context to the check function
        json_response = check(currContext, block)
        
        responses.append(f"Response {i}: {json_response}")

    delimiter = "\n---\n"
    return delimiter.join(contexts), delimiter.join(responses)


def generate_new_json(chain: Chain, data:str) -> Chain:
    contexts, responses = gather_contexts_and_responses(data)

    # Add contexts to the chain
    chain.add(OpenAIMessage(
        role='assistant',
        content=contexts,
    ))

    # Add responses to the chain
    chain.add(OpenAIMessage(
        role='assistant',
        content=responses,
    ))


    # context = ""
    # currContext = ""

    # print(len(data["blocks"]))
    # for block in data["blocks"]:
    #     currContext = Chain.wrap_prompt_in_context(block["type"] + "\n")
    #     print(currContext)
    #     print(block["type"])
    #     json_response = check(currContext, block)
    #     context += f"Context: {currContext}\nJSON Response: {json_response}\n"
    #     input("Press Enter to continue...")
    # function_call = json.loads(chain.serialize()[-1]["content"]).get("function")
    # print("Done")
    # chain.add(OpenAIMessage(
    #     role='assistant',
    #     content=context,
    # ))

    return chain



def check(context, currJson) -> str:
    # Ensure context is a list of dictionaries
    context = context[0]

    # Extract description from the context
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
    
    # Replace the description in the context with the extracted details
    updated_context = copy.deepcopy(context)
    updated_context['description'] = extracted_details

    # Check block type
    block_type = updated_context["block_type"]

    # Preserve parameters for Inport and Outport block types
    if block_type in ['Inport', 'Outport']:
        print("Preserving parameters for Inport and Outport block types")
        parameters = currJson.get('parameters', [])
    else:
        parameters = []

    # Adjust the context to include preserved parameters if needed
    if parameters:
        updated_context['parameters'] = parameters

    # Prepare the messages for the API call
    # messages = [
    #     {
    #         "role": "assistant",
    #         "content": "context:\n" + json.dumps(updated_context, indent=4) + "\n\n" + "currjson:\n" + json.dumps(currJson, indent=4),
    #     },
    #     {
    #         "role": "system",
    #         "content": """Given the most recent `context` variable and `currJson` data, generate a new JSON object based on the `context`. Ensure the following structure:
    #         {
    #             "type": "String of the block type found in the `context` in the block_type section",
    #             "name": "String of the block name found in the `currJson` data. Make sure to only reference `currJson` and not `context`",
    #             "location": "String of the block location found in the `context` in the libraries section",
    #             "parameters": [
    #                 {
    #                     // Replace `param_name` with the `Parameter` value for that specific parameter specified in the `parameters` key of the `context`.
    #                     // Replace `param_value` with the appropriate value based on the following rules:
    #                     // 1. Use the value from `currJson` if it matches the conditions specified in the `description` and any type requirements and possible values specified for that specific parameter in the `parameters` key.
    #                     // 2. If the value from `currJson` does not match these conditions, try to determine the best value using the available information like possible values, type, and description.
    #                     // 3. If no appropriate value can be determined, use the default value specified for that specific parameter in the `parameters` key of the `context`, if available.
    #                     // 4. If no default value is specified and no appropriate value can be determined, use your best judgment given all available information.
    #                     "param_name": "param_value" // `param_name` and `param_value` are placeholders. Replace them with the actual parameter name and value.
    #                 },
    #                 ... (add more parameters if needed)
    #             ] 
    #         }
            
    #         Important guidelines:
    #         1. Ensure that the block name is sourced strictly from `currJson`.
    #         2. The block type and location should be derived from the `context`.
    #         3. Only include parameters that are specified in the `context`. If `currJson` includes additional parameters not found in the `context`, exclude them.
    #         4. If the parameters in `currJson` make sense and abide by these guidelines, keep them. Ensure they are relevant and valid according to the `context`.
    #         5. Validate the parameters to ensure they make sense given the block type and `context`:
    #             a. If the `context` specifies numeric values for certain parameters, ensure the values are appropriately numeric and relevant.
    #             b. Look at the `context` `description` for validating parameters if relevant. This information will not always be available, but if it is, use it to validate the parameters' values.
    #             c. Ensure parameters such as numerator and denominator values, among others, are sensible and functional within the given context. For example, a time domain realization of a transfer function for block 'BandpassFilterModel/BandpassFilter' should validate the values of 'Numerator' and 'Denominator' parameters.
    #             d. This validation is especially important when the blocks have parameters that must be certain values to work correctly. Please take your time to ensure the values are correct.
    #         6. **Parameters can only have values if they are specified as key-value pairs in the `context`.** If the `context` does not have parameter key-value pairs, there should be no parameters, regardless of what the description says.
    #         7. The description should be used only for conceptual guidance and not as key-value pairs for the parameters.
    #         8. The generated code should not expect any further user input or external variables. For example, `set_param('CruiseControlSystem/Constant1', 'Value', 'desired_speed');` is incorrect because `desired_speed` is an external variable.
    #         9. When constructing matrices or lists in MATLAB/Simulink, ensure that brackets are used correctly and that syntax errors are avoided. For example, use square brackets for lists: `set_param('CruiseControlSystem/Scope1', 'Bilevel Measurements', ['Confirm measurement capabilities for transitions, overshoots, undershoots, and cycles.', 'Verify that a Simscape™ or DSP System Toolbox license is available to enable Peak Finder, Bilevel Measurements, and Signal Statistics features.']);`
    #         """
    #     },
    #     {
    #         "role": "user",
    #         "content": "Could you generate for me a new JSON?",
    #     }
    # ]

    # messages = [
    #     {
    #         "role": "assistant",
    #         "content": "context:\n" + json.dumps(updated_context, indent=4) + "\n\n" + "currjson:\n" + json.dumps(currJson, indent=4),
    #     },
    #     {
    #         "role": "user",
    #         "content": """Given the most recent `context` variable and `currJson` data, generate a new JSON object based on the `context`. Ensure the following structure:
    #         {
    #             "type": "String of the block type found in the `context` in the `block_type` section",
    #             "name": "String of the block name found in the `currJson` data. Make sure to only reference `currJson` and not `context`",
    #             "location": "String of the block location found in the `context` in the libraries section",
    #             "parameters": [
    #                 {
    #                     "param_name": "param_value"  // `param_name` and `param_value` are placeholders. Replace them with the actual parameter name and value.
    #                 },
    #                 // Add as many parameters as needed
    #             ] 
    #         }
            
    #         Important guidelines:
    #         1. Ensure block names are sourced strictly from `currJson`. Derive block type and location strictly from the `context`.
    #         2. **Do not include all parameters from the `context`. Include only parameters specified in `currJson` or, if a parameter from `currJson` does not exist in the `context`, include only the least number of necessary parameters from the `context` that might achieve the same goal.** This applies to all blocks.
    #             - For example, if the `currJson` specifies PID parameters (P, I, D), only include these and ignore other parameters available in the context that are not necessary for the specified goal.
    #         3. **Values from `currJson`, if valid, are the most preferred.** Validate that parameters make sense for the block type. Use the other key-value pairs (`type`, `values`, and `default`) in the specific parameter as well as the `description` in the `context` for conceptual guidance.
    #         4. Avoid syntax errors when constructing matrices or lists in MATLAB/Simulink. Ensure correct use of brackets.
    #         5. Ensure that the generated code does not expect any further user input or external variables. All parameters must be filled in appropriately within the generated MATLAB code.
    #         6. `param_name` and `param_value` are placeholders and must be replaced with actual valid parameter names and values. They should never appear in the generated `.m` file.
    #         7. It is okay to have no parameters if the context does not contain any.
    #         """
    #     }
    # ]


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



    # Make the API call
    json_response = openai.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        response_format={"type": "json_object"},
    )

    return json_response.choices[0].message.content

# def check(chain: Chain) -> tuple[Chain, str]:
#     chain.add(OpenAIMessage(
#         role='user',
#         content="""Given the most recent context and json data, please
#         provide a JSON response that includes the following information:
            
#                 "rerun": True or False # Set this to True if all the following conditions are met based on the assistant's response and the most recent JSON data. ONLY TAKE THE DOCUMENTATION INTO ACCOUNT WHEN CHECKING THESE CONDITIONS.:
#                     # 1. The 'type' of each block or state must be found in the documentation.
#                     # 2. The 'parameters' of each block or state must:
#                     #    a. Be found in the documentation.
#                     #    b. Be correct according to the documentation, corresponding to the correct block or state type.
#                     # 3. The 'location' of each block or state must:
#                     #    a. Be found in the documentation.
#                     #    b. Be correct according to the documentation, referring to the correct block or state.
#                     #
#                     # If any of these conditions are not met, set "rerun" to False.
#             }
#         """,
#         name=None,
#         function_call=None,
#     ))
#     response = f.checkJson(chain)

#     arr = handle_response(response, chain)
#     return arr

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
    # chain.print(clear=True)
    chain.add(prompt_user(wrap_in_context=False))

    response = f.llm(
        chain,
        # make sure to use a newer model so that it can work with the format_response parameter
        temperature=0,
    )
    arr = handle_response(response, chain)
    name = arr[1]["simulink_model_name"]
    lines = arr[1]["lines"]
    chain = generate_new_json(arr[0], arr[1])
    function_call = json.loads(chain.serialize()[-3]["content"]).get("function")

    # # Collect all responses
    responses_content = chain.serialize()[-1]["content"]
    blocks = parse_responses(responses_content)

    prompt = chain.serialize()[1]["content"]

    if function_call == "simulink":
        f.simulink(name, blocks, lines, prompt, chain)
    return chain

# Load block names from pickle file
pickle_file_path = './data/block_types.pkl'
with open(pickle_file_path, 'rb') as file:
    block_types = pickle.load(file)

# Initialize Chain with block names
chain = Chain(block_types=block_types)
if True:
    try:
        chain = prompt_step(chain)
    except KeyboardInterrupt:
        from sys import exit
        exit()