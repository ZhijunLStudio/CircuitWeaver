import os
import uuid
import re
import traceback
import time
import json
from datetime import datetime
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
import schemdraw
import schemdraw.elements as elm
from schemdraw import flow, dsp, logic # Import modules for exec scope

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from configs import models, settings
from prompts import planner_prompts, coder_prompts, debugger_prompts, architect_prompts
from src.sandbox.local_sandbox import LocalCodeSandbox
from src.tools.documentation_search_tool import DocumentationSearchTool
from src.core.solution_miner import SolutionMiner
from src.db.knowledge_base import KnowledgeBaseManager
from src.core.success_code_manager import get_success_code_manager
from src.utils.image_utils import resize_and_encode_image
from src.tools.example_retriever_tool import ExampleRetrieverTool
from src.utils.layout_analyzer import LayoutAnalyzer


class CircuitWeaverOrchestrator:
    def __init__(self, job_id=0, async_pool=None):
        self.job_id = job_id
        self.run_id = uuid.uuid4().hex[:8]
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.results_dir = os.path.join(settings.RESULTS_DIR, f"{timestamp}_job_{self.job_id}_run_{self.run_id}")
        os.makedirs(self.results_dir, exist_ok=True)
        
        print(f"[Job {self.job_id}] Orchestrator initialized. Results: {self.results_dir}")
        
        # LLM Configurations
        llm_request_timeout = 300
        llm_max_retries = 2
        self.planner_llm = ChatOpenAI(model=models.MODEL_FOR_CREATION, api_key=models.API_KEY, base_url=models.BASE_URL, request_timeout=llm_request_timeout, max_retries=llm_max_retries)
        self.architect_llm = ChatOpenAI(model=models.MODEL_FOR_CREATION, api_key=models.API_KEY, base_url=models.BASE_URL, request_timeout=llm_request_timeout, max_retries=llm_max_retries, model_kwargs={"response_format": {"type": "json_object"}})
        self.coder_llm = ChatOpenAI(model=models.MULTI_MODAL_MODEL, api_key=models.API_KEY, base_url=models.BASE_URL, request_timeout=llm_request_timeout, max_retries=llm_max_retries)
        self.fixer_llms = [
            ChatOpenAI(model_name=model, api_key=models.API_KEY, base_url=models.BASE_URL, temperature=0.2 + i * 0.1, request_timeout=llm_request_timeout, max_retries=llm_max_retries)
            for i, model in enumerate(models.MODELS_FOR_FIXING)
        ]

        # Tool Initializations
        self.sandbox = LocalCodeSandbox(timeout=settings.SANDBOX_TIMEOUT)
        self.rag_tool = DocumentationSearchTool()
        self.kb_manager = KnowledgeBaseManager()
        self.solution_miner = SolutionMiner()
        self.success_code_manager = get_success_code_manager()
        self.example_retriever = ExampleRetrieverTool()
        self.async_pool = async_pool if async_pool else ThreadPoolExecutor()

    def run(self):
        try:
            # Stage 1: Constrained Ideation
            print(f"\n[Job {self.job_id}] --- Stage 1: Generating Constrained Diagram Concept ---")
            circuit_idea = self.planner_llm.invoke([HumanMessage(content=planner_prompts.GET_IDEA_PROMPT)]).content
            self._save_artifact("1_circuit_idea.txt", circuit_idea)
            
            # Stage 2: Structural Modeling
            print(f"\n[Job {self.job_id}] --- Stage 2: Creating Structural JSON Blueprint ---")
            json_blueprint = self._create_json_blueprint(circuit_idea)
            if not json_blueprint: return

            # Stage 3: Code Generation and Refinement
            print(f"\n[Job {self.job_id}] --- Stage 3: Code Generation and Refinement ---")
            final_code = self._generation_and_refinement_workflow(circuit_idea, json_blueprint)
            
            if final_code:
                self._finalize_and_save(final_code, circuit_idea)
            else:
                print(f"\n❌ [Job {self.job_id}] Agent failed to produce a valid script. Orchestration stopped.")

        except Exception as e:
            print(f"\n🚨 [Job {self.job_id}] An unexpected error occurred: {e}")
            traceback.print_exc()
        finally:
            print(f"\n--- [Job {self.job_id}] Orchestration Complete ---")
            print(f"All artifacts saved in: {self.results_dir}")

    def _create_json_blueprint(self, circuit_idea: str) -> dict | None:
        reference_examples = self.success_code_manager.retrieve_successes(circuit_idea, k=settings.SUCCESS_CODE_RAG_K)
        prompt = architect_prompts.GENERATE_JSON_BLUEPRINT_PROMPT.format(
            circuit_idea=circuit_idea,
            reference_examples_code=reference_examples
        )
        try:
            response = self.architect_llm.invoke([HumanMessage(content=prompt)]).content
            blueprint = json.loads(response)
            self._save_artifact("2_json_blueprint.json", json.dumps(blueprint, indent=2))
            # Basic validation
            if "components" in blueprint and "connections" in blueprint:
                print("✅ JSON blueprint created successfully.")
                return blueprint
            else:
                raise ValueError("JSON blueprint missing required keys.")
        except (json.JSONDecodeError, ValueError) as e:
            print(f"🔴 Failed to create a valid JSON blueprint: {e}")
            self._save_artifact("2_json_blueprint_error.txt", response)
            return None

    def _generation_and_refinement_workflow(self, circuit_idea: str, json_blueprint: dict) -> str | None:
        initial_code = self._generate_initial_code(circuit_idea, json_blueprint)
        if not initial_code: return None

        runnable_code = self._runtime_debugging_loop(initial_code, circuit_idea)
        if not runnable_code:
            print(f"❌ Failed to produce a runnable script in the Runtime Debugging Workshop.")
            return None
        
        print(f"✅ Exited Runtime Workshop. Code is now runnable.")
        self._save_artifact("4_runnable_code.py", runnable_code)

        polished_code = self._layout_polishing_loop(runnable_code)
        if not polished_code:
            print(f"🟡 Failed to polish layout. Returning the last runnable version.")
            return runnable_code
        
        print(f"✅ Exited Layout Workshop. Code has been polished.")
        return polished_code

    def _generate_initial_code(self, circuit_idea: str, json_blueprint: dict) -> str | None:
        print(f"--- Step 3.1: Generating Code from Blueprint (Multi-Modal) ---")
        retrieved_examples = self.success_code_manager.retrieve_successes_as_docs(circuit_idea, k=settings.EXAMPLE_RAG_K)
        
        # We now use a different coder prompt that takes the JSON blueprint
        codegen_prompt = coder_prompts.CODEGEN_FROM_BLUEPRINT_PROMPT.format(
            circuit_idea=circuit_idea,
            json_blueprint=json.dumps(json_blueprint, indent=2)
        )
        codegen_message_content = [{"type": "text", "text": codegen_prompt}]
        for example_doc in retrieved_examples:
            # Assuming you've seeded your successful_circuits with images now
            # This part is a placeholder for that logic. If no images, it does nothing.
            pass
        
        response = self.coder_llm.invoke([HumanMessage(content=codegen_message_content)])
        code = self._extract_python_code(response.content)
        self._save_artifact("3_initial_generated_code.py", code)
        return code if code else None
        
    def _finalize_and_save(self, final_code, circuit_idea):
        print(f"\n✅ Agent successfully generated a visually and functionally valid script.")
        self._save_artifact("final_successful_code.py", final_code)
        final_run_dir = os.path.join(self.results_dir, "final_run")
        success, _ = self.sandbox.run(final_code, final_run_dir)
        if success:
            final_svg_path = os.path.join(final_run_dir, "circuit_diagram.svg")
            if os.path.exists(final_svg_path):
                shutil.copy(final_svg_path, os.path.join(self.results_dir, "final_successful_diagram.svg"))
                print(f"🖼️  Copied final diagram to root directory.")
        self.success_code_manager.add_success(final_code, circuit_idea)


    def _runtime_debugging_loop(self, code_to_debug: str, circuit_idea: str) -> str | None:
        print(f"\n[Job {self.job_id}] --- Entering Runtime Debugging Workshop ---")
        current_code = code_to_debug
        failure_chain = []

        for i in range(settings.MAX_RUNTIME_DEBUG_ATTEMPTS):
            attempt_num = i + 1
            print(f"[Job {self.job_id}] Runtime check, attempt {attempt_num}/{settings.MAX_RUNTIME_DEBUG_ATTEMPTS}...")
            
            validation_dir = os.path.join(self.results_dir, f"runtime_check_{attempt_num}")
            success, error = self.sandbox.run(current_code, validation_dir)
            
            if success:
                if failure_chain:
                    self.async_pool.submit(self.solution_miner.mine_and_save_from_chain, failure_chain, current_code)
                return current_code

            print(f"🔴 Runtime error detected: {error.strip().splitlines()[-1]}")
            failure_chain.append((current_code, error))
            
            fix_result = self._handle_runtime_error(current_code, error, circuit_idea, attempt_num)
            
            if fix_result and fix_result.get('best_attempt_code'):
                current_code = fix_result['best_attempt_code']
                if fix_result.get('successful_code'):
                    print("🏆 Runtime fix successful. Re-validating immediately.")
                else:
                    print(f"🟡 Fix attempt failed. Progressing with a new (but still broken) attempt.")
            else:
                print(f"🔴 Catastrophic failure: no models produced any code. Aborting runtime workshop.")
                return None
        
        return None

    def _layout_polishing_loop(self, runnable_code: str) -> str | None:
        print(f"\n[Job {self.job_id}] --- Entering Layout Polishing Workshop ---")
        current_code = runnable_code

        for i in range(settings.MAX_LAYOUT_DEBUG_ATTEMPTS):
            attempt_num = i + 1
            print(f"[Job {self.job_id}] Layout check, attempt {attempt_num}/{settings.MAX_LAYOUT_DEBUG_ATTEMPTS}...")

            try:
                local_scope = {'schemdraw': schemdraw, 'elm': elm}
                code_to_exec = current_code.replace("with schemdraw.Drawing(", "d = schemdraw.Drawing(")
                exec(code_to_exec, local_scope, local_scope)
                drawing_obj = local_scope.get('d')
                if not drawing_obj: raise ValueError("'d' object not found.")
                drawing_obj.draw()

                analyzer = LayoutAnalyzer(drawing_obj, settings.LAYOUT_ANALYSIS_CONFIG)
                layout_issues = analyzer.run_all_checks()

                if not layout_issues:
                    print(f"🎉 [Job {self.job_id}] Layout analysis passed! Polishing complete.")
                    return current_code
                
                print(f"🟡 Found {len(layout_issues)} layout issues. Requesting fix.")
                layout_report = analyzer.generate_report()
                self._save_artifact(f"layout_check_{attempt_num}_report.md", layout_report)
                
                fixed_code_proposal_result = self._handle_layout_error(current_code, layout_report, attempt_num)

                if not fixed_code_proposal_result or not fixed_code_proposal_result.get('best_attempt_code'):
                    print("🟡 Layout fix failed to produce new code. Aborting polish.")
                    return current_code

                fixed_code_proposal = fixed_code_proposal_result['best_attempt_code']

                print("[Job {self.job_id}] Verifying that the layout fix is still runnable...")
                verify_dir = os.path.join(self.results_dir, f"layout_fix_{attempt_num}_verify")
                success, _ = self.sandbox.run(fixed_code_proposal, verify_dir)

                if success:
                    print("🟢 Layout fix is valid. Continuing loop.")
                    current_code = fixed_code_proposal
                else:
                    print("🔴 Layout fix introduced a runtime error! Rejecting fix and trying again.")
                    continue

            except Exception as e:
                print(f"🔴 Critical error during layout analysis: {e}. Aborting polish.")
                return current_code

        print(f"🟡 [Job {self.job_id}] Reached max layout attempts. Returning best available code.")
        return current_code

    def _handle_runtime_error(self, code, error, circuit_idea, attempt_num):
        rag_context = self.rag_tool.forward(query=error.strip().split('\n')[-1])
        kb_context = self.kb_manager.get_relevant_solutions(error)
        full_context = f"{rag_context}\n\n{kb_context}".strip()
        
        debug_prompt = debugger_prompts.get_debug_prompt(code, error, full_context)
        fix_round_dir = os.path.join(self.results_dir, f"runtime_fix_round_{attempt_num}")
        
        return self._find_and_validate_fixes(debug_prompt, fix_round_dir)

    def _handle_layout_error(self, code, report, attempt_num):
        layout_debug_prompt = debugger_prompts.get_layout_debug_prompt(code, report)
        fix_round_dir = os.path.join(self.results_dir, f"layout_fix_round_{attempt_num}")
        
        return self._find_and_validate_fixes(layout_debug_prompt, fix_round_dir)

    def _find_and_validate_fixes(self, prompt, round_dir):
        history = [HumanMessage(content=prompt)]
        fix_responses = self._race_models_for_fix(history)
        
        validated_attempts = []
        for model_idx, response_content in fix_responses.items():
            code_proposal = self._extract_python_code(response_content)
            if not code_proposal: continue
            
            model_name = models.MODELS_FOR_FIXING[model_idx]
            validation_dir = os.path.join(round_dir, f"model_{model_idx}_{model_name.replace('/', '_')}")

            success, error = self.sandbox.run(code_proposal, validation_dir)
            
            validated_attempts.append({
                "code": code_proposal,
                "is_success": success,
                "error": error
            })
            
            if success:
                print(f"🏆 Model #{model_idx} ({model_name}) provided a valid, runnable fix.")
                return {
                    "successful_code": code_proposal,
                    "best_attempt_code": code_proposal
                }
        
        print(f"🟡 All models failed to provide a runnable fix.")
        if validated_attempts:
            return {"best_attempt_code": validated_attempts[0]['code']}
        else:
            return None

    def _generate_circuit_idea(self) -> str:
        return self.planner_llm.invoke([HumanMessage(content=planner_prompts.GET_IDEA_PROMPT)]).content

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

    def _extract_python_code(self, content: str) -> str:
        match = re.search(r"```python\n(.*?)\n```", content, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _save_artifact(self, filename: str, content: str):
        path = os.path.join(self.results_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)