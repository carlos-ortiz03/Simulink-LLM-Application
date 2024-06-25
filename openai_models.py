from enum import Enum
from pydantic import BaseModel, validator


class OpenAIRole(str, Enum):
    system = 'system'
    assistant = 'assistant'
    user = 'user'
    function = 'function'


class OpenAIFunctionCall(BaseModel):
    name: str
    arguments: str


class OpenAIMessage(BaseModel):
    role: OpenAIRole
    content: str | None
    name: str | None = None
    function_call: OpenAIFunctionCall | None = None

    @validator('content')
    def content_must_be_some(cls, content: str) -> str:
        return content or ''


class OpenAIChoice(BaseModel):
    index: int
    message: OpenAIMessage
    finish_reason: str


class OpenAIUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class OpenAIResponse(BaseModel):
    id: str
    object: str
    created: int
    choices: list[OpenAIChoice]
    usage: OpenAIUsage

    def prepare_for_function_call(self):
        new = self.copy(deep=True)
        name = new.choices[0].message.function_call.name
        for choice in new.choices:
            choice.message.function_call = dict(
                choice.message.function_call,
            )
            choice.message = dict(choice.message)
        return name, new