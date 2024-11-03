import requests
import os

def load_keys():
    endpoints = {
        'OPENAI_API_KEY': 'https://l1wlltwcad.execute-api.us-east-1.amazonaws.com/default/openaiLambda',
        'ANTHROPIC_API_KEY': 'https://nxb1ox1u9a.execute-api.us-east-1.amazonaws.com/default/anthropicLambda'
    }
    
    api_keys = {}
    try:
        # Get secrets from both endpoints
        for service, endpoint in endpoints.items():
            response = requests.get(endpoint)
            if response.status_code == 200:
                secret = response.json()
                api_keys[service] = secret['key']
            else:
                raise Exception(f'Error retrieving {service} secret: {response.status_code}, {response.text}')
        return api_keys
        
    except Exception as e:
        raise Exception(f'Error in load_keys: {str(e)}')