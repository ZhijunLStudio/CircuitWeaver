# src/sandbox/local_sandbox.py
import os
import sys
import multiprocessing
import traceback
import importlib.util
import uuid
from typing import Tuple

def _sandbox_target(code_string: str, result_queue: multiprocessing.Queue, work_dir: str):
    # This function runs in a completely separate process.
    
    stdout_path = os.path.join(work_dir, 'stdout.txt')
    stderr_path = os.path.join(work_dir, 'stderr.txt')
    
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    # Ensure files are created even if process crashes immediately
    with open(stdout_path, 'w', encoding='utf-8') as f_out, open(stderr_path, 'w', encoding='utf-8') as f_err:
        sys.stdout = f_out
        sys.stderr = f_err

        try:
            module_name = f"ai_generated_module_{uuid.uuid4().hex}"
            
            # Use a fixed name 'code.py' as we already created it in the main process
            temp_script_path = os.path.join(work_dir, "code.py")
            
            original_cwd = os.getcwd()
            os.chdir(work_dir)

            spec = importlib.util.spec_from_file_location(module_name, temp_script_path)
            if spec is None:
                raise ImportError(f"Could not create module spec for {temp_script_path}.")
            
            ai_module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = ai_module
            spec.loader.exec_module(ai_module)
            
            result_queue.put({'status': 'success'})
            
        except Exception:
            # Write traceback to stderr file, which is more reliable inside the sandbox
            traceback.print_exc(file=sys.stderr)
            result_queue.put({'status': 'error', 'output': traceback.format_exc()})
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            os.chdir(original_cwd)
            if module_name in sys.modules:
                del sys.modules[module_name]

class LocalCodeSandbox:
    def __init__(self, timeout: int = 120):
        self.timeout = timeout

    def run(self, python_code: str, work_dir: str) -> Tuple[bool, str]:
        os.makedirs(work_dir, exist_ok=True)
        
        with open(os.path.join(work_dir, "code.py"), "w", encoding="utf-8") as f:
            f.write(python_code)

        result_queue = multiprocessing.Queue()
        process = multiprocessing.Process(
            target=_sandbox_target,
            args=(python_code, result_queue, os.path.abspath(work_dir))
        )
        
        process.start()
        process.join(timeout=self.timeout)
        
        error_output = ""
        success = False

        if process.is_alive():
            process.terminate()
            process.join()
            error_output = f"Execution timed out (>{self.timeout}s)."
            success = False
        else:
            try:
                result = result_queue.get_nowait()
                if result.get('status') == 'success':
                    success = True
                else:
                    success = False
                    error_output = result.get('output', "Unknown error occurred in sandbox.")
            except Exception: # Catches Empty queue error if process died without putting result
                success = False
                error_output = "Sandbox process terminated unexpectedly before producing a result."

        # Consolidate logs after process has finished
        try:
            with open(os.path.join(work_dir, 'stdout.txt'), 'r', encoding='utf-8') as f:
                stdout_content = f.read()
            with open(os.path.join(work_dir, 'stderr.txt'), 'r', encoding='utf-8') as f:
                stderr_content = f.read()
            
            full_output = f"--- STDOUT ---\n{stdout_content}\n--- STDERR ---\n{stderr_content}\n"
            with open(os.path.join(work_dir, "output.txt"), "w", encoding="utf-8") as f:
                f.write(full_output)
            
            # If the main error_output is empty, but there's content in stderr, use that.
            if not error_output and stderr_content.strip():
                error_output = stderr_content.strip()

        except FileNotFoundError:
            if not error_output:
                error_output = "Sandbox failed to create log files."
        
        if not success:
             with open(os.path.join(work_dir, "error.txt"), "w", encoding="utf-8") as f:
                f.write(error_output)

        return success, error_output