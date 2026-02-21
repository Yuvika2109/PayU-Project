import requests
import json
import re

OLLAMA_URL = "http://localhost:11434/api/generate"

def call_llm(prompt: str):
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": "llama3",
            "prompt": prompt,
            "stream": False
        }
    )

    text = response.json()["response"]

    # Extract clean JSON
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON found in LLM output")

    clean_json = match.group(0)
    return json.loads(clean_json)