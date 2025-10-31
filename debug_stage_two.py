# debug_stage_two.py
import os
import argparse
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor

# Add project root to path to allow imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# --- KEY FIX: Import ALL necessary initializers in the correct order ---
from src.tools.documentation_search_tool import init_embedding_model, init_doc_retriever
from src.core.success_code_manager import init_success_code_manager
from src.core.visual_orchestrator import VisualOrchestrator
from configs import settings

def main():
    parser = argparse.ArgumentParser(description="Standalone debugger for Stage 2 Visual Correction.")
    parser.add_argument(
        "job_dir",
        type=str,
        help="Path to a completed Stage 1 job directory (e.g., results/2025-10-31...)"
    )
    args = parser.parse_args()

    # --- KEY FIX: Pre-initialize all shared resources in the CORRECT ORDER ---
    print("Pre-initializing all shared resources...")
    try:
        # Step 1: Initialize the most foundational resource first.
        init_embedding_model()
        
        # Step 2: Initialize resources that depend on the embedding model.
        init_doc_retriever()
        init_success_code_manager()
        
        print("✅ All shared resources initialized successfully.\n")
    except Exception as e:
        print(f"FATAL: Failed to initialize shared resources: {e}")
        traceback.print_exc()
        return

    if not os.path.isdir(args.job_dir):
        print(f"Error: Directory not found at '{args.job_dir}'")
        return

    # --- Find the necessary input files ---
    code_path = os.path.join(args.job_dir, "final_successful_code.py")
    svg_path = os.path.join(args.job_dir, "final_successful_diagram.svg")
    idea_path = os.path.join(args.job_dir, "1_circuit_idea.txt")

    if not all(os.path.exists(p) for p in [code_path, svg_path, idea_path]):
        print("Error: The provided job directory is incomplete. Missing one of:")
        print("- final_successful_code.py")
        print("- final_successful_diagram.svg")
        print("- 1_circuit_idea.txt")
        return

    # --- Load the inputs ---
    with open(code_path, 'r', encoding='utf-8') as f:
        initial_code = f.read()
    with open(idea_path, 'r', encoding='utf-8') as f:
        circuit_idea = f.read()
        
    print("--- Inputs Loaded ---")
    print(f"Job Directory: {args.job_dir}")
    print(f"Circuit Idea: {circuit_idea[:100]}...")
    print("----------------------")

    with ThreadPoolExecutor() as async_pool:
        try:
            job_id_str = os.path.basename(args.job_dir.strip(os.sep)).split('_')[2]
        except IndexError:
            job_id_str = "debug"

        visual_orchestrator = VisualOrchestrator(
            job_id=job_id_str,
            base_results_dir=args.job_dir,
            async_pool=async_pool
        )
        
        final_code = visual_orchestrator.run(
            initial_code=initial_code,
            initial_svg_path=svg_path,
            circuit_idea=circuit_idea
        )

    # --- Save the final visually corrected code ---
    final_code_path = os.path.join(args.job_dir, "final_visually_corrected_code.py")
    with open(final_code_path, 'w', encoding='utf-8') as f:
        f.write(final_code)
        
    print("\n--- Visual Correction Complete ---")
    print(f"Final, visually corrected code saved to: {final_code_path}")

if __name__ == "__main__":
    main()