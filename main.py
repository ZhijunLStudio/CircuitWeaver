import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import traceback

# --- KEY FIX: Import the finest-grained initializers ---
from src.tools.documentation_search_tool import init_embedding_model, init_doc_retriever
from src.core.success_code_manager import init_success_code_manager
# NEW: Import the new initializer for the example retriever
from src.tools.example_retriever_tool import init_example_retriever
from src.core.orchestrator import CircuitWeaverOrchestrator
from configs import settings

# --- Worker and main loop functions remain unchanged ---
stop_event = threading.Event()
job_counter = 0

def run_orchestrator_instance(job_id: int, async_pool):
    """Function to be run by each worker."""
    if stop_event.is_set():
        print(f"[Job {job_id}] Received stop signal before starting. Aborting.")
        return

    print(f"\n--- 🚀 Starting Job #{job_id} ---")
    start_time = time.time()
    try:
        orchestrator = CircuitWeaverOrchestrator(job_id=job_id, async_pool=async_pool)
        orchestrator.run()
    except Exception as e:
        print(f"🚨 FATAL ERROR in Job #{job_id}: {e}")
        traceback.print_exc()
    finally:
        end_time = time.time()
        print(f"--- ✅ Job #{job_id} Finished in {end_time - start_time:.2f} seconds ---")

def main_loop(max_jobs: int, num_workers: int):
    """Main loop to submit and manage jobs."""
    global job_counter
    
    with ThreadPoolExecutor(max_workers=num_workers * 2, thread_name_prefix="SolutionMiner") as async_task_pool:
        with ThreadPoolExecutor(max_workers=num_workers, thread_name_prefix="CircuitAgent") as main_executor:
            futures = set()
            initial_job_count = min(num_workers, max_jobs if max_jobs > 0 else num_workers)
            for i in range(initial_job_count):
                job_counter += 1
                future = main_executor.submit(run_orchestrator_instance, job_counter, async_task_pool)
                futures.add(future)

            print(f"🏭 Agent Factory started with {len(futures)} initial workers.")
            print(f"🎯 Target: {'Infinite' if max_jobs == 0 else max_jobs} jobs.")
            print("Press Ctrl+C to stop gracefully...")

            try:
                while futures and not stop_event.is_set():
                    for future in as_completed(futures):
                        futures.remove(future)
                        if stop_event.is_set(): break
                        if max_jobs != 0 and job_counter >= max_jobs: continue
                        
                        job_counter += 1
                        new_future = main_executor.submit(run_orchestrator_instance, job_counter, async_task_pool)
                        futures.add(new_future)
            except KeyboardInterrupt:
                print("\n🛑 Ctrl+C received. Initiating graceful shutdown...")
                stop_event.set()
                for f in futures: f.cancel()
            
            for future in as_completed(futures): pass
    print("\n🏭 Agent Factory has shut down.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the CircuitWeaver Agent Factory.")
    parser.add_argument("-n", "--num-jobs", type=int, default=10, help="Total jobs to run. 0 for infinite.")
    parser.add_argument("-w", "--workers", type=int, default=2, help="Number of concurrent agents.")
    args = parser.parse_args()

    # --- KEY: Absolutely sequential, fine-grained initialization ---
    print("Pre-initializing all shared resources to prevent deadlocks...")
    try:
        # Step 1: Initialize the heaviest and most foundational resource first.
        init_embedding_model()
        
        # Step 2: Initialize resources that depend on the embedding model.
        init_doc_retriever()
        init_success_code_manager()
        # NEW: Initialize the circuit examples retriever
        init_example_retriever()
        
        print("\n✅ All shared resources initialized successfully.\n")
    except Exception as e:
        print(f"FATAL: Failed to initialize shared resources: {e}")
        traceback.print_exc()
        exit(1)
    
    main_loop(max_jobs=args.num_jobs, num_workers=args.workers)