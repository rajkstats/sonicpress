import os
import json
from openai import OpenAI
import litellm
from litellm import completion
from .config import MISTRAL_API_KEY

def Message(content, role="assistant"):
    return {"role": role, "content": content}

def parse_json(s):
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        print(f"Error decoding JSON for tool call arguments: {s}")
        return None

def extract_json_objects(s):
    """Extract all balanced JSON objects from a string."""
    objects = []
    brace_level = 0
    start_index = None
    for i, char in enumerate(s):
        if char == "{":
            if brace_level == 0:
                start_index = i
            brace_level += 1
        elif char == "}":
            brace_level -= 1
            if brace_level == 0 and start_index is not None:
                candidate = s[start_index : i + 1]
                try:
                    obj = json.loads(candidate)
                    objects.append(obj)
                except json.JSONDecodeError:
                    pass
                start_index = None
    return objects

class LLMProvider:
    base_url = None
    api_key = None
    aliases = {}

    def __init__(self, model):
        self.model = self.aliases.get(model, model)
        print(f"Using {self.__class__.__name__} with {self.model}")
        self.client = self.create_client()

    def create_function_schema(self, definitions):
        functions = []
        for name, details in definitions.items():
            properties = {}
            required = []
            for param_name, param_desc in details["params"].items():
                properties[param_name] = {"type": "string", "description": param_desc}
                required.append(param_name)
            if not properties:
                properties["noop"] = {
                    "type": "string",
                    "description": "Dummy parameter for function with no parameters.",
                }
            function_def = self.create_function_def(name, details, properties, required)
            functions.append(function_def)
        return functions

    def create_tool_call(self, name, parameters):
        return {
            "type": "function",
            "name": name,
            "parameters": parameters,
        }

    def completion(self, messages, **kwargs):
        filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        completion = self.client.create(messages=messages, model=self.model, **filtered_kwargs)
        if hasattr(completion, "error"):
            raise Exception("Error calling model: {}".format(completion.error))
        return completion

class OpenAIBaseProvider(LLMProvider):
    def create_client(self):
        return OpenAI(base_url=self.base_url, api_key=self.api_key).chat.completions

    def create_function_def(self, name, details, properties, required):
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": details["description"],
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    def call(self, messages, functions=None):
        tools = self.create_function_schema(functions) if functions else None
        completion = self.completion(messages, tools=tools)
        message = completion.choices[0].message

        if functions:
            tool_calls = message.tool_calls or []
            combined_tool_calls = [
                self.create_tool_call(
                    tool_call.function.name, parse_json(tool_call.function.arguments)
                )
                for tool_call in tool_calls
                if parse_json(tool_call.function.arguments) is not None
            ]

            if message.content and not tool_calls:
                json_objs = extract_json_objects(message.content)
                for obj in json_objs:
                    parameters = obj.get("parameters", obj.get("arguments"))
                    if obj.get("name") and parameters is not None:
                        combined_tool_calls.append(
                            self.create_tool_call(obj.get("name"), parameters)
                        )
                if combined_tool_calls:
                    return None, combined_tool_calls

            return message.content, combined_tool_calls
        else:
            return message.content

class LiteLLMBaseProvider(OpenAIBaseProvider):
    def create_client(self):
        litellm.drop_params = True
        litellm.modify_params = True
        return completion

    def completion(self, messages, **kwargs):
        filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        completion_response = self.client(
            model=self.model,
            messages=messages,
            api_key=self.api_key,
            **filtered_kwargs,
        )
        return completion_response

    def call(self, messages, functions=None):
        if (
            "mistral" in self.model.lower()
            and messages
            and messages[-1].get("role") == "assistant"
        ):
            prefix = messages.pop()["content"]
            if messages and messages[-1].get("role") == "user":
                messages[-1]["content"] = prefix + "\n" + messages[-1].get("content", "")
            else:
                messages.append({"role": "user", "content": prefix})
        return super().call(messages, functions)

