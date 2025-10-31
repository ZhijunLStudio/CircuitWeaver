PLANNING_PROMPT = """
You are an expert `schemdraw` designer. Your first task is to create a high-level plan for a circuit diagram based on the user's idea.
You must analyze the provided examples to understand good layout practices.

**User's Circuit Idea:**
{circuit_idea}

---
**Reference Examples (Code Only):**
These examples show valid syntax and structure.
{reference_examples_code}
---

**YOUR TASK:**
Based on the user's idea, create a detailed, structured plan for the diagram. The plan should be in a markdown format.
Describe the following:
1.  **Overall Layout Strategy:** A brief sentence on the flow (e.g., "Left-to-right signal flow, power on top, ground at bottom.").
2.  **Component List:** A list of all necessary `schemdraw` elements.
3.  **Connection Netlist:** A precise list of connections, specifying which anchor of which component connects to another (e.g., "- R1.end to C1.start").
4.  **Labeling Plan:** A list of all labels and where they should be placed to avoid overlaps (e.g., "- '10kΩ' near R1, positioned top.").

**Do NOT write any Python code.** Your output must be only the markdown-formatted plan.
"""

CODEGEN_FROM_PLAN_PROMPT = """
You are a `schemdraw` code generation specialist. Your task is to translate a detailed plan into a perfect Python script.
You have been provided with images of well-designed circuits as a visual style guide. Your generated diagram should visually resemble the style of these examples.

**User's Original Circuit Idea:**
{circuit_idea}

---
**Execution Plan (You MUST follow this plan exactly):**
{execution_plan}
---

**CRITICAL INSTRUCTIONS:**
1.  **Adhere to the Plan:** Your Python code must implement every component, connection, and label specified in the Execution Plan.
2.  **Visual Style:** The final diagram should be clean, well-aligned, and un-cluttered, similar to the provided reference images.
3.  **Save the File:** The script MUST save the output to a file named 'circuit_diagram.svg'. Use `with schemdraw.Drawing(file='circuit_diagram.svg') as d:`.
4.  **Output Format:** Your response must be ONLY the complete Python script, enclosed in a single ```python ... ``` block. No explanations.
"""