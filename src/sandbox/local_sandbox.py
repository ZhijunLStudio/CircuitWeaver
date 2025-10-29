# src/sandbox/local_sandbox.py
import os
import sys
import multiprocessing
import traceback
import importlib.util
import uuid
from typing import Tuple

def _sandbox_target(code_string: str, result_queue: multiprocessing.Queue, work_dir: str):
    """子进程中运行的目标函数。"""
    # 为每次执行生成唯一的模块名，防止缓存和冲突
    module_name = f"ai_generated_module_{uuid.uuid4().hex}"
    temp_script_path = os.path.join(work_dir, f"{module_name}.py")

    with open(temp_script_path, 'w', encoding='utf-8') as f:
        f.write(code_string)
        
    original_cwd = os.getcwd()
    # 切换工作目录至沙箱目录，确保文件（如SVG）在此生成
    os.chdir(work_dir)

    try:
        spec = importlib.util.spec_from_file_location(module_name, temp_script_path)
        if spec is None:
            raise ImportError(f"无法为 {temp_script_path} 创建模块规范。")
        
        ai_module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = ai_module
        spec.loader.exec_module(ai_module)
        
        # 收集子进程中的 stdout/stderr (如果需要的话，但目前我们只关心traceback)
        result_queue.put({'status': 'success', 'output': '代码作为模块成功加载和执行。'})
        
    except Exception:
        error_info = traceback.format_exc()
        result_queue.put({'status': 'error', 'output': error_info})
    finally:
        os.chdir(original_cwd)
        if module_name in sys.modules:
            del sys.modules[module_name]
        if os.path.exists(temp_script_path):
            try:
                os.remove(temp_script_path)
            except OSError as e:
                print(f"Warning: Could not remove temp file {temp_script_path}: {e}")

class LocalCodeSandbox:
    """
    一个使用 multiprocessing 和 importlib 实现的轻量级、安全的本地代码执行沙箱。
    """
    def __init__(self, timeout: int = 60):
        self.timeout = timeout

    def run(self, python_code: str, work_dir: str) -> Tuple[bool, str]:
        """
        在隔离的子进程中执行Python代码。
        
        Args:
            python_code: 要执行的Python代码字符串。
            work_dir: 子进程的工作目录。
            
        Returns:
            一个元组 (success: bool, output: str)，
            如果成功，output是成功信息；如果失败，output是完整的traceback。
        """
        if not os.path.exists(work_dir):
            os.makedirs(work_dir)

        result_queue = multiprocessing.Queue()
        process = multiprocessing.Process(
            target=_sandbox_target,
            args=(python_code, result_queue, os.path.abspath(work_dir))
        )
        
        process.start()
        process.join(timeout=self.timeout)
        
        if process.is_alive():
            process.terminate()
            process.join()
            return False, f"代码执行超时 (超过 {self.timeout} 秒)。"
            
        try:
            result = result_queue.get_nowait()
            if result['status'] == 'success':
                return True, result['output']
            else:
                return False, result['output']
        except Exception:
            return False, "沙箱进程意外终止。可能是因为内存耗尽或段错误。"