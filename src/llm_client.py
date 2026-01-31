"""
LLM Client - Unified interface for multiple LLM providers
Supports: Agent Maestro (Anthropic), Azure OpenAI, OpenAI, etc.

Usage:
    from llm_client import get_llm_client
    
    llm = get_llm_client()
    response = llm.chat("What is fashion?")
"""
import os
import json
import requests
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class LLMClient(ABC):
    """Abstract base class for LLM clients"""
    
    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        timeout: int = 30,
        **kwargs
    ) -> str:
        """
        Send chat completion request and return response text.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens in response
            timeout: Request timeout in seconds
            **kwargs: Additional provider-specific options
        
        Returns:
            Response text content
        
        Raises:
            LLMError: If request fails
        """
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name for logging"""
        pass


class LLMError(Exception):
    """Exception raised when LLM request fails"""
    pass


class AnthropicClient(LLMClient):
    """
    Anthropic Claude API client (via Agent Maestro or direct)
    
    Response format:
        {"content": [{"text": "..."}]}
    """
    
    def __init__(self, endpoint: str, model: str, api_key: Optional[str] = None):
        self.endpoint = endpoint
        self.model = model
        self.api_key = api_key
    
    @property
    def provider_name(self) -> str:
        return f"Anthropic ({self.model})"
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        timeout: int = 30,
        **kwargs
    ) -> str:
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
        
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages
        }
        
        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                headers=headers,
                timeout=timeout
            )
            
            if response.status_code != 200:
                raise LLMError(f"Anthropic API error: {response.status_code} - {response.text[:200]}")
            
            result = response.json()
            return result["content"][0]["text"]
            
        except requests.exceptions.Timeout:
            raise LLMError(f"Request timeout after {timeout}s")
        except requests.exceptions.RequestException as e:
            raise LLMError(f"Request failed: {e}")
        except (KeyError, IndexError) as e:
            raise LLMError(f"Invalid response format: {e}")


class AzureOpenAIClient(LLMClient):
    """
    Azure OpenAI API client
    
    Response format (OpenAI compatible):
        {"choices": [{"message": {"content": "..."}}]}
    """
    
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        deployment: str,
        api_version: str = "2024-08-01-preview"
    ):
        self.endpoint = endpoint.rstrip('/')
        self.api_key = api_key
        self.deployment = deployment
        self.api_version = api_version
    
    @property
    def provider_name(self) -> str:
        return f"Azure OpenAI ({self.deployment})"
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        timeout: int = 30,
        **kwargs
    ) -> str:
        url = f"{self.endpoint}/openai/deployments/{self.deployment}/chat/completions?api-version={self.api_version}"
        
        headers = {
            "Content-Type": "application/json",
            "api-key": self.api_key
        }
        
        payload = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": kwargs.get("temperature", 0.7)
        }
        
        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=timeout
            )
            
            if response.status_code != 200:
                raise LLMError(f"Azure OpenAI API error: {response.status_code} - {response.text[:200]}")
            
            result = response.json()
            return result["choices"][0]["message"]["content"]
            
        except requests.exceptions.Timeout:
            raise LLMError(f"Request timeout after {timeout}s")
        except requests.exceptions.RequestException as e:
            raise LLMError(f"Request failed: {e}")
        except (KeyError, IndexError) as e:
            raise LLMError(f"Invalid response format: {e}")


class OpenAIClient(LLMClient):
    """
    OpenAI API client (also works with OpenAI-compatible endpoints)
    
    Response format:
        {"choices": [{"message": {"content": "..."}}]}
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        endpoint: str = "https://api.openai.com/v1/chat/completions"
    ):
        self.api_key = api_key
        self.model = model
        self.endpoint = endpoint
    
    @property
    def provider_name(self) -> str:
        return f"OpenAI ({self.model})"
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        timeout: int = 30,
        **kwargs
    ) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": kwargs.get("temperature", 0.7)
        }
        
        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                headers=headers,
                timeout=timeout
            )
            
            if response.status_code != 200:
                raise LLMError(f"OpenAI API error: {response.status_code} - {response.text[:200]}")
            
            result = response.json()
            return result["choices"][0]["message"]["content"]
            
        except requests.exceptions.Timeout:
            raise LLMError(f"Request timeout after {timeout}s")
        except requests.exceptions.RequestException as e:
            raise LLMError(f"Request failed: {e}")
        except (KeyError, IndexError) as e:
            raise LLMError(f"Invalid response format: {e}")


# =============================================================================
# Factory Function
# =============================================================================

_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """
    Get or create the LLM client based on environment configuration.
    
    Environment Variables:
        LLM_PROVIDER: 'anthropic' | 'azure_openai' | 'openai' (default: anthropic)
        
        For Anthropic (Agent Maestro):
            LLM_API_ENDPOINT: API endpoint URL
            MODEL_NAME: Model name (e.g., claude-3-5-haiku-20241022)
            ANTHROPIC_API_KEY: API key (optional for Agent Maestro)
        
        For Azure OpenAI:
            AZURE_OPENAI_ENDPOINT: Azure endpoint URL
            AZURE_OPENAI_API_KEY: API key
            AZURE_OPENAI_DEPLOYMENT: Deployment name
            AZURE_OPENAI_API_VERSION: API version (default: 2024-08-01-preview)
        
        For OpenAI:
            OPENAI_API_KEY: API key
            OPENAI_MODEL: Model name (default: gpt-4o-mini)
    
    Returns:
        Configured LLM client instance
    """
    global _llm_client
    
    if _llm_client is not None:
        return _llm_client
    
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    
    if provider == "anthropic":
        _llm_client = AnthropicClient(
            endpoint=os.getenv("LLM_API_ENDPOINT", "http://localhost:23333/api/anthropic/v1/messages"),
            model=os.getenv("MODEL_NAME", "claude-3-5-haiku-20241022"),
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
    
    elif provider == "azure_openai":
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
        
        if not all([endpoint, api_key, deployment]):
            raise ValueError(
                "Azure OpenAI requires AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, and AZURE_OPENAI_DEPLOYMENT"
            )
        
        _llm_client = AzureOpenAIClient(
            endpoint=endpoint,
            api_key=api_key,
            deployment=deployment,
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
        )
    
    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI requires OPENAI_API_KEY")
        
        _llm_client = OpenAIClient(
            api_key=api_key,
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        )
    
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}. Use 'anthropic', 'azure_openai', or 'openai'")
    
    print(f"[LLM] Initialized {_llm_client.provider_name}")
    return _llm_client


def reset_llm_client():
    """Reset the cached LLM client (useful for testing)"""
    global _llm_client
    _llm_client = None


# =============================================================================
# Convenience Functions
# =============================================================================

def chat_completion(
    prompt: str,
    max_tokens: int = 512,
    timeout: int = 30,
    system_prompt: Optional[str] = None
) -> str:
    """
    Simple convenience function for single-turn chat.
    
    Args:
        prompt: User prompt
        max_tokens: Maximum tokens in response
        timeout: Request timeout
        system_prompt: Optional system prompt
    
    Returns:
        Response text
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    client = get_llm_client()
    return client.chat(messages, max_tokens=max_tokens, timeout=timeout)


def parse_json_response(text: str) -> Any:
    """
    Parse JSON from LLM response, handling markdown code blocks.
    
    Args:
        text: Raw LLM response text
    
    Returns:
        Parsed JSON object
    
    Raises:
        json.JSONDecodeError: If parsing fails
    """
    # Handle markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    
    return json.loads(text.strip())
