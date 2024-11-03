import requests
import os

def load_keys():
    endpoints = {
        'openai': 'https://l1wlltwcad.execute-api.us-east-1.amazonaws.com/default/openaiLambda',
        'anthropic': 'https://nxb1ox1u9a.execute-api.us-east-1.amazonaws.com/default/anthropicLambda'
    }
        
    try:
        # Get secrets from both endpoints
        for service, endpoint in endpoints.items():
            response = requests.get(endpoint)
            if response.status_code == 200:
                secret = response.json()
                # Set environment variables
                for key, value in secret.items():
                    os.environ[key] = value
            else:
                raise Exception(f'Error retrieving {service} secret: {response.status_code}, {response.text}')
        
    except Exception as e:
        raise Exception(f'Error in load_keys: {str(e)}')
