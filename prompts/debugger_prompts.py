# prompts/debugger_prompts.py

def get_debug_prompt(failed_code: str, error_message: str, rag_context: str) -> str:
    """创建一个包含 RAG 上下文和反思指令的调试提示。"""
    prompt = f"""
The Python script I am trying to fix has failed.

**LAST FAILED CODE THAT I AM DEBUGGING:**
```python
{failed_code}
```

**RESULTING ERROR MESSAGE:**
```
{error_message}
```
"""
    # 只有当 RAG 找到了有效信息时，才添加这部分
    if rag_context and "No relevant documentation found." not in rag_context:
        prompt += f"""
**CONTEXT: I searched the official documentation and our past successful solutions. This information is your best guide to find the correct API usage:**
---
{rag_context}
---
"""
    
    # <<< KEY CHANGE >>>
    # The conversation history will now contain a detailed failure summary from the previous attempt.
    # This prompt primes the model to look for it and use it.
    prompt += """
**YOUR TASK: ADVANCED COLLECTIVE DEBUGGING**

You are part of a team of AI models. In the previous turn (visible in the conversation history), your team attempted to fix this problem, but all attempts failed. You will see a summary of those failures.

1.  **ANALYZE ALL PREVIOUS FAILURES**: Carefully review the summary of failed attempts from your AI teammates in the last turn. Understand *why* each of them failed.
2.  **DO NOT REPEAT ANY MISTAKES**: You MUST generate a solution that avoids every single error pattern identified in the previous failed attempts.
3.  **SYNTHESIZE A NOVEL SOLUTION**: Based on the context hints AND the lessons learned from all previous failures, formulate a new, fundamentally different approach to solve the problem.
4.  **REWRITE THE ENTIRE SCRIPT** with your new, superior solution.

Your output must ONLY be the corrected Python code inside a single ```python ... ``` block.
"""
    return prompt
