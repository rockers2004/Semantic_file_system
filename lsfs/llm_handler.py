import requests
import json
from typing import List, Dict, Any, Optional


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

class OllamaHandler: 
    """Handles interaction with local Ollama LLM"""
    
    def __init__(self, model:  str, base_url: str):
        self.model = model
        self.base_url = base_url. rstrip('/')
        self.api_url = f"{self.base_url}/api/generate"
        self.chat_url = f"{self.base_url}/api/chat"
        # Allow slower local models without timing out
        self.request_timeout = 120
        
        print(f"🤖 Connecting to Ollama:  {model} at {base_url}")
        
        # Test connection
        if not self._test_connection():
            raise ConnectionError(f"❌ Cannot connect to Ollama at {base_url}")
        
        print("✅ Ollama connected!")
    
    def _test_connection(self) -> bool:
        """Test if Ollama is running"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except: 
            return False
    
    def parse_command(self, user_input: str) -> Dict[str, Any]:
        """Parse natural language command using LLM"""
        
        system_prompt = """You are a file system command parser. Parse the user's natural language command into a structured JSON response. 

Available operations:
- create_file: Create a new file (params: file_name, content)
- create_dir: Create a directory (params: dir_name)
- write: Write/append content to a file (params:  file_name, content, append)
- read: Read a file (params: file_name)
- search: Search files semantically (params: query, k, keywords)
- list: List files in directory (params: subdir)
- delete: Delete a file/directory (params: file_name)
- move: Move/rename a file (params: source, destination)
- copy: Copy a file (params: source, destination)
- reindex: Re-index all files (no params)
- stats: Show system statistics (no params)
- categorize: Group and display files by type (no params)

Return ONLY valid JSON in this format:
{
    "operation": "operation_name",
    "parameters": {
        "param1": "value1",
        "param2": "value2"
    },
    "confidence": 0.95
}

Examples:
User: "create a file called notes.txt"
{"operation": "create_file", "parameters": {"file_name": "notes.txt"}, "confidence": 0.9}

User: "write 'hello world' to test.txt"
{"operation": "write", "parameters": {"file_name": "test.txt", "content": "hello world"}, "confidence": 0.9}

User: "search for files about machine learning"
{"operation":  "search", "parameters": {"query": "machine learning", "k":  5}, "confidence": 0.95}

User: "show me all files"
{"operation":  "list", "parameters": {}, "confidence": 0.95}

User: "categorize the files"
{"operation": "categorize", "parameters": {}, "confidence": 0.9}

User: "move report.txt to documents/report.txt"
{"operation": "move", "parameters": {"source":  "report.txt", "destination":  "documents/report.txt"}, "confidence": 0.9}

User: "copy notes.txt to backup/notes.txt"
{"operation": "copy", "parameters": {"source": "notes.txt", "destination": "backup/notes.txt"}, "confidence": 0.9}

User: "delete old_file.txt"
{"operation": "delete", "parameters": {"file_name": "old_file.txt"}, "confidence": 0.9}"""

        try:
            # Call Ollama
            response = requests.post(
                self.chat_url,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_input}
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 250
                    }
                },
                timeout=self.request_timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['message']['content'].strip()
                
                # Extract JSON from response robustly
                json_str = _extract_first_json_block(content)
                if json_str:
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError as e:
                        return {"operation": "error", "parameters": {"message": f"Parse error: {e}"}, "confidence": 0.0}
                else:
                    return {"operation": "error", "parameters": {"message": "No JSON found in LLM response"}, "confidence": 0.0}
            
            return {"operation": "error", "parameters": {"message": "LLM request failed"}, "confidence": 0.0}
        
        except Exception as e:
            print(f"❌ LLM parsing error: {e}")
            return {"operation": "error", "parameters": {"message": str(e)}, "confidence": 0.0}
    
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