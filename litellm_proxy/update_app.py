import os
import re

def update_providers_file():
    """Update the providers.py file to use the LiteLLM Proxy."""
    providers_path = "agentic_news/providers.py"
    
    # Read the current content
    with open(providers_path, "r") as f:
        content = f.read()
    
    # Define the LiteLLMProvider class with proxy support
    litellm_provider_class = """
class LiteLLMProvider(LiteLLMBaseProvider):
    \"\"\"Universal provider for all LLM models using LiteLLM\"\"\"

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
        \"\"\"Get a completion from the LLM API.\"\"\"
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
        \"\"\"Get list of available text-only models\"\"\"
        return list(cls.TEXT_MODELS.keys())

    @classmethod
    def get_providers(cls, model):
        \"\"\"Get available providers for a model\"\"\"
        model_info = cls.aliases.get(model)
        if isinstance(model_info, dict):
            return list(model_info.keys())
        return [model_info.split("/")[0]] if model_info else []
"""
    
    # Find the LiteLLMProvider class and replace it
    pattern = r"class LiteLLMProvider\(LiteLLMBaseProvider\):.*?(?=\n\n\w+|$)"
    updated_content = re.sub(pattern, litellm_provider_class.strip(), content, flags=re.DOTALL)
    
    # Write the updated content back to the file
    with open(providers_path, "w") as f:
        f.write(updated_content)
    
    print(f"Updated {providers_path} with LiteLLM Proxy support")

def update_agent_file():
    """Update the agent.py file to import ProxyConfig."""
    agent_path = "agentic_news/agent.py"
    
    # Read the current content
    with open(agent_path, "r") as f:
        content = f.read()
    
    # Check if the import is already there
    if "from litellm.proxy import ProxyConfig" not in content:
        # Add the import
        content = content.replace(
            "from litellm import chat_completion",
            "from litellm import chat_completion\nfrom litellm.proxy import ProxyConfig"
        )
        
        # Write the updated content back to the file
        with open(agent_path, "w") as f:
            f.write(content)
        
        print(f"Updated {agent_path} with ProxyConfig import")
    else:
        print(f"ProxyConfig import already exists in {agent_path}")

def update_env_file():
    """Update the .env file with the LiteLLM Proxy URL."""
    env_path = ".env"
    
    # Get the proxy URL from environment or use the default
    proxy_url = os.environ.get("LITELLM_PROXY_URL", "https://litellm-proxy-91999464974.us-central1.run.app")
    
    # Read the current content if the file exists
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            content = f.readlines()
        
        # Check if LITELLM_PROXY_URL is already in the file
        proxy_line_exists = False
        for i, line in enumerate(content):
            if line.startswith("LITELLM_PROXY_URL="):
                content[i] = f"LITELLM_PROXY_URL={proxy_url}\n"
                proxy_line_exists = True
                break
        
        # If not, add it
        if not proxy_line_exists:
            content.append(f"\n# LiteLLM Proxy URL\nLITELLM_PROXY_URL={proxy_url}\n")
    else:
        # Create a new file
        content = [f"# LiteLLM Proxy URL\nLITELLM_PROXY_URL={proxy_url}\n"]
    
    # Write the updated content back to the file
    with open(env_path, "w") as f:
        f.writelines(content)
    
    print(f"Updated {env_path} with LITELLM_PROXY_URL={proxy_url}")

if __name__ == "__main__":
    update_providers_file()
    update_agent_file()
    update_env_file()
    
    print("\nUpdates complete! You can now run your application with the LiteLLM Proxy.")
    print("\nTo run the proxy locally:")
    print("1. Set your API key: export MISTRAL_API_KEY=your_api_key_here")
    print("2. Run the Docker container: docker-compose up -d")
    print("\nOr use the deployed proxy at:", os.environ.get("LITELLM_PROXY_URL", "https://litellm-proxy-91999464974.us-central1.run.app")) 