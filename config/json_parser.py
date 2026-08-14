import re
import json

def parse_json_response(content: str) -> dict:
    """
    Safely extract and parse JSON from LLM response strings,
    handling markdown codeblocks (```json ... ```) and reasoning preambles.
    """
    if not content:
        raise ValueError("LLM returned empty content")
        
    text = content.strip()
    
    # Strip markdown codeblocks
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0].strip()
        
    # Find JSON object boundaries
    match = re.search(r'(\{.*\})', text, re.DOTALL)
    if match:
        text = match.group(1)
        
    return json.loads(text)
