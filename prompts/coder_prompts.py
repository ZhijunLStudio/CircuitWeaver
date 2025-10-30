# prompts/coder_prompts.py

CODEGEN_PROMPT = """
Your task is to write a Python script using the `schemdraw` library to draw a circuit diagram based on the provided concept.

**Circuit Idea to Implement:**
{circuit_idea}

---
**STYLE GUIDE (Your code should follow the style of this example):**
{few_shot_examples}
---
**RELEVANT PAST SUCCESSES (These are full code examples from similar, successfully completed tasks. Use them for inspiration and structure):**
{successful_examples}
---

**CRITICAL FINAL REQUIREMENTS:**
1.  Your script MUST save the final drawing to a file named 'circuit_diagram.svg'.
2.  Your output must be ONLY the Python code, enclosed in a single ```python ... ``` block. Do not include any text or explanations.
"""