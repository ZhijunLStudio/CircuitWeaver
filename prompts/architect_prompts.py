# prompts/architect_prompts.py

GENERATE_PSEUDOCODE_PROMPT = """
You are an expert `schemdraw` layout designer and router. Your task is to convert a diagram concept into a high-level, step-by-step **"pseudocode" plan**. This plan MUST use a flow-based, relative layout philosophy and create clean, orthogonal (90-degree) connections.

**DIAGRAM CONCEPT:**
---
{circuit_idea}
---

**CRITICAL INSTRUCTIONS:**

1.  **THINK LIKE A HUMAN ROUTER:** Plan the drawing steps as if you were drawing it manually, one element at a time.
2.  **USE RELATIVE POSITIONING:** Your plan MUST rely on relative placement using element anchors. Do NOT use absolute (x, y) coordinates.
3.  **ORTHOGONAL ROUTING IS MANDATORY:** When connecting two points that are not on the same horizontal or vertical line, you **MUST** create a 90-degree "L-shaped" or "Z-shaped" path. Do NOT use a direct diagonal connection.

**PSEUDOCODE COMMANDS:**

*   **Placement:**
    *   `CREATE [id] = [type](label='...')`
    *   `PLACE [id]` (for the first element)
    *   `PLACE [id] AT [other_id].[anchor] [direction] [distance]` (e.g., `PLACE mixer AT lna.E right 1.5*unit`)

*   **Connection (Routing):**
    *   `CONNECT [from_id].[anchor] TO [to_id].[anchor] WITH [Line/Arrow]`: **Use ONLY if the points are already aligned** horizontally or vertically.
    *   `CONNECT [from_id].[anchor] TO [to_id].[anchor] WITH L_ROUTED_ARROW (label='...')`: **Use for all other cases.** This command signifies an L-shaped, orthogonal connection. The Coder AI will figure out the intermediate point.

**EXAMPLE PSEUDOCODE WITH ROUTING:**
1. CREATE start = flow.Start(label='Start')
2. PLACE start
3. CREATE step1 = flow.Process(label='Step 1')
4. PLACE step1 AT start.S down 2*unit
5. CONNECT start.S TO step1.N WITH Arrow
6. CREATE side_process = flow.Process(label='Side Task')
7. PLACE side_process AT step1.E right 3*unit
8. CREATE feedback_sum = dsp.Sum()
9. PLACE feedback_sum AT start.W left 3*unit
10. # This is a non-aligned connection, so use L_ROUTED_ARROW
11. CONNECT side_process.S TO feedback_sum.E WITH L_ROUTED_ARROW (label='Feedback')

Now, generate the pseudocode plan for the provided diagram concept, ensuring all non-aligned connections use `L_ROUTED_ARROW`.
"""