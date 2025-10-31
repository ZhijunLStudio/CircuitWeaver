import os
import uuid
import re
import traceback
import time
from datetime import datetime
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from configs import models, settings
from prompts import planner_prompts, coder_prompts, debugger_prompts
from src.sandbox.local_sandbox import LocalCodeSandbox
from src.tools.documentation_search_tool import DocumentationSearchTool
from src.core.solution_miner import SolutionMiner
from src.db.knowledge_base import KnowledgeBaseManager
from src.core.success_code_manager import get_success_code_manager
from src.utils.image_utils import resize_and_encode_image
from src.tools.example_retriever_tool import ExampleRetrieverTool


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

        self.planner_llm = ChatOpenAI(model=models.MODEL_FOR_CREATION, api_key=models.API_KEY, base_url=models.BASE_URL, request_timeout=llm_request_timeout, max_retries=llm_max_retries)
        self.coder_llm = ChatOpenAI(model=models.MULTI_MODAL_MODEL, api_key=models.API_KEY, base_url=models.BASE_URL, request_timeout=llm_request_timeout, max_retries=llm_max_retries)
        self.fixer_llms = [
            ChatOpenAI(model_name=model, api_key=models.API_KEY, base_url=models.BASE_URL, temperature=0.2 + i * 0.1, request_timeout=llm_request_timeout, max_retries=llm_max_retries)
            for i, model in enumerate(models.MODELS_FOR_FIXING)
        ]

        self.sandbox = LocalCodeSandbox(timeout=settings.SANDBOX_TIMEOUT)
        self.rag_tool = DocumentationSearchTool()
        self.kb_manager = KnowledgeBaseManager()
        self.solution_miner = SolutionMiner()
        self.success_code_manager = get_success_code_manager()
        self.example_retriever = ExampleRetrieverTool()
        self.async_pool = async_pool if async_pool else ThreadPoolExecutor()

    def run(self):
        try:
            print(f"\n[Job {self.job_id}] --- STAGE 1: Generating circuit design concept ---")
            circuit_idea = self._generate_circuit_idea()
            self._save_artifact("1_circuit_idea.txt", circuit_idea)
            
            print(f"\n[Job {self.job_id}] --- STAGE 2: Multi-Modal Generation & Debugging ---")
            final_code = self._generate_and_debug_code(circuit_idea)
            
            if final_code:
                print(f"\n✅ [Job {self.job_id}] Agent successfully generated a working script.")
                self._save_artifact("final_successful_code.py", final_code)

                final_run_dir = os.path.join(self.results_dir, "final_run")
                success, _ = self.sandbox.run(final_code, final_run_dir)
                if success:
                    final_svg_path = os.path.join(final_run_dir, "circuit_diagram.svg")
                    if os.path.exists(final_svg_path):
                        shutil.copy(final_svg_path, os.path.join(self.results_dir, "final_successful_diagram.svg"))
                        print(f"🖼️  Copied final diagram to root directory.")
                
                # We still save the new, high-quality success to build a better library from scratch
                self.success_code_manager.add_success(final_code, circuit_idea)
            else:
                print(f"\n❌ [Job {self.job_id}] Agent failed to generate a working script after all attempts. Orchestration stopped.")

        except Exception as e:
            print(f"\n🚨 [Job {self.job_id}] An unexpected error occurred in the orchestrator: {e}")
            traceback.print_exc()
        finally:
            print(f"\n--- [Job {self.job_id}] Orchestration Complete ---")
            print(f"All artifacts for Job {self.job_id} saved in: {self.results_dir}")

    def _generate_circuit_idea(self) -> str:
        return self.planner_llm.invoke([HumanMessage(content=planner_prompts.GET_IDEA_PROMPT)]).content

    def _generate_and_debug_code(self, circuit_idea: str) -> str | None:
        # STAGE 2.1: Retrieve high-quality, curated examples
        print(f"\n[Job {self.job_id}] Retrieving {settings.EXAMPLE_RAG_K} visual examples from standard library...")
        retrieved_examples = self.example_retriever.forward(circuit_idea, k=settings.EXAMPLE_RAG_K)
        reference_codes = "\n\n---\n\n".join([ex['code'] for ex in retrieved_examples])

        # STAGE 2.2: Generate Layout Plan based on curated examples
        print(f"[Job {self.job_id}] Generating high-level layout plan...")
        planning_prompt = coder_prompts.PLANNING_PROMPT.format(
            circuit_idea=circuit_idea,
            reference_examples_code=reference_codes
        )
        execution_plan = self.planner_llm.invoke([HumanMessage(content=planning_prompt)]).content
        self._save_artifact("2_execution_plan.md", execution_plan)
        print(f"[Job {self.job_id}] Layout plan generated successfully.")

        # STAGE 2.3: Generate Code from Plan using Multi-Modal LLM
        print(f"[Job {self.job_id}] Generating initial code from plan using multi-modal context...")
        
        codegen_prompt = coder_prompts.CODEGEN_FROM_PLAN_PROMPT.format(
            circuit_idea=circuit_idea,
            execution_plan=execution_plan
        )
        codegen_message_content = [{"type": "text", "text": codegen_prompt}]
        
        for i, example in enumerate(retrieved_examples):
            if example.get('image_path'):
                full_image_path = os.path.join(settings.PROCESSED_CIRCUITS_DIR, example['image_path'])
                b64_image = resize_and_encode_image(full_image_path, settings.MAX_IMAGE_DIMENSION)
                if b64_image:
                    print(f"  > Attaching reference image #{i+1} to prompt...")
                    codegen_message_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64_image}"}
                    })
        
        response = self.coder_llm.invoke([HumanMessage(content=codegen_message_content)])
        current_code = self._extract_python_code(response.content)
        self._save_artifact("3_initial_generated_code.py", current_code)
        
        if not current_code:
            print("🔴 [Job {self.job_id}] Initial code generation failed (no code produced). Aborting.")
            return None

        # STAGE 2.4: Runtime Validation & Debug Loop
        current_failure_chain = []
        for i in range(settings.MAX_DEBUG_ATTEMPTS):
            attempt_num = i + 1
            print(f"\n[Job {self.job_id}] " + "="*15 + f" Validation Attempt #{attempt_num} " + "="*15)
            
            attempt_dir = os.path.join(self.results_dir, f"attempt_{attempt_num}_validation")
            success, error = self.sandbox.run(current_code, attempt_dir)

            if success:
                print(f"🟢 [Job {self.job_id}] Code is valid in attempt #{attempt_num}!")
                if current_failure_chain:
                    self.async_pool.submit(self.solution_miner.mine_and_save_from_chain, current_failure_chain, current_code)
                return current_code
            
            print(f"🔴 [Job {self.job_id}] Code failed validation. See directory: attempt_{attempt_num}_validation")
            print(f"Error Details:\n{error}")
            current_failure_chain.append((current_code, error))
            
            print(f"\n[Job {self.job_id}] " + "="*15 + f" Debug Attempt #{attempt_num}/{settings.MAX_DEBUG_ATTEMPTS} " + "="*15)
            
            rag_context = self.rag_tool.forward(query=error.strip().split('\n')[-1])
            kb_context = self.kb_manager.get_relevant_solutions(error)
            
            # ========================= KEY CHANGE =========================
            # Temporarily disable retrieving from the self-generated success repo.
            # This prevents potentially low-quality examples from influencing the debugging process.
            # To re-enable later, uncomment the following two lines and comment out the third.
            #
            # successful_examples = self.success_code_manager.retrieve_successes(circuit_idea, k=settings.SUCCESS_CODE_RAG_K)
            # full_context = f"{rag_context}\n\n{kb_context}\n\n{successful_examples}".strip()
            
            # The full context for debugging will now ONLY contain documentation and the knowledge base.
            full_context = f"{rag_context}\n\n{kb_context}".strip()
            # ======================= END OF KEY CHANGE =======================

            debug_prompt = debugger_prompts.get_debug_prompt(current_code, error, full_context)
            conversation_history = [HumanMessage(content=debug_prompt)]

            fix_round_dir = os.path.join(self.results_dir, f"attempt_{attempt_num}_fix_round")
            fix_responses = self._race_models_for_fix(conversation_history)
            
            validated_results, successful_fix = [], None
            for model_idx, response_content in fix_responses.items():
                is_valid, result_or_error, code_snippet, _ = self._validate_fix(response_content, model_idx, fix_round_dir)
                if is_valid:
                    successful_fix = {"response": response_content, "code": result_or_error, "model_idx": model_idx}
                    break
                else:
                    validated_results.append({"model_idx": model_idx, "code": code_snippet, "error": result_or_error})

            if successful_fix:
                print(f"🏆 [Job {self.job_id}] Model #{successful_fix['model_idx']} found a valid fix!")
                current_code = successful_fix['code']
            else:
                print(f"🟡 [Job {self.job_id}] All models failed to provide a working fix in this attempt.")
                if validated_results and validated_results[0]['code']: # Fallback to the first failed attempt's code if it exists
                    current_code = validated_results[0]['code']
                # If no model even produced code, we re-use the original failed code for the next attempt.
        
        return None

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

    def _validate_fix(self, response_content: str, model_idx: int, round_dir: str) -> tuple[bool, str, str, str]:
        model_name = models.MODELS_FOR_FIXING[model_idx]
        validation_dir = os.path.join(round_dir, f"model_{model_idx}_{model_name.replace('/', '_')}")
        
        code = self._extract_python_code(response_content)
        if not code:
            return False, "Model did not return a valid Python code block.", "", validation_dir

        success, output = self.sandbox.run(code, validation_dir)
        return (True, code, code, validation_dir) if success else (False, output, code, validation_dir)

    def _extract_python_code(self, content: str) -> str:
        match = re.search(r"```python\n(.*?)\n```", content, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _save_artifact(self, filename: str, content: str):
        path = os.path.join(self.results_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)