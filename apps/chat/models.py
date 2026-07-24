import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

class RouterAgent:
    def __init__(self, system_prompt="", reasoning=False):
        self.reasoning = reasoning
        self.system_prompt = {"role": "system", "content": system_prompt}
    
    def run(self, prompt: str, history: list):
      messages = [
        *history,
        self.system_prompt,
        {"role": "user", "content": prompt}
      ]

      resp = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
          "Authorization": f"Bearer {os.getenv('Router_API')}",
          "Content-Type": "application/json",
        },
        data=json.dumps({
          "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
          "messages": messages, 
          "response_format": {"type": "json_object"},
          "reasoning": {"enabled": self.reasoning}
        })
      ).json()

      try:
        return resp['choices'][0]['message'].get('content')
      except Exception as e:
        print(f"Error in LLM call: {resp}")
        raise e
          
    

class ChatAgent:
    def __init__(self, system_prompt="", reasoning=True):
        self.reasoning = reasoning
        self.system_prompt = {"role": "system", "content": system_prompt}
    
    def run(self, prompt: str, history: list):
      messages = [
        *history,
        self.system_prompt,
        {"role": "user", "content": prompt}
      ]

      resp = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
          "Authorization": f"Bearer {os.getenv('Chat_API')}",
          "Content-Type": "application/json",
        },
        data=json.dumps({
          "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
          "messages": messages, 
          "stream": True,
          "reasoning": {"enabled": self.reasoning}
        }),
        stream=True
      )

      for line in resp.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith("data: ") and line != "data: [DONE]":
                    try:
                        chunk = json.loads(line[6:])
                        choices = chunk.get('choices', [])
                        
                        if choices:
                            content = choices[0].get('delta', {}).get('content', '')
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue
                    

if __name__ == "__main__":
  router = RouterAgent()
  print(router.run("what is the capital of france?", {}))






        