DEBUGGING_INSTRUCTIONS = """
You are a senior Python developer debugging a `schemdraw` script. Your goal is to produce a script that runs without errors.

**Your Debugging Workflow:**
1.  **Analyze the Error**: Carefully read the `Traceback`.
2.  **Hypothesize**: Form a hypothesis about the cause.
3.  **Use Your Tool**: Use the `documentation_search` tool to verify your hypothesis.
4.  **Implement the Fix**: Rewrite the ENTIRE Python code block with the fix.
"""


def get_debug_prompt(failed_code: str, error_message: str, rag_context: str) -> str:
    """创建一个包含 RAG 上下文的调试提示。"""
    return f"""
        The previous Python script you provided failed to execute.

        **FAILED CODE:**
        ```python
        {failed_code}
        ```

        **ERROR MESSAGE (Traceback):**
        ```
        {error_message}
        ```

        **POSSIBLY RELEVANT DOCUMENTATION (from a vector search on the error):**
        ---
        {rag_context}
        ---

        Your task is to analyze the error, use the provided documentation context to find the correct API usage, and provide a fixed version of the ENTIRE Python script.
        Your output must ONLY be the corrected Python code inside a single ```python ... ``` block. No explanations.
        """