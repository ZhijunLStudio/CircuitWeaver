import os
import uuid
import re
import traceback
import time
from datetime import datetime
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
import schemdraw
import schemdraw.elements as elm
from schemdraw import flow, dsp, logic

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from configs import models, settings
from prompts import coder_prompts, debugger_prompts
from src.sandbox.local_sandbox import LocalCodeSandbox
from src.core.solution_miner import SolutionMiner
from src.db.knowledge_base import KnowledgeBaseManager
from src.core.success_code_manager import get_success_code_manager
from src.utils.layout_analyzer import LayoutAnalyzer

class CircuitWeaverOrchestrator:
    def __init__(self, job_id=0, async_pool=None):
        self.job_id = job_id
        self.run_id = uuid.uuid4().hex[:8]
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.results_dir = os.path.join(settings.RESULTS_DIR, f"{timestamp}_job_{self.job_id}_run_{self.run_id}")
        os.makedirs(self.results_dir, exist_ok=True)
        
        print(f"[Job {self.job_id}] Orchestrator initialized. Results: {self.results_dir}")
        
        llm_request_timeout = 300
        llm_max_retries = 2
        self.generator_llm = ChatOpenAI(model=models.MODEL_FOR_CREATION, api_key=models.API_KEY, base_url=models.BASE_URL, request_timeout=llm_request_timeout, max_retries=llm_max_retries, temperature=0.7)
        self.fixer_llms = [
            ChatOpenAI(model_name=model, api_key=models.API_KEY, base_url=models.BASE_URL, temperature=0.2 + i * 0.1, request_timeout=llm_request_timeout, max_retries=llm_max_retries)
            for i, model in enumerate(models.MODELS_FOR_FIXING)
        ]
        
        self.sandbox = LocalCodeSandbox(timeout=settings.SANDBOX_TIMEOUT)
        # We are not using RAG for now, so these can be commented out if you want
        self.kb_manager = KnowledgeBaseManager()
        self.solution_miner = SolutionMiner()
        self.success_code_manager = get_success_code_manager()
        self.async_pool = async_pool if async_pool else ThreadPoolExecutor()

    def run(self):
        try:
            final_code = self._generation_and_refinement_workflow()
            if final_code:
                self._finalize_and_save(final_code)
            else:
                print(f"\n❌ [Job {self.job_id}] Agent failed to produce a valid script after all attempts. Orchestration stopped.")
        except Exception as e:
            print(f"\n🚨 [Job {self.job_id}] An unexpected error occurred: {e}")
            traceback.print_exc()
        finally:
            print(f"\n--- [Job {self.job_id}] Orchestration Complete ---")
            print(f"All artifacts saved in: {self.results_dir}")

    def _generation_and_refinement_workflow(self) -> str | None:
        print(f"\n[Job {self.job_id}] --- Stage 1: Generating Code from Design Patterns ---")
        generated_content = self._generate_initial_content()
        if not generated_content: 
            print("🔴 Generation failed at the first step (no content produced).")
            return None

        # Assemble the full script from the template and the AI's content
        full_script = self._assemble_script(generated_content)
        self._save_artifact("3_initial_full_script.py", full_script)

        runnable_code = self._runtime_debugging_loop(full_script)
        if not runnable_code:
            print(f"❌ Failed to produce a runnable script in the Runtime Debugging Workshop.")
            return None
        self._save_artifact("4_runnable_code.py", runnable_code)
        print(f"✅ Exited Runtime Workshop. Code is now runnable.")

        polished_code = self._layout_polishing_loop(runnable_code)
        return polished_code if polished_code else runnable_code

    def _generate_initial_content(self) -> str | None:
        """Generates ONLY the inner content for the drawing block."""
        prompt = coder_prompts.DESIGN_PATTERN_PROMPT
        response = self.generator_llm.invoke([HumanMessage(content=prompt)])
        return self._extract_python_code(response.content, require_fences=False)

    def _assemble_script(self, content: str) -> str:
        """Injects the AI-generated content into the fixed code template."""
        template = """import schemdraw
import schemdraw.dsp as dsp
import schemdraw.elements as elm

with schemdraw.Drawing(file='circuit_diagram.svg', show=False, unit=2.5) as d:
    # --- Start of AI-generated content ---
{content}
    # --- End of AI-generated content ---
"""
        # Indent the AI's code correctly
        indented_content = "    " + content.replace("\n", "\n    ")
        return template.format(content=indented_content)
    
    def _runtime_debugging_loop(self, code_to_debug: str) -> str | None:
        # This loop's logic is sound and remains the same
        print(f"\n[Job {self.job_id}] --- Entering Runtime Debugging Workshop ---")
        current_code = code_to_debug
        failure_chain = []

        for i in range(settings.MAX_RUNTIME_DEBUG_ATTEMPTS):
            attempt_num = i + 1
            print(f"[Job {self.job_id}] Runtime check, attempt {attempt_num}/{settings.MAX_RUNTIME_DEBUG_ATTEMPTS}...")
            validation_dir = os.path.join(self.results_dir, f"runtime_check_{attempt_num}")
            success, error = self.sandbox.run(current_code, validation_dir)
            if success:
                if failure_chain: self.async_pool.submit(self.solution_miner.mine_and_save_from_chain, failure_chain, current_code)
                return current_code

            print(f"🔴 Runtime error detected: {error.strip().splitlines()[-1]}")
            failure_chain.append((current_code, error))
            fix_result = self._handle_runtime_error(current_code, error, attempt_num)
            if fix_result and fix_result.get('best_attempt_code'):
                current_code = fix_result['best_attempt_code']
            else:
                print(f"🔴 Catastrophic failure: no models produced any code. Aborting workshop.")
                return None
        return None

    def _layout_polishing_loop(self, runnable_code: str) -> str | None:
        # This loop is now enhanced with a check for empty drawings
        print(f"\n[Job {self.job_id}] --- Entering Layout Polishing Workshop ---")
        current_code = runnable_code

        for i in range(settings.MAX_LAYOUT_DEBUG_ATTEMPTS):
            attempt_num = i + 1
            print(f"[Job {self.job_id}] Layout check, attempt {attempt_num}/{settings.MAX_LAYOUT_DEBUG_ATTEMPTS}...")

            try:
                local_scope = {'schemdraw': schemdraw, 'elm': elm, 'flow': flow, 'dsp': dsp, 'logic': logic}
                code_to_exec = current_code.replace("with schemdraw.Drawing(", "d = schemdraw.Drawing(")
                exec(code_to_exec, local_scope, local_scope)
                drawing_obj = local_scope.get('d')
                
                if not drawing_obj: raise ValueError("'d' object not found after execution.")
                if not drawing_obj.elements: raise ValueError("Drawing is empty. No elements were added to the drawing object 'd'.")
                
                drawing_obj.draw()
                analyzer = LayoutAnalyzer(drawing_obj, settings.LAYOUT_ANALYSIS_CONFIG)
                layout_issues = analyzer.run_all_checks()

                if not layout_issues:
                    print(f"🎉 Layout analysis passed! Polishing complete.")
                    return current_code
                
                print(f"🟡 Found {len(layout_issues)} layout issues. Requesting fix.")
                layout_report = analyzer.generate_report()
                self._save_artifact(f"layout_check_{attempt_num}_report.md", layout_report)
                fixed_code_proposal_result = self._handle_layout_error(current_code, layout_report, attempt_num)

                if not fixed_code_proposal_result or not fixed_code_proposal_result.get('best_attempt_code'):
                    return current_code

                fixed_code_proposal = fixed_code_proposal_result['best_attempt_code']
                verify_dir = os.path.join(self.results_dir, f"layout_fix_{attempt_num}_verify")
                success, _ = self.sandbox.run(fixed_code_proposal, verify_dir)

                if success:
                    print("🟢 Layout fix is valid. Continuing loop.")
                    current_code = fixed_code_proposal
                else:
                    print("🔴 Layout fix introduced a runtime error! Rejecting fix.")
            
            except Exception as e:
                print(f"🔴 Critical error during layout analysis: {e}. Requesting a runtime fix.")
                fixed_code = self._handle_runtime_error(current_code, str(e), attempt_num)
                if not fixed_code or not fixed_code.get('best_attempt_code'):
                    return runnable_code
                current_code = fixed_code['best_attempt_code']
        
        return current_code

    def _handle_runtime_error(self, code, error, attempt_num):
        debug_prompt = debugger_prompts.get_debug_prompt(code, error, "") # No RAG
        fix_round_dir = os.path.join(self.results_dir, f"runtime_fix_round_{attempt_num}")
        return self._find_and_validate_fixes(debug_prompt, fix_round_dir)

    def _handle_layout_error(self, code, report, attempt_num):
        layout_debug_prompt = debugger_prompts.get_layout_debug_prompt(code, report)
        fix_round_dir = os.path.join(self.results_dir, f"layout_fix_round_{attempt_num}")
        return self._find_and_validate_fixes(layout_debug_prompt, fix_round_dir)

    def _find_and_validate_fixes(self, prompt, round_dir):
        # This function's logic is sound and remains the same
        history = [HumanMessage(content=prompt)]
        fix_responses = self._race_models_for_fix(history)
        validated_attempts = []
        for model_idx, response_content in fix_responses.items():
            # For this simplified workflow, we expect the FULL script back
            code_proposal = self._extract_python_code(response_content, require_fences=True)
            if not code_proposal: continue
            
            model_name = models.MODELS_FOR_FIXING[model_idx]
            validation_dir = os.path.join(round_dir, f"model_{model_idx}_{model_name.replace('/', '_')}")
            success, _ = self.sandbox.run(code_proposal, validation_dir)
            validated_attempts.append({"code": code_proposal})
            if success:
                return {"successful_code": code_proposal, "best_attempt_code": code_proposal}
        
        if validated_attempts:
            return {"best_attempt_code": validated_attempts[0]['code']}
        return None

    def _finalize_and_save(self, final_code):
        print(f"\n✅ Agent successfully generated a valid script.")
        self._save_artifact("final_successful_code.py", final_code)
        final_run_dir = os.path.join(self.results_dir, "final_run")
        self.sandbox.run(final_code, final_run_dir)
        final_svg_path = os.path.join(final_run_dir, "circuit_diagram.svg")
        if os.path.exists(final_svg_path):
            shutil.copy(final_svg_path, os.path.join(self.results_dir, "final_successful_diagram.svg"))
            print(f"🖼️  Copied final diagram to root directory.")

    def _race_models_for_fix(self, history: list) -> dict:
        print(f"[Job {self.job_id}] Racing {len(self.fixer_llms)} models for a fix...")
        responses = {}
        with ThreadPoolExecutor(max_workers=len(self.fixer_llms)) as executor:
            future_to_model = {executor.submit(llm.invoke, history): model_idx for model_idx, llm in enumerate(self.fixer_llms)}
            for future in as_completed(future_to_model):
                model_idx = future_to_model[future]
                try:
                    response_content = future.result().content
                    if response_content: responses[model_idx] = response_content
                except Exception as e:
                    print(f"💥 [Job {self.job_id}] Model #{model_idx} submission failed: {e}")
        return responses

    def _extract_python_code(self, content: str, require_fences: bool = True) -> str:
        if require_fences:
            match = re.search(r"```python\n(.*?)\n```", content, re.DOTALL)
            return match.group(1).strip() if match else ""
        else:
            # For the initial generation, AI might not use fences, so we take the whole content
            return content.strip()

    def _save_artifact(self, filename: str, content: str):
        path = os.path.join(self.results_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)