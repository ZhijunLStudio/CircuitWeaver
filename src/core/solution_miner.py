# src/core/solution_miner.py
import re
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
        )
        self.kb_manager = KnowledgeBaseManager()

    def mine_and_save_solution(self, failed_code: str, error_message: str, successful_code: str):
        print("⛏️ Mining for solution pattern...")
        core_error = error_message.strip().split('\n')[-1]
        
        prompt = f"""
You are a code analysis AI. Your task is to extract the core problem and its solution from the provided code diff.

**FAILED CODE SNIPPET:**
```python
{failed_code}
```

**ERROR MESSAGE:**
```
{error_message}
```

**SUCCESSFUL CODE SNIPPET:**
```python
{successful_code}
```

Based on the difference between the failed and successful code, and the error message, answer the following two questions in plain text.
1.  **Error Pattern**: Summarize the core error in one concise line. This will be used as a database key. Example: `AttributeError: module 'schemdraw.elements' has no attribute 'Vcc'`.
2.  **Solution Summary**: Describe the general solution in one or two sentences. Do NOT include code. Example: "The power supply element 'Vcc' is incorrect. The correct element in schemdraw is 'elm.Vdd'."

**YOUR RESPONSE (must be in this exact format):**
Error Pattern: [Your one-line summary here]
Solution Summary: [Your one-to-two sentence summary here]
"""
        
        messages = [
            SystemMessage(content="You are a precise code analysis assistant."),
            HumanMessage(content=prompt)
        ]
        
        try:
            response = self.llm.invoke(messages).content
            error_pattern_match = re.search(r"Error Pattern: (.*)", response)
            solution_summary_match = re.search(r"Solution Summary: (.*)", response, re.DOTALL)
            
            if error_pattern_match and solution_summary_match:
                error_pattern = error_pattern_match.group(1).strip()
                solution_summary = solution_summary_match.group(1).strip()
                
                if error_pattern and solution_summary:
                    self.kb_manager.add_solution(error_pattern, solution_summary)
                else:
                    print("Could not extract a valid pattern/solution from LLM response.")
            else:
                print(f"Could not parse solution from LLM response:\n{response}")

        except Exception as e:
            print(f"An error occurred during solution mining: {e}")

