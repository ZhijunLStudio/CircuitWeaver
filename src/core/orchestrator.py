import os
import uuid
import re
import traceback
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from openai import APITimeoutError

from configs import models, settings
from prompts import planner_prompts, coder_prompts, debugger_prompts, few_shot_library
from src.sandbox.local_sandbox import LocalCodeSandbox
from src.tools.documentation_search_tool import DocumentationSearchTool
from src.utils.metadata_injector import inject_metadata_code
from src.core.solution_miner import SolutionMiner
from src.db.knowledge_base import KnowledgeBaseManager

class CircuitWeaverOrchestrator:
    # __init__ 方法保持不变
    def __init__(self, job_id=0, async_pool=None):
        self.job_id = job_id
        self.run_id = uuid.uuid4().hex[:8]
        self.results_dir = os.path.join(settings.RESULTS_DIR, f"job_{job_id}_run_{self.run_id}")
        os.makedirs(self.results_dir, exist_ok=True)
        
        print(f"[Job {self.job_id}] Orchestrator initialized. Results: {self.results_dir}")

        llm_request_timeout = 300
        llm_max_retries = 2

        self.planner_llm = ChatOpenAI(
            model=models.MODEL_FOR_CREATION,
            api_key=models.API_KEY,
            base_url=models.BASE_URL,
            request_timeout=llm_request_timeout,
            max_retries=llm_max_retries
        )
        
        self.fixer_llms = [
            ChatOpenAI(
                model_name=model,
                api_key=models.API_KEY,
                base_url=models.BASE_URL,
                temperature=0.2 + i * 0.1,
                request_timeout=llm_request_timeout,
                max_retries=llm_max_retries
            )
            for i, model in enumerate(models.MODELS_FOR_FIXING)
        ]

        self.sandbox = LocalCodeSandbox(timeout=120)
        self.rag_tool = DocumentationSearchTool()
        self.kb_manager = KnowledgeBaseManager()
        
        self.solution_miner = SolutionMiner()
        self.async_pool = async_pool if async_pool else ThreadPoolExecutor()

    # run 方法保持不变
    def run(self):
        try:
            print(f"\n[Job {self.job_id}] --- STAGE 1: Generating circuit design concept ---")
            circuit_idea = self._generate_circuit_idea()
            self._save_artifact("1_circuit_idea.txt", circuit_idea)
            print(f"✅ [Job {self.job_id}] AI Design Concept:\n{circuit_idea}")

            print(f"\n[Job {self.job_id}] --- STAGE 2 & 3: Generating and Debugging Code ---")
            final_code = self._generate_and_debug_code(circuit_idea)
            
            if not final_code:
                print(f"\n❌ [Job {self.job_id}] Agent failed to generate a working script. Orchestration stopped.")
                return

            self._save_artifact("4_final_successful_code.py", final_code)
            print(f"✅ [Job {self.job_id}] Agent successfully generated a working script.")
            
            print(f"\n[Job {self.job_id}] --- STAGE 4: Injecting metadata and generating final assets ---")
            self._finalize_and_run(final_code)

        except Exception as e:
            print(f"\n🚨 [Job {self.job_id}] An unexpected error occurred in the orchestrator: {e}")
            traceback.print_exc()
        finally:
            print(f"\n--- [Job {self.job_id}] Orchestration Complete ---")
            print(f"All artifacts for Job {self.job_id} saved in: {self.results_dir}")

    def _generate_circuit_idea(self) -> str:
        return self.planner_llm.invoke([HumanMessage(content=planner_prompts.GET_IDEA_PROMPT)]).content

    def _generate_and_debug_code(self, circuit_idea: str) -> str | None:
        initial_prompt = coder_prompts.CODEGEN_PROMPT.format(
            circuit_idea=circuit_idea, 
            few_shot_examples=few_shot_library.EXAMPLE_1_HYBRID_SYSTEM
        )
        conversation_history = [HumanMessage(content=initial_prompt)]
        
        print(f"\n[Job {self.job_id}] " + "="*15 + f" Attempt #1/{settings.MAX_DEBUG_ATTEMPTS} (Initial Code Gen) " + "="*15)
        response = self.fixer_llms[0].invoke(conversation_history)
        current_code = self._extract_python_code(response.content)
        conversation_history.append(response)

        # <<< KEY CHANGE: Initialize failure chain tracker >>>
        current_failure_chain = []

        for i in range(settings.MAX_DEBUG_ATTEMPTS):
            attempt_num = i + 1
            if i > 0:
                print(f"\n[Job {self.job_id}] " + "="*15 + f" Debug Attempt #{attempt_num}/{settings.MAX_DEBUG_ATTEMPTS} " + "="*15)

            if not current_code:
                last_error = "AI failed to generate any Python code in the previous step."
                code_to_debug = ""
            else:
                self._save_artifact(f"2_attempt_{attempt_num}_code.py", current_code)
                success, output = self.sandbox.run(current_code, self.results_dir)
                if success:
                    print(f"🟢 [Job {self.job_id}] Code executed successfully on attempt #{attempt_num}!")
                    
                    # <<< KEY CHANGE: Trigger multi-step learning >>>
                    if current_failure_chain:
                        self.async_pool.submit(
                            self.solution_miner.mine_and_save_from_chain,
                            current_failure_chain, # Pass the whole chain
                            current_code
                        )
                        current_failure_chain = [] # Reset the chain after learning

                    return current_code
                
                last_error = output
                code_to_debug = current_code
                print(f"🔴 [Job {self.job_id}] Code for Attempt #{attempt_num} failed. Error:\n{last_error}")
                self._save_artifact(f"2_attempt_{attempt_num}_error.txt", last_error)

            # <<< KEY CHANGE: Add the new failure to the chain >>>
            current_failure_chain.append((code_to_debug, last_error))

            rag_context = self.rag_tool.forward(query=last_error.strip().split('\n')[-1])
            kb_context = self.kb_manager.get_relevant_solutions(last_error)
            full_context = f"{rag_context}\n\n{kb_context}".strip()
            
            debug_prompt = debugger_prompts.get_debug_prompt(code_to_debug, last_error, full_context)
            conversation_history.append(HumanMessage(content=debug_prompt))

            fix_responses = self._race_models_for_fix(conversation_history)
            
            validated_results = []
            successful_fix = None
            for model_idx, response_content in fix_responses.items():
                is_valid, result_or_error, code_snippet = self._validate_fix(response_content, model_idx, attempt_num)
                if is_valid:
                    successful_fix = {"response": response_content, "code": result_or_error, "model_idx": model_idx}
                    break
                else:
                    validated_results.append({
                        "model_idx": model_idx, "code": code_snippet, "error": result_or_error
                    })

            if successful_fix:
                print(f"🏆 [Job {self.job_id}] Model #{successful_fix['model_idx']} found a valid fix!")
                current_code = successful_fix['code']
                conversation_history.append(AIMessage(content=successful_fix['response']))
            else:
                print(f"🟡 [Job {self.job_id}] All models failed to provide a working fix in this attempt.")
                failure_summary = self._create_failure_summary(attempt_num, validated_results)
                conversation_history.append(AIMessage(content=failure_summary))
                
                if validated_results:
                    current_code = validated_results[0]['code']
                else:

                    current_code = code_to_debug 
        
        return None

    # ... The rest of the file (_create_failure_summary, _race_models_for_fix, etc.) remains exactly the same ...
    def _create_failure_summary(self, attempt_num: int, results: list) -> str:
        """Builds a detailed summary of all failed attempts for the conversation history."""
        if not results:
            return f"ATTEMPT {attempt_num} FAILED. No models produced any code to validate."
        
        summary = f"ATTEMPT {attempt_num} FAILED. All model solutions were invalid. I must learn from all their mistakes and try a new approach.\n\n"
        summary += "--- ANALYSIS OF FAILED ATTEMPTS ---\n"
        for res in results:
            model_name = models.MODELS_FOR_FIXING[res['model_idx']]
            summary += f"\n[Model #{res['model_idx']} ({model_name}) Attempt]:\n"
            summary += f"- Error Produced:\n```\n{res['error']}\n```\n"
            # No need to include the code again as it's saved as an artifact
        summary += "--- END OF ANALYSIS ---\n"
        return summary

    def _race_models_for_fix(self, history: list) -> dict:
        print(f"[Job {self.job_id}] Preparing to race models...")
        responses = {}
        with ThreadPoolExecutor(max_workers=len(self.fixer_llms)) as executor:
            future_to_model = {
                executor.submit(self._get_model_response, llm, history, model_idx): model_idx
                for model_idx, llm in enumerate(self.fixer_llms)
            }
            
            for future in as_completed(future_to_model):
                model_idx = future_to_model[future]
                try:
                    response_content = future.result()
                    if response_content:
                        responses[model_idx] = response_content
                except Exception as e:
                    print(f"💥 [Job {self.job_id}] Model #{model_idx} submission failed: {type(e).__name__} - {e}")
        return responses

    def _get_model_response(self, llm: ChatOpenAI, history: list, model_idx: int) -> str | None:
        model_name = models.MODELS_FOR_FIXING[model_idx]
        print(f"   [Job {self.job_id}] Model #{model_idx} ({model_name}) starting generation...")
        try:
            response = llm.invoke(history)
            return response.content
        except APITimeoutError:
            print(f"   [Job {self.job_id}] Model #{model_idx} ({model_name}) timed out.")
        except Exception:
            pass
        return None

    def _validate_fix(self, response_content: str, model_idx: int, attempt_num: int) -> tuple[bool, str, str]:
        code = self._extract_python_code(response_content)
        model_name = models.MODELS_FOR_FIXING[model_idx]
        
        if not code:
            error_msg = "Model did not return a valid Python code block."
            print(f"   ❌ [Job {self.job_id}] Code from Model #{model_idx} ({model_name}) FAILED: {error_msg}")
            return False, error_msg, ""

        print(f"   [Job {self.job_id}] Validating code from Model #{model_idx} ({model_name})...")
        success, output = self.sandbox.run(code, self.results_dir)
        
        # Save every model's attempt for full transparency
        model_filename_prefix = f"3_attempt_{attempt_num}_model_{model_idx}_{model_name.replace('/', '_')}"
        self._save_artifact(f"{model_filename_prefix}_code.py", code)

        if success:
            print(f"   ✅ [Job {self.job_id}] Code from Model #{model_idx} ({model_name}) is VALID.")
            return True, code, code
        else:
            print(f"   ❌ [Job {self.job_id}] Code from Model #{model_idx} ({model_name}) FAILED validation.")
            self._save_artifact(f"{model_filename_prefix}_error.txt", output)
            return False, output, code

    def _extract_python_code(self, content: str) -> str:
        match = re.search(r"```python\n(.*?)\n```", content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    def _save_artifact(self, filename: str, content: str):
        path = os.path.join(self.results_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _finalize_and_run(self, final_code: str):
        image_filename = 'final_circuit_diagram.svg'
        metadata_filename = 'final_circuit_metadata.json'
        
        script_with_metadata = inject_metadata_code(final_code, image_filename, metadata_filename)
        self._save_artifact("5_final_code_with_metadata.py", script_with_metadata)

        print(f"Executing final script to generate '{image_filename}' and '{metadata_filename}'...")
        success, output = self.sandbox.run(script_with_metadata, self.results_dir)
        
        if success:
            print(f"✅ [Job {self.job_id}] Successfully generated final assets.")
        else:
            print(f"❌ [Job {self.job_id}] ERROR: The final script with metadata injection failed!")
            print(f"   Error details:\n{output}")
            self._save_artifact("6_final_run_error.txt", output)