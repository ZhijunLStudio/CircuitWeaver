# main.py
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse # 用于从命令行接收参数

from src.core.orchestrator import CircuitWeaverOrchestrator
from configs import settings

# --- 全局控制变量 ---
# 使用 threading.Event 来优雅地停止所有工作线程
stop_event = threading.Event()
job_counter = 0

def run_orchestrator_instance(job_id: int, async_pool):
    """
    单个 Agent 工作流的执行函数。
    会检查 stop_event，以便在任务开始前就能停止。
    """
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
    finally:
        end_time = time.time()
        print(f"--- ✅ Job #{job_id} Finished in {end_time - start_time:.2f} seconds ---")

def main_loop(max_jobs: int, num_workers: int):
    """
    主循环，持续不断地向线程池提交任务。
    
    Args:
        max_jobs (int): 要生成的电路总数。如果为 0，则无限生成。
        num_workers (int): 并发运行的 Agent 数量。
    """
    global job_counter
    
    # 这个线程池用于异步挖掘解决方案，在所有 Agent 任务之间共享
    with ThreadPoolExecutor(max_workers=num_workers * 2, thread_name_prefix="SolutionMiner") as async_task_pool:
        # 这个线程池用于并发执行 Agent 的主工作流
        with ThreadPoolExecutor(max_workers=num_workers, thread_name_prefix="CircuitAgent") as main_executor:
            
            futures = set()
            
            # 初始提交一批任务，填满工作队列
            for i in range(num_workers):
                if max_jobs != 0 and job_counter >= max_jobs:
                    break
                job_counter += 1
                future = main_executor.submit(run_orchestrator_instance, job_counter, async_task_pool)
                futures.add(future)

            print(f"🏭 Agent Factory started with {num_workers} concurrent workers.")
            print(f"🎯 Target: {'Infinite' if max_jobs == 0 else max_jobs} jobs.")
            print("Press Ctrl+C to stop gracefully...")

            try:
                while not stop_event.is_set():
                    # as_completed 会在任何一个 future 完成时返回它
                    # 这使得我们可以实现一个任务完成后立即补充一个新任务的模式
                    for future in as_completed(futures):
                        # 从集合中移除已完成的 future
                        futures.remove(future)
                        
                        # 检查是否需要停止
                        if stop_event.is_set():
                            break

                        # 检查是否已达到任务上限
                        if max_jobs != 0 and job_counter >= max_jobs:
                            print("🏁 Reached job limit. No more jobs will be submitted.")
                            continue # 不再提交新任务，但会等待现有任务完成
                        
                        # 提交一个新任务来替代刚刚完成的任务
                        job_counter += 1
                        new_future = main_executor.submit(run_orchestrator_instance, job_counter, async_task_pool)
                        futures.add(new_future)
                    
                    # 如果所有任务都完成了 (因为达到了上限)，则退出循环
                    if not futures:
                        break
                        
            except KeyboardInterrupt:
                print("\n🛑 Ctrl+C received. Initiating graceful shutdown...")
                stop_event.set()
                
                # 给正在运行的任务一些时间来完成
                print("Waiting for currently running jobs to finish...")
                # 取消尚未开始的任务
                for f in futures:
                    f.cancel()
            
            # 等待所有剩余的 future 完成（无论它们是成功、失败还是被取消）
            for future in as_completed(futures):
                pass
    
    print("\n🏭 Agent Factory has shut down.")


if __name__ == "__main__":
    # 使用 argparse 来解析命令行参数，增加灵活性
    parser = argparse.ArgumentParser(description="Run the CircuitWeaver Agent Factory.")
    parser.add_argument(
        "-n", "--num-jobs",
        type=int,
        default=0,
        help="Total number of circuits to generate. 0 for infinite. Default is 0."
    )
    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=3,
        help="Number of concurrent agents to run. Default is 3."
    )
    args = parser.parse_args()

    main_loop(max_jobs=args.num_jobs, num_workers=args.workers)