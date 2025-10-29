# prompts/planner_prompts.py

GET_IDEA_PROMPT = """
You are an expert electronics engineer. Your task is to propose a concept for a circuit diagram that is interesting but not overly complex.

**CRITICAL INSTRUCTIONS:**
1.  **Choose ONE Type**: You must choose ONLY ONE of the following three circuit types for your concept:
    *   **Type A: Pure Block Diagram**: A high-level system diagram using only blocks (like `flow.Box`, `dsp.Box`) and connectors.
    *   **Type B: Hybrid Diagram**: A diagram that mixes high-level blocks with some basic electronic components (like Resistors, Capacitors, Opamps). This is a good choice.
    *   **Type C: Pure Schematic**: A detailed circuit diagram using only basic electronic components.

2.  **Limit Complexity**: The TOTAL number of key components AND blocks in your design must NOT exceed 10. Keep it concise.
3.  **Include Hierarchy (if applicable)**: If it fits naturally, include a simple nested relationship (e.g., one block containing a couple of internal components).

**Output Format:**
1.  Start with a line specifying the chosen type, e.g., `**Chosen Type:** Hybrid Diagram`.
2.  Provide a concise description of the circuit idea.
3.  Provide a bulleted list of the `schemdraw` components/blocks needed (max 10 total).
"""