# src/core/orchestrator.py
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
            print(f"\n✅ [Job {self.job_id}] Agent successfully generated a working script.")
            
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
        
    # --- KEY CHANGE: Refactored _generate_and_debug_code for Stateful Memory ---
    def _generate_and_debug_code(self, circuit_idea: str) -> str | None:
        # 1. Initialize conversation history
        initial_prompt = coder_prompts.CODEGEN_PROMPT.format(
            circuit_idea=circuit_idea, 
            few_shot_examples=few_shot_library.EXAMPLE_1_HYBRID_SYSTEM
        )
        conversation_history = [HumanMessage(content=initial_prompt)]
        
        # 2. Get the first code generation
        print(f"\n[Job {self.job_id}] " + "="*15 + f" Attempt #1/{settings.MAX_DEBUG_ATTEMPTS} (Initial Code Gen) " + "="*15)
        response = self.fixer_llms[0].invoke(conversation_history)
        current_code = self._extract_python_code(response.content)
        conversation_history.append(response) # Add AI's first attempt to history

        for i in range(settings.MAX_DEBUG_ATTEMPTS):
            attempt_num = i + 1
            if i > 0: # Only print attempt number for debug loops
                print(f"\n[Job {self.job_id}] " + "="*15 + f" Debug Attempt #{attempt_num}/{settings.MAX_DEBUG_ATTEMPTS} " + "="*15)

            # 3. Validate the current code
            if not current_code:
                last_error = "AI failed to generate any Python code."
                failed_code = ""
            else:
                self._save_artifact(f"2_attempt_{attempt_num}_code.py", current_code)
                success, output = self.sandbox.run(current_code, self.results_dir)
                if success:
                    print(f"🟢 [Job {self.job_id}] Code executed successfully on attempt #{attempt_num}!")
                    # If this was a fix, the successful code is `current_code`, and the failed code was from the previous loop.
                    # We need to find the previously failed code to log the solution.
                    if i > 0:
                        # Find the last HumanMessage which contains the debug prompt and failed code
                        last_debug_prompt = next((msg for msg in reversed(conversation_history) if isinstance(msg, HumanMessage) and "FAILED CODE" in msg.content), None)
                        if last_debug_prompt:
                           match = re.search(r"FAILED CODE:\s*```python\n(.*?)\n```", last_debug_prompt.content, re.DOTALL)
                           if match:
                               prev_failed_code = match.group(1).strip()
                               prev_error = re.search(r"ERROR MESSAGE \(Traceback\):\s*```\n(.*?)\n```", last_debug_prompt.content, re.DOTALL).group(1).strip()
                               self.async_pool.submit(
                                   self.solution_miner.mine_and_save_solution,
                                   prev_failed_code, prev_error, current_code
                               )
                    return current_code
                
                last_error = output
                failed_code = current_code
                print(f"🔴 [Job {self.job_id}] Code failed. Error:\n{last_error}")
                self._save_artifact(f"2_attempt_{attempt_num}_error.txt", last_error)

            # 4. Prepare and execute the fix request
            # This is where the stateful memory is built
            core_error = last_error.strip().split('\n')[-1]
            rag_context = self.rag_tool.forward(query=core_error)
            kb_context = self.kb_manager.get_relevant_solutions(core_error)
            full_context = f"{rag_context}\n\n{kb_context}".strip()
            
            # Create the debug prompt for this turn
            debug_prompt = debugger_prompts.get_debug_prompt(failed_code, last_error, full_context)
            
            # *** CRITICAL MEMORY STEP ***
            # Add the user's debug request to the history for the NEXT turn to see
            conversation_history.append(HumanMessage(content=debug_prompt))

            # 5. Race models for a fix
            fix_responses = self._race_models_for_fix(conversation_history)
            
            if fix_responses:
                # Find the first valid code from the responses
                for model_idx, response_content in fix_responses.items():
                    validated_code = self._validate_fix(response_content, model_idx)
                    if validated_code:
                        print(f"🏆 [Job {self.job_id}] Model #{model_idx} found a valid fix!")
                        # *** CRITICAL MEMORY STEP ***
                        # Add the SUCCESSFUL model's response to history
                        conversation_history.append(AIMessage(content=response_content))
                        current_code = validated_code
                        # Break the inner loop and proceed to the next validation loop (for loop)
                        break 
                else: # This 'else' belongs to the 'for', executed if no break
                    print(f"🟡 [Job {self.job_id}] All model responses failed validation in this attempt.")
                    # *** CRITICAL MEMORY STEP ***
                    # Add a summary of the failure to the history so the AI knows its previous attempt was fruitless
                    failure_summary = f"ATTEMPT {attempt_num} FAILED. All models ({', '.join(map(str, fix_responses.keys()))}) provided code that did not pass validation. The error was still: {core_error}. I must try a completely different approach."
                    conversation_history.append(AIMessage(content=failure_summary))
                    # current_code remains the last failed code
            else:
                 print(f"🟡 [Job {self.job_id}] All models failed to generate any response in this attempt.")
                 conversation_history.append(AIMessage(content=f"ATTEMPT {attempt_num} FAILED. All models failed to generate a response."))
        
        return None # All attempts failed

    # --- KEY CHANGE: race_models_for_fix now returns ALL responses, validation happens outside ---
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
        print(f"   [Job {self.job_id}] Model #{model_idx} starting generation...")
        try:
            response = llm.invoke(history)
            return response.content
        except APITimeoutError:
            print(f"   [Job {self.job_id}] Model #{model_idx} timed out.")
        except Exception:
            # Other exceptions are already logged in the race_models_for_fix
            pass
        return None

    def _validate_fix(self, response_content: str, model_idx: int) -> str | None:
        code = self._extract_python_code(response_content)
        if not code:
            print(f"   [Job {self.job_id}] Model #{model_idx} did not return code.")
            return None
        
        print(f"   [Job {self.job_id}] Validating code from Model #{model_idx}...")
        success, _ = self.sandbox.run(code, self.results_dir)
        if success:
            print(f"   ✅ [Job {self.job_id}] Code from Model #{model_idx} is VALID.")
            return code
        else:
            print(f"   ❌ [Job {self.job_id}] Code from Model #{model_idx} FAILED validation.")
            return None

    # Unchanged helper methods below
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