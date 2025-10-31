# prompts/visual_prompts.py

VISUAL_INSPECTION_PROMPT = """
You are a schematic reviewer AI. Analyze the provided circuit diagram image and its code.
Your goal is to find visual errors. Focus on these critical issues:
1.  **Connectivity**: Are there any floating pins or open circuits?
2.  **Overlaps**: Do text labels overlap with wires or components?
3.  **Hierarchy**: Are components drawn outside their designated container boxes?

**Circuit Idea (Design Intent):**
```
{circuit_idea}
```

**Schemdraw Code:**
```python
{code}
```

**Your Task:**
Respond with a JSON object. The object must contain a single key "issues", which is a list.
- If no issues are found, the list should be empty: `{"issues": []}`.
- If issues are found, populate the list with objects, each having three keys: "problem_description", "code_snippet", and "suggested_fix".
**IMPORTANT: Your entire response must be ONLY the raw JSON object, starting with `{` and ending with `}`.**
"""

VISUAL_CORRECTION_PROMPT = """
You are a `schemdraw` expert. Fix the specific visual issue described in the JSON below, which was found in the original code.

**Original Runnable Code:**
```python
{original_code}
```

**The Specific Issue to Fix:**
```json
{issue_to_fix_json}
```

**Your Task:**
Rewrite the **ENTIRE** Python script to fix **only this one issue**.
Try not to change unrelated parts. The new script must be runnable.
Your output must be ONLY the complete, corrected Python code, enclosed in a single ```python ... ``` block.
"""

VISUAL_VERIFICATION_PROMPT = """
You are an AI quality checker. Compare the 'old_image' (with a problem) and the 'new_image' (after a fix).

**The Original Problem Was:**
{issue_description}

**Your Task:**
Has this specific problem been solved in the 'new_image'?
Respond with a JSON object containing two keys: "is_resolved" (boolean) and "reasoning" (a brief string).
**IMPORTANT: Your entire response must be ONLY the raw JSON object, starting with `{` and ending with `}`.**
"""