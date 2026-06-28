"""
slpfs/llm_handler.py

Ollama LLM Integration Layer for Local SLPFS

Provides the language-model interface used by the semantic file system.
This module is responsible for:

- Connecting to and validating a local Ollama service
- Translating natural-language user input into structured file-system commands
- 
- Generating friendly natural-language summaries of operation results

Primary components:
   - _extract_first_json_block: Safely finds the first balanced JSON object in text
   - OllamaHandler: Wrapper around Ollama /api/chat and /api/generate endpoints,
     with timeout handling, error normalization, and response parsing

Design notes:
   - Local-first operation (no cloud dependency assumed)
   - Defensive parsing to tolerate non-JSON text around model outputs
   - Returns structured error objects when parsing or requests fail
   
"""
import json
import logging
from typing import  Dict, Any, Optional
import requests


logger = logging.getLogger(__name__)

EXPLICIT_OPERATION_PREFIXES = {
    "create_file",
    "create_dir",
    "write",
    "read",
    "search",
    "list",
    "delete",
    "move",
    "copy",
    "reindex",
    "stats",
    "chat",
}


def _extract_first_json_block(text: str) -> Optional[str]:
    """Extract the first balanced JSON object from text."""
    start = text.find('{')
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _extract_explicit_operation(text: str) -> tuple[Optional[str], str]:
    """Return an exact operation token when the input starts with one."""
    stripped = text.strip()
    if not stripped:
        return None, ""

    first_token, _, remainder = stripped.partition(" ")
    normalized = first_token.rstrip(":").lower()
    if normalized in EXPLICIT_OPERATION_PREFIXES:
        return normalized, remainder.strip()

    return None, stripped

class OllamaHandler: 
    """Handles interaction with local Ollama LLM"""
    
    def __init__(self, model:  str, base_url: str):
        self.model = model
        self.base_url = base_url. rstrip('/')
        self.api_url = f"{self.base_url}/api/generate"
        self.chat_url = f"{self.base_url}/api/chat"
        # Allow slower local models without timing out
        self.request_timeout = 120
        
        logger.info("Connecting to Ollama: %s at %s", model, base_url)
        
        # Test connection
        if not self._test_connection():
            raise ConnectionError(f"Cannot connect to Ollama at {base_url}")
        
        logger.info("Ollama connected")
    
    def _test_connection(self) -> bool:
        """Test if Ollama is running"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except requests.RequestException: 
            return False
    
    def _call_llm(self, system_prompt: str, user_content: str, temperature: float = 0.05) -> Optional[dict]:
        """Send a chat request to Ollama and return the parsed response dict, or None on failure."""
        try:
            response = requests.post(
                self.chat_url,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": 300,
                    },
                },
                timeout=self.request_timeout,
            )
            if response.status_code != 200:
                logger.error("LLM request failed: status=%s body=%s", response.status_code, response.text.strip())
                return None
            result = response.json()
            content = result.get("message", {}).get("content", "").strip()
            if not content:
                return None
            json_str = _extract_first_json_block(content)
            if not json_str:
                return None
            parsed = json.loads(json_str)
            if not isinstance(parsed, dict):
                return None
            parsed["raw_ollama_output"] = content
            return parsed
        except Exception as exc:
            logger.exception("LLM call error: %s", exc)
            return None

    def parse_command(self, user_input: str) -> Dict[str, Any]:
        """Parse natural language command using LLM, with retry on JSON failure."""
        forced_operation, remaining_input = _extract_explicit_operation(user_input)
        forced_operation_block = ""
        if forced_operation:
            forced_operation_block = f"""

Explicit operation prefix detected:
- The user's first token is exactly "{forced_operation}".
- You MUST return operation "{forced_operation}".
- Interpret the remaining text as arguments for that operation.
- Do not change it to another operation unless the remaining text is empty and the selected operation can reasonably run without parameters.
"""

        system_prompt = f"""You are a file system command parser. Parse the user's natural language command into a structured JSON response.

Available operations:
- search: Search files semantically (params: query, k, keywords)
- create_file: Create a new file (params: file_name, content)
- create_dir: Create a directory (params: dir_name)
- write: Write/append content to a file (params: file_name, content, append)
- read: Read a file (params: file_name)
- list: List files in directory (params: subdir)
- delete: Delete a file/directory (params: file_name)
- move: Move/rename a file (params: source, destination)
- copy: Copy a file (params: source, destination)
- reindex: Re-index all files (no params)
- stats: Show system statistics (no params)
- chat: Normal conversation/small talk/non-filesystem query (params: message)

