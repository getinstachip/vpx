import requests
from typing import Dict, Optional
from functools import lru_cache

class KeyManager:
    _instance: Optional['KeyManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(KeyManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self.endpoints = {
            'OPENAI_API_KEY': 'https://l1wlltwcad.execute-api.us-east-1.amazonaws.com/default/openaiLambda',
            'ANTHROPIC_API_KEY': 'https://nxb1ox1u9a.execute-api.us-east-1.amazonaws.com/default/anthropicLambda'
        }
        self._keys: Optional[Dict[str, str]] = None
        self._initialized = True

    @lru_cache(maxsize=1)
    def _fetch_keys_from_server(self) -> Dict[str, str]:
        """Fetch API keys from the server"""
        api_keys = {}
        errors = []
        
        for service, endpoint in self.endpoints.items():
            try:
                response = requests.get(endpoint)
                response.raise_for_status()
                secret = response.json()
                api_keys[service] = secret['key']
            except requests.exceptions.RequestException as e:
                errors.append(f"{service}: {str(e)}")
        
        if not api_keys:
            raise Exception(f"Failed to retrieve API keys: {'; '.join(errors)}")
            
        return api_keys

    def get_keys(self) -> Dict[str, str]:
        """Get API keys, using cached version if available"""
        if not self._keys:
            self._keys = self._fetch_keys_from_server()
        return self._keys

    def get_key(self, service: str) -> str:
        """Get a specific API key"""
        keys = self.get_keys()
        if service not in keys:
            raise KeyError(f"No key found for service: {service}")
        return keys[service]

# Global instance
key_manager = KeyManager()

def get_openai_key() -> str:
    """Get OpenAI API key"""
    return key_manager.get_key('OPENAI_API_KEY')

def get_anthropic_key() -> str:
    """Get Anthropic API key"""
    return key_manager.get_key('ANTHROPIC_API_KEY')