class LiteLLMProvider(LiteLLMBaseProvider):
    """Universal provider for all LLM models using LiteLLM"""

    # Proxy URL - can be overridden with environment variable
    PROXY_URL = os.environ.get("LITELLM_PROXY_URL", "http://localhost:8080")

    TEXT_MODELS = {
        "llama3.3": {
            "groq": "groq/llama-3.3-70b-versatile",
            "fireworks": "fireworks/llama-v3p3-70b-instruct",
        },
        "small": "mistral-small",  # Use proxy model names
        "medium": "mistral-medium",  # Use proxy model names
        "large": "mistral-large",  # Use proxy model names
        "gpt-4": "openai/gpt-4-turbo-preview",
        "claude-3-opus": "anthropic/claude-3-opus-20240229",
        "claude-3-sonnet": "anthropic/claude-3-5-sonnet-20241022",
        "claude-3-haiku": "anthropic/claude-3-haiku-20240229",
        "gemini-pro": "gemini/gemini-pro",
        "deepseek-coder": "deepseek/deepseek-coder-33b-instruct",
    }

    aliases = TEXT_MODELS

    PROVIDER_MODEL_MAPPINGS = {
        "fireworks": {
            "provider": "fireworks_ai",
            "model_template": "fireworks_ai/accounts/fireworks/models/{model}",
        },
        "openai": {"provider": "openai", "model_template": "openai/{model}"},
        "anthropic": {"provider": "anthropic", "model_template": "anthropic/{model}"},
        "groq": {"provider": "groq", "model_template": "groq/{model}"},
        "mistral": {"provider": "mistral", "model_template": "mistral/{model}"},
        "gemini": {"provider": "gemini", "model_template": "gemini/{model}"},
    }

    def __init__(self, model, provider=None):
        model_info = self.aliases.get(model)
        
        # If using proxy, simplify model handling
        if self.PROXY_URL:
            if isinstance(model_info, dict):
                if not provider:
                    provider = next(iter(model_info))
                self.model = model_info[provider]
            else:
                self.model = model_info or model
            
            # Print proxy information
            print(f"Using LiteLLMProvider with {self.model} via proxy at {self.PROXY_URL}")
            
            # Set API key to None as it will be handled by the proxy
            self.api_key = None
            
            # Initialize with proxy settings
            super(LiteLLMBaseProvider, self).__init__(self.model)
            return
        
        # Original initialization for direct API access
        if isinstance(model_info, dict):
            if not provider:
                provider = next(iter(model_info))
            model_path = model_info[provider]
        else:
            model_path = model_info

        parts = model_path.split("/")
        provider_name = parts[0]
        provider_config = self.PROVIDER_MODEL_MAPPINGS.get(
            provider_name,
            {"provider": provider_name, "model_template": f"{provider_name}/{{model}}"},
        )

        if "/" in model_path:
            _, model_name = model_path.split("/", 1)
            self.model = provider_config["model_template"].format(model=model_name)
            self.provider = provider_config["provider"]
        else:
            self.model = model_path
            self.provider = provider_name

        self.api_key = os.getenv(f"{provider_name.upper()}_API_KEY")
        super().__init__(self.model)

    def completion(self, messages, **kwargs):
        """Get a completion from the LLM API."""
        filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        
        # If using proxy, add api_base parameter
        if self.PROXY_URL:
            filtered_kwargs["api_base"] = self.PROXY_URL
            
            # Handle different message formats
            if isinstance(messages, str):
                # Convert string to messages format
                filtered_kwargs["messages"] = [{"role": "user", "content": messages}]
            else:
                filtered_kwargs["messages"] = messages
                
            try:
                completion_response = self.client(
                    model=self.model,
                    **filtered_kwargs,
                )
                return completion_response
            except Exception as e:
                print(f"Error with LiteLLM Proxy: {e}")
                # Fall back to direct API if proxy fails
                if "api_base" in filtered_kwargs:
                    del filtered_kwargs["api_base"]
                # Try direct API call
                return super().completion(messages, **filtered_kwargs)
        
        # Original completion method for direct API access
        return super().completion(messages, **filtered_kwargs)

    @classmethod
    def get_text_models(cls):
        """Get list of available text-only models"""
        return list(cls.TEXT_MODELS.keys())

    @classmethod
    def get_providers(cls, model):
        """Get available providers for a model"""
        model_info = cls.aliases.get(model)
        if isinstance(model_info, dict):
            return list(model_info.keys())
        return [model_info.split("/")[0]] if model_info else []