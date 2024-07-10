from dotenv import load_dotenv
import json
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

    print(responses)
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
    json_response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "assistant",
                "content": context + "\n" + json.dumps(currJson),
            },
            {
                "role": "system",
                "content": """Given the most recent context and JSON data, generate a new JSON object based on the context. Ensure the following structure:
                {
                    "type": "String of the block type found in the context in the block_name section",
                    "name": "String of the block name found in the currJson data. Make sure to only reference 'currJson' and not 'context'",
                    "location": "String of the block location found in the `context` in the libraries section",
                    "parameters": [
                        {
                            "param_name": "param_value"
                        },
                        ...
                    ]
                }
                Ensure all parameters are provided as a list of dictionaries, even if there is only one parameter. The parameter values should be correctly formatted according to the given context. If currJson contains a parameter that is not in the context, exclude it and adhere strictly to the parameters defined by the context. Additionally, make sure to check the values provided for these parameters and ensure they are valid."""
            },
            {
                "role": "user",
                "content": "Could you generate for me a new JSON?",
            }
        ],
        response_format={ "type": "json_object" },
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
    if len(chain) <= 1:
        chain.add(prompt_user(wrap_in_context=False))

    if len(chain) > 10:
        chain.reload_context()

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

    if function_call == "simulink":
        f.simulink(name, blocks, lines)
    return chain


chain = Chain()
if True:
    try:
        chain = prompt_step(chain)
    except KeyboardInterrupt:
        from sys import exit
        exit()