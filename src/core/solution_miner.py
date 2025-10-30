# src/core/solution_miner.py
import re
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.db.knowledge_base import KnowledgeBaseManager
from configs import models

class SolutionMiner:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=models.MODEL_FOR_CREATION, # Use a smart model for analysis
            api_key=models.API_KEY,
            base_url=models.BASE_URL,
            temperature=0.0,
            # Request a JSON response from the model
            model_kwargs={"response_format": {"type": "json_object"}},
        )
        self.kb_manager = KnowledgeBaseManager()

    def mine_and_save_from_chain(self, failure_chain: list, successful_code: str):
        if not failure_chain:
            return

        print(f"⛏️ Mining for solutions from a chain of {len(failure_chain)} failures...")
        
        # Format the failure chain for the prompt
        formatted_failures = ""
        for i, (code, error) in enumerate(failure_chain):
            formatted_failures += f"--- Failure #{i+1} ---\n"
            formatted_failures += f"ERROR MESSAGE:\n```\n{error}\n```\n"
            # Optional: Add code snippet for more context, but can make prompt very long
            # formatted_failures += f"FAILED CODE THAT CAUSED IT:\n```python\n{code}\n```\n"

        prompt = f"""
You are an expert code analysis AI. Your task is to analyze a sequence of failures that ultimately led to a successful code fix.
You must identify each unique root cause of error in the failure sequence and provide a general solution for it.

**FAILURE SEQUENCE:**
{formatted_failures}

**SUCCESSFUL CODE THAT FIXED EVERYTHING:**
```python
{successful_code}
```

**INSTRUCTIONS:**
1. Review the entire failure sequence. Identify each distinct error pattern.
2. For each unique error pattern, determine the general solution based on the final successful code.
3. Your output MUST be a JSON object containing a single key "solutions", which is a list of objects.
4. Each object in the list must have two keys: "error_pattern" (a one-line summary of the error) and "solution_summary" (a one-or-two-sentence general solution, without code).
5. Only include solutions for errors that are clearly resolved by the final code. Do not guess.

**EXAMPLE JSON OUTPUT FORMAT:**
{{
  "solutions": [
    {{
      "error_pattern": "ImportError: cannot import name 'opamp' from 'schemdraw'",
      "solution_summary": "The 'opamp' element is not a top-level module. It should be imported from 'schemdraw.elements', typically using 'import schemdraw.elements as elm' and then accessed via 'elm.Opamp'."
    }},
    {{
      "error_pattern": "AttributeError: 'BBox' object has no attribute 'y1'",
      "solution_summary": "The bounding box object 'BBox' in schemdraw uses 'ymin' and 'ymax' attributes to define its vertical boundaries, not 'y1' or 'y2'."
    }}
  ]
}}
"""
        
        messages = [
            SystemMessage(content="You are a precise code analysis assistant that outputs structured JSON."),
            HumanMessage(content=prompt)
        ]
        
        try:
            response = self.llm.invoke(messages).content
            solution_data = json.loads(response)
            
            if "solutions" in solution_data and isinstance(solution_data["solutions"], list):
                if not solution_data["solutions"]:
                    print("⛏️ Miner LLM returned no distinct solutions from the chain.")
                    return

                for solution in solution_data["solutions"]:
                    if "error_pattern" in solution and "solution_summary" in solution:
                        self.kb_manager.add_solution(
                            solution["error_pattern"],
                            solution["solution_summary"]
                        )
                    else:
                        print(f"Warning: Malformed solution object found: {solution}")
                print(f"🧠 Successfully mined and saved {len(solution_data['solutions'])} new solutions from the chain.")
            else:
                print(f"Could not parse a valid 'solutions' list from LLM JSON response: {response}")

        except json.JSONDecodeError:
            print(f"Error: Failed to decode JSON from LLM response:\n{response}")
        except Exception as e:
            print(f"An error occurred during multi-step solution mining: {e}")