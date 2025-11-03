# prompts/architect_prompts.py

GENERATE_JSON_BLUEPRINT_PROMPT = """
You are a meticulous Systems Architect AI. Your task is to convert a high-level diagram concept into a precise, structured JSON "blueprint". This blueprint defines all components and their logical connections (the netlist).

**DIAGRAM CONCEPT:**
---
{circuit_idea}
---

**REFERENCE EXAMPLES (for structure and component names):**
---
{reference_examples_code}
---

**INSTRUCTIONS:**
1.  **Identify Components & Assign IDs:** Identify every block and give it a unique ID (e.g., "start_node", "filter_1").
2.  **Define Connections:** Specify the exact connections between components using standard anchor points (`N`, `S`, `E`, `W`, etc.).
3.  **MODEL FEEDBACK LOOPS:** If the concept describes a feedback loop, the `connections` list **must** include an entry where the `from` component appears later in the main flow than the `to` component. This is critical.
4.  **Format as JSON:** Your output **MUST** be a single, valid JSON object with `components` and `connections` keys.

**JSON BLUEPRINT SPECIFICATION:**
-   `components`: An object where each key is the unique component ID. The value is an object with `type` and optional `label`.
-   `connections`: A list of objects representing wires/arrows, each with `from`, `to`, and optional `label`.

**EXAMPLE OUTPUT WITH A FEEDBACK LOOP:**
```json
{{
  "components": {{
    "input_src": {{ "type": "dsp.Box", "label": "Input" }},
    "processor": {{ "type": "dsp.Box", "label": "Processor" }},
    "summer": {{ "type": "dsp.Sum", "label": "" }},
    "output_sink": {{ "type": "dsp.Box", "label": "Output" }}
  }},
  "connections": [
    {{ "from": "input_src.E", "to": "summer.W" }},
    {{ "from": "summer.E", "to": "processor.W" }},
    {{ "from": "processor.E", "to": "output_sink.W" }},
    {{ "from": "processor.E", "to": "summer.S", "label": "- Feedback" }}
  ]
}}
```

Now, generate the JSON blueprint for the provided diagram concept.
"""