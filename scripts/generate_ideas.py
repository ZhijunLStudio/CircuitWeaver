import os
import sys
import shutil
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

# --- Setup Project Path ---
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from configs import models

# --- Configuration ---
# 你的原始、纯代码文件存放的地方
SOURCE_CODE_DIR = "seed_circuits_source" 
# 脚本将自动创建这个文件夹，并填充好 source.py 和 idea.txt
OUTPUT_SEED_DIR = "seed_circuits" 
# 你希望并发处理的数量
MAX_WORKERS = 8

# --- Prompt for the LLM ---
IDEA_GENERATION_PROMPT = """
You are an expert technical writer specializing in `schemdraw`.
Your task is to analyze the following Python script and generate a concise, high-level description of the block diagram or flowchart it creates. This description will be used for semantic search, so it should capture the essence of the diagram's purpose and structure.

**Key things to include in your description:**
- The overall type of diagram (e.g., "RF receiver front-end," "digital filter structure," "simple process flowchart").
- The main components or stages involved (e.g., "LNA, Mixer, and IF Filter," "decision nodes and processes").
- The general signal or process flow.
- Keep the description to 2-4 sentences.

**Python Code:**
```python
{code}
```

**CRITICAL:** Your output MUST be ONLY the plain text description. Do not include markdown headings, bullet points, or any other formatting. Just the raw text.
"""

def process_file(filepath: str, llm: ChatOpenAI):
    """
    Reads a Python file, sends it to an LLM to generate an idea, 
    and returns the code and the generated idea.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
        
        prompt = IDEA_GENERATION_PROMPT.format(code=code)
        response = llm.invoke([HumanMessage(content=prompt)])
        idea = response.content.strip()
        
        return code, idea
    except Exception as e:
        print(f"Error processing file {filepath}: {e}")
        return None, None

def main():
    print("--- Automating Idea Generation for Seed Circuits ---")

    if not os.path.exists(SOURCE_CODE_DIR):
        print(f"Error: Source directory '{SOURCE_CODE_DIR}' not found.")
        print("Please create it and place your .py files inside.")
        return

    if os.path.exists(OUTPUT_SEED_DIR):
        print(f"Warning: Output directory '{OUTPUT_SEED_DIR}' already exists. It will be overwritten.")
        shutil.rmtree(OUTPUT_SEED_DIR)
    os.makedirs(OUTPUT_SEED_DIR, exist_ok=True)

    llm = ChatOpenAI(
        model=models.MULTI_MODAL_MODEL, # Using your specified powerful model
        api_key=models.API_KEY,
        base_url=models.BASE_URL
    )

    py_files = [os.path.join(SOURCE_CODE_DIR, f) for f in os.listdir(SOURCE_CODE_DIR) if f.endswith('.py')]
    if not py_files:
        print(f"No Python files found in '{SOURCE_CODE_DIR}'.")
        return

    print(f"Found {len(py_files)} Python files. Generating ideas concurrently with {MAX_WORKERS} workers...")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # We pass the llm object to each worker
        results = list(tqdm(executor.map(lambda f: process_file(f, llm), py_files), total=len(py_files)))

    successful_count = 0
    for filepath, (code, idea) in zip(py_files, results):
        if code and idea:
            base_name = os.path.splitext(os.path.basename(filepath))[0]
            example_dir = os.path.join(OUTPUT_SEED_DIR, f"example_{base_name}")
            os.makedirs(example_dir, exist_ok=True)
            
            with open(os.path.join(example_dir, "source.py"), 'w', encoding='utf-8') as f:
                f.write(code)
            with open(os.path.join(example_dir, "idea.txt"), 'w', encoding='utf-8') as f:
                f.write(idea)
            
            successful_count += 1
            
    print(f"\n✅ Generation complete! Successfully created {successful_count} structured examples in '{OUTPUT_SEED_DIR}'.")
    print("You can now run 'python scripts/seed_success_repo.py' to build the knowledge base.")


if __name__ == "__main__":
    main()
