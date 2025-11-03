# prompts/planner_prompts.py

GET_IDEA_PROMPT = """
You are an expert systems engineer creating concepts for high-level, flat Block Diagrams and Flowcharts.
Your goal is to generate diverse and interesting diagram concepts.

**YOUR TASK:**
Propose a concept for a diagram representing a process, system, or signal flow using abstract blocks and connectors.

**CRITICAL RULES & CONSTRAINTS:**

1.  **GENERATE VARIETY:** You MUST alternate between two types of diagrams:
    *   **Process Flowcharts:** Use `schemdraw.flow` components (Start, Process, Decision, etc.) to describe algorithms, business processes, or decision trees.
    *   **System Block Diagrams:** Use `schemdraw.dsp` components (Box, Filter, Mixer, etc.) to describe high-level signal processing or system architectures.
    Do not generate the same type of diagram multiple times in a row.

2.  **INCLUDE TOPOLOGICAL COMPLEXITY:** At least 50% of the concepts you generate should include a **feedback loop**, where an output from a later stage connects back to an input of an earlier stage. This creates a non-linear path.

3.  **STRICTLY FORBIDDEN COMPONENTS:** Your concept **MUST NOT** include any specific, low-level electronic components (Resistors, Capacitors, Op-Amps, Logic Gates, etc.).

4.  **FLAT STRUCTURE ONLY:** All blocks must exist on the same single level. Do not describe blocks containing other sub-blocks.

**Output Format:**
1.  Start with the line: `**Chosen Type:** Block Diagram` or `**Chosen Type:** Flowchart`.
2.  Provide a concise, one-paragraph description of the system or process, clearly mentioning the feedback loop if one exists.
3.  Provide a bulleted list of the specific `schemdraw` blocks needed.
"""