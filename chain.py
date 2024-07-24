import os
import json
import pickle
import doc_agent as docs
from openai_models import OpenAIMessage, OpenAIRole
from pydantic import BaseModel, Field
from sys import argv
from termcolor import colored

class Chain(BaseModel):
    messages: list[OpenAIMessage] = Field(default=[])
    testbench: str | None = Field(default=None)

    @staticmethod
    def wrap_prompt_in_context(prompt):
        context = docs.simulink_documentation_lookup(prompt)
        return context

    def __init__(self, system: str | None = None, block_types=None):
        super().__init__()
        if block_types is None:
            block_types = []


        system_message_content = system or f"""
        You are a helpful assistant and an expert in Simulink. You can choose between two methods to create a model:
        1. Using the 'simulink' function (for blocks and lines).
        2. Using the 'state_transition' function (for states and transitions using Stateflow).

        **The available block types you can use are: {block_types}. You must only use block types from this list to accomplish the end goal.**

        After deciding which function to use, you must determine which blocks or states to add to the model as well as lines or transitions. Return this information in a JSON object with the following structure:
        {{
            "function": "function_name",  // The function to use: either 'simulink' or 'state_transition'
            "simulink_model_name": "model_name",    // The name of the model to create
            "blocks" or "states": [       // An array of blocks or states to add to the model, depending on the function
                {{
                    "type": "block_type",  // The type of the block or state. Only use block types from the provided list: {block_types}.
                    "description": "block_description",  // A formal complete description from the MathWorks website of the specific block or state
                    "location": "block_location",  // The location of the block in the model (e.g., 'simulink/Commonly Used Blocks')
                    "name": "blocktypeindex", // The name of the block or state, ensuring uniqueness by appending an index (e.g., 'TransferFcn1', 'TransferFcn2')
                    "parameters": {{       // A dictionary of parameters for the block or state
                        "param_name": "param_value" // Add as many parameters as needed, applicable to the specific block or state type. Make sure the values make sense for the block or state and achieve the specified end goal.
                    }}
                }},
                // Add as many blocks or states as needed
            ],
            "lines" or "transitions": [   // An array of connections (links) between the blocks or states
                {{
                    "source": "blockname1/(corresponding port)", // The source block or state name
                    "target": "blockname2/(corresponding port)"  // The target block or state name
                }},
                // Add as many links or transitions as needed
            ]
        }}

        Ensure that the names provided for blocks are unique. If two blocks have the same type, append a number to their names to differentiate them (e.g., 'TransferFcn1', 'TransferFcn2'). Use these unique names consistently in the 'lines' or 'transitions' array.
        Make sure to use valid ports and do not try to use ports that don't exist, especially for the lines. Validate that the ports you reference on each block actually exist and are correctly specified.

        When generating your JSON response, ensure you are using only the block types from the provided list to accomplish the specified end goal. Carefully validate all parameters, especially those provided, to ensure they are appropriate and will lead to achieving the user's desired outcome. When setting parameters such as P, I, and D for a PID controller, ensure they are tuned to achieve the goal specified in the prompt.

        **Emphasize the importance of ensuring enough simulation time is allotted. The simulation time should be determined based on the parameter values and the nature of the system being modeled. Ensure the simulation runs for at most 5 minutes or until the system reaches stability and exhibits the desired dynamics based on the prompt. The accuracy of the system response, especially achieving minimal overshoot, is crucial.**
        """




        self.messages = [OpenAIMessage(
            role='system',
            content=system_message_content,
            name=None,
            function_call=None
        )]
        print("Chain initialized")



    def add(self, message: OpenAIMessage | dict[str, str]):
        if not isinstance(message, OpenAIMessage):
            message = OpenAIMessage(**message)
        self.messages.append(message)

    def serialize(self) -> list[dict[str, str]]:
        return [
            m.dict(exclude_unset=True)
            for m in self.messages
        ]

    def reload_context(self):
        self.messages = self.messages[:2]

        # try:
        #     root = '../'
        #     model_file = [
        #         f for f in os.listdir(root)
        #         if f.startswith('llm_')
        #     ][0]
        #     with open(f'{root}{model_file}', 'r') as f:
        #         self.add(OpenAIMessage(
        #             role=OpenAIRole.user,
        #             content=f'Current model definition:\n{f.read()}',
        #             name=None,
        #             function_call=None
        #         ))

        # except FileNotFoundError:
        #     pass

    def __len__(self) -> int:
        return len(self.messages)

    def print(self, clear=True):
        if clear:
            os.system('clear')

        role_to_color = {
            'system': 'red',
            'user': 'green',
            'assistant': 'blue',
            'function_call': 'yellow',
            'function': 'magenta',
        }

        def format_message(message):
            match message.role:
                case OpenAIRole.system:
                    return f'system: {message.content}', role_to_color['system']
                case OpenAIRole.user:
                    return f'user: {message.content}', role_to_color['user']
                case OpenAIRole.assistant:
                    if message.function_call:
                        return f'assistant ({message.function_call.name}): {message.function_call.arguments}', role_to_color['function_call']
                    else:
                        return f'assistant: {message.content}', role_to_color['assistant']
                case OpenAIRole.function:
                    return f'function ({message.name}): {message.content}', role_to_color['function']
                case _:
                    raise ValueError(f'Unknown role: {message.role}')

        for message in self.messages:
            print(colored(*format_message(message)))