Important rules:
- If the user is asking a question, looking for information, or describing something they want to find, ALWAYS use "search". This is the most common case.
- If the user uses words like "find", "search", "look for", "show", "get", "where is", "do you have", "find me", "show me" followed by a topic, use "search".
- Even without those keywords, if the input looks like a search query (e.g., "python tutorial", "meeting notes", "invoice pdf"), use "search".
- ONLY use "chat" for pure greetings, small talk, or general knowledge questions unrelated to files.
- Do NOT use "chat" for queries that could be file searches.
{forced_operation_block}

Return ONLY valid JSON in this format:
{{
    "operation": "operation_name",
    "parameters": {{
        "param1": "value1",
        "param2": "value2"
    }},
    "confidence": 0.95
}}

Examples:
User: "find me files about machine learning"
{{"operation": "search", "parameters": {{"query": "machine learning", "k": 5}}, "confidence": 0.95}}

User: "show me python scripts"
{{"operation": "search", "parameters": {{"query": "python scripts", "k": 5}}, "confidence": 0.95}}

User: "where is my resume"
{{"operation": "search", "parameters": {{"query": "resume", "k": 5}}, "confidence": 0.95}}

User: "pictures from my trip"
{{"operation": "search", "parameters": {{"query": "trip pictures", "k": 5}}, "confidence": 0.95}}

User: "create a file called notes.txt"
{{"operation": "create_file", "parameters": {{"file_name": "notes.txt"}}, "confidence": 0.9}}

User: "write 'hello world' to test.txt"
{{"operation": "write", "parameters": {{"file_name": "test.txt", "content": "hello world"}}, "confidence": 0.9}}

User: "search for files about machine learning"
{{"operation": "search", "parameters": {{"query": "machine learning", "k": 5}}, "confidence": 0.95}}

User: "show me all files"
{{"operation": "list", "parameters": {{}}, "confidence": 0.95}}

User: "move report.txt to documents/report.txt"
{{"operation": "move", "parameters": {{"source": "report.txt", "destination": "documents/report.txt"}}, "confidence": 0.9}}

User: "copy notes.txt to backup/notes.txt"
{{"operation": "copy", "parameters": {{"source": "notes.txt", "destination": "backup/notes.txt"}}, "confidence": 0.9}}

User: "delete old_file.txt"
{{"operation": "delete", "parameters": {{"file_name": "old_file.txt"}}, "confidence": 0.9}}

User: "hello how are you"
{{"operation": "chat", "parameters": {{"message": "Hello! I am doing well. How can I help with your files today?"}}, "confidence": 0.95}}"""

        model_input = user_input
        if forced_operation:
            model_input = (
                f'Explicit operation: "{forced_operation}"\n'
                f'Remaining request: "{remaining_input}"'
            )

        # First attempt
        parsed = self._call_llm(system_prompt, model_input, temperature=0.05)
        if parsed is not None:
            return parsed

        # Retry once with a stricter prompt on failure
        retry_prompt = system_prompt + "\n\nIMPORTANT: You MUST respond with ONLY a valid JSON object. No explanations, no extra text, no markdown. JSON only."
        parsed = self._call_llm(retry_prompt, model_input, temperature=0.01)
        if parsed is not None:
            return parsed

        return {
            "operation": "error",
            "parameters": {"message": "Could not parse command after retry."},
            "confidence": 0.0,
        }
    
    def summarize_results(self, operation: str, results: Any) -> str:
        """Generate natural language summary of results"""
        
        prompt = f"""Summarize this file system operation result in a friendly, concise way (1-2 sentences):

Operation: {operation}
Results:  {json.dumps(results, indent=2)[: 500]}

Be helpful and mention key details like file names, counts, or paths."""

        try:
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 100
                    }
                },
                timeout=self.request_timeout
            )
            
            if response.status_code == 200:
                return response.json()['response'].strip()
            
            return "Operation completed."
        
        except Exception as e: 
            return f"Operation completed:  {results. get('message', 'Success')}"
