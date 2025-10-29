CODEGEN_PROMPT = """
Your task is to write a Python script using the `schemdraw` library to draw a circuit diagram based on the provided concept.
You must imitate the style and API usage from the provided examples.

**Circuit Idea to Implement:**
{circuit_idea}

**High-Quality Examples (Your goal is to write code like this):**
{few_shot_examples}

**Final Output Requirements:**
- The script must save the drawing to a file named 'circuit_diagram.svg'.
- Your output must be ONLY the Python code, enclosed in a single ```python ... ``` block. No explanations.
"""