def strip_code_tags(code: str) -> str:
    if '```' in code:
        code = code.split('```', 1)[-1]

    code = code.split('\n', 1)[-1]
    
    if '```' in code:
        code = code.rsplit('```', 1)[0]
    
    return code.strip()

def add_braces(json_snippet: str) -> str:
    json_snippet = json_snippet.strip()

    if not json_snippet.startswith('{'):
        json_snippet = '{\n' + json_snippet
    if not json_snippet.endswith('}'):
        json_snippet = json_snippet + '\n}'

    return json_snippet