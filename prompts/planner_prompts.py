# prompts/planner_prompts.py

# This prompt is now much simpler. It just fills in a template.
GET_IDEA_PROMPT = """
You are a creative systems engineer. Your task is to take a high-level diagram category and description, and flesh it out into a more concrete and interesting concept.

**Diagram Category:**
{category}

**High-Level Description:**
{description}

**YOUR TASK:**
Based on the provided category and description, write a detailed, one-paragraph concept.
- Give the system a specific, imaginative name (e.g., "A Simple AGC Loop," "A User Login Flow," "A Microcontroller to RAM Interface").
- Describe the specific blocks and the signal/data flow between them in a clear, narrative style.
- The total number of blocks should be between 5 and 8.

**Output Format:**
Your output should be ONLY the detailed, one-paragraph concept. Do not repeat the category or description.
"""