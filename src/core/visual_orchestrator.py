# src/core/visual_orchestrator.py
import os
import json
import base64
import traceback
import re
import shutil
from typing import List, Dict

import cairosvg
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from configs import models, settings
from prompts import visual_prompts, debugger_prompts
from src.core.orchestrator import CircuitWeaverOrchestrator

class VisualOrchestrator:
    def __init__(self, job_id, base_results_dir, async_pool=None):
        self.job_id = job_id
        self.stage2_dir = os.path.join(base_results_dir, "stage_two_debug")
        os.makedirs(self.stage2_dir, exist_ok=True)
        
        self.inspector_llm = ChatOpenAI(
            model=models.MULTI_MODAL_MODEL,
            api_key=models.API_KEY,
            base_url=models.BASE_URL,
            temperature=0.0,
            max_tokens=2048,
        )
        
        print("[VisualOrchestrator] Reusing components from main orchestrator...")
        self.base_orchestrator = CircuitWeaverOrchestrator(job_id, async_pool)
        print(f"[Job {self.job_id}] VisualOrchestrator initialized. Debug results in: {self.stage2_dir}")

    def run(self, initial_code: str, initial_svg_path: str, circuit_idea: str) -> str:
        print(f"\n[Job {self.job_id}] " + "="*15 + f" Visual Sanity Check " + "="*15)
        print("🔬 Performing initial visual inspection to generate master issue list...")
        master_issue_list = self._inspect_image_for_issues(initial_code, initial_svg_path, circuit_idea, "initial")

        if not master_issue_list:
            print("✅ No visual issues found in the initial diagram. Refinement complete!")
            return initial_code
        
        print(f"⚠️ Found {len(master_issue_list)} initial visual issues to resolve. Starting targeted fixing process.")
        
        current_code = initial_code
        current_svg_path = initial_svg_path

        for i in range(settings.MAX_VISUAL_DEBUG_ATTEMPTS):
            if not master_issue_list:
                print("🎉 All initial visual issues have been resolved! Refinement complete.")
                break

            attempt = i + 1
            print(f"\n[Job {self.job_id}] " + "="*15 + f" Targeted Visual Fix Attempt #{attempt}/{settings.MAX_VISUAL_DEBUG_ATTEMPTS} " + "="*15)

            issue_to_fix = master_issue_list[0]
            print(f"🎯 Targeting issue: {issue_to_fix['problem_description']}")
            
            print("🎨 Attempting to generate a targeted fix...")
            correction_prompt = visual_prompts.VISUAL_CORRECTION_PROMPT.format(
                original_code=current_code,
                issue_to_fix_json=json.dumps(issue_to_fix, indent=2)
            )
            
            fix_round_dir = os.path.join(self.stage2_dir, f"attempt_{attempt}_fix_for_issue_{i+1}")
            
            successful_fix, _ = self._run_fix_cycle([HumanMessage(content=correction_prompt)], fix_round_dir)
            
            if not successful_fix:
                print("🟡 No model could produce a valid code for this issue. Removing from list to avoid loop.")
                master_issue_list.pop(0) # Assume unfixable for now
                continue

            fixed_code = successful_fix['code']
            fix_code_dir = os.path.dirname(successful_fix['validation_dir']) # e.g., .../model_0_.../
            
            validation_dir = fix_code_dir # The code is already validated, this is our new source
            new_svg_path = os.path.join(validation_dir, "circuit_diagram.svg")

            print(f"🔬 Verifying if the targeted issue was resolved by comparing old and new images...")
            verification_result = self._verify_fix(issue_to_fix['problem_description'], current_svg_path, new_svg_path, attempt)

            # --- KEY STATE UPDATE LOGIC ---
            if verification_result.get("is_resolved"):
                print(f"🟢 Success! Issue '{issue_to_fix['problem_description'][:50]}...' is resolved.")
                master_issue_list.pop(0)
                # CRITICAL: Update both code and SVG path for the next iteration
                current_code = fixed_code
                current_svg_path = new_svg_path
            else:
                print(f"🔴 Fix attempt was valid but did not resolve the visual issue. Reason: {verification_result.get('reasoning')}. The issue remains.")
                # We still update the code, as it's a valid change, but keep the issue in the list.
                # This prevents getting stuck on an unfixable issue with old code.
                current_code = fixed_code
                current_svg_path = new_svg_path
                # To prevent infinite loops, we can move the failed issue to the back of the queue
                master_issue_list.append(master_issue_list.pop(0))
                
        if master_issue_list:
            print(f"🔚 Reached max visual debug attempts with {len(master_issue_list)} issues remaining.")
        
        return current_code

    def _run_fix_cycle(self, history: list, round_dir: str):
        fix_responses = self.base_orchestrator._race_models_for_fix(history)
            
        validated_results = []
        successful_fix = None
        for model_idx, response_content in fix_responses.items():
            is_valid, result_or_error, code_snippet, validation_dir = self.base_orchestrator._validate_fix(
                response_content, model_idx, round_dir
            )
            if is_valid:
                successful_fix = {"response": response_content, "code": result_or_error, "model_idx": model_idx, "validation_dir": validation_dir}
                break
            else:
                validated_results.append({"model_idx": model_idx, "code": code_snippet, "error": result_or_error})
        
        return successful_fix, validated_results

    def _parse_json_from_response(self, response_content: str, attempt: str, report_name: str) -> Dict:
        try:
            match = re.search(r"```json\n(.*?)\n```", response_content, re.DOTALL)
            json_str = match.group(1) if match else response_content
            parsed_json = json.loads(json_str)
            
            report_path = os.path.join(self.stage2_dir, f"{report_name}_{attempt}.json")
            with open(report_path, 'w', encoding='utf-8') as f: json.dump(parsed_json, f, indent=2)
            return parsed_json
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON from LLM: {e}. Content: {response_content}")
            raw_path = os.path.join(self.stage2_dir, f"{report_name}_{attempt}_failed.txt")
            with open(raw_path, 'w', encoding='utf-8') as f: f.write(response_content)
            return {"error": "JSONDecodeError", "content": response_content}

    def _verify_fix(self, issue_description: str, old_svg_path: str, new_svg_path: str, attempt: int) -> Dict:
        try:
            png_paths = []
            for path in [old_svg_path, new_svg_path]:
                png_path = os.path.splitext(path)[0] + f"_verify_{attempt}.png"
                cairosvg.svg2png(url=path, write_to=png_path)
                png_paths.append(png_path)
            
            with open(png_paths[0], "rb") as f: old_png_b64 = base64.b64encode(f.read()).decode('utf-8')
            with open(png_paths[1], "rb") as f: new_png_b64 = base64.b64encode(f.read()).decode('utf-8')

            prompt = visual_prompts.VISUAL_VERIFICATION_PROMPT.format(issue_description=issue_description)
            message = HumanMessage(content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{old_png_b64}"}},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{new_png_b64}"}},
            ])
            
            response = self.inspector_llm.invoke([message])
            parsed_json = self._parse_json_from_response(response.content, str(attempt), "verification_report")

            if "is_resolved" not in parsed_json:
                return {"is_resolved": False, "reasoning": "AI verifier returned an invalid JSON format."}

            return parsed_json
        except Exception as e:
            print(f"An unexpected error occurred during fix verification: {e}")
            return {"is_resolved": False, "reasoning": f"An exception occurred: {e}"}

    def _inspect_image_for_issues(self, code: str, svg_path: str, circuit_idea: str, attempt_name: str) -> List[Dict]:
        try:
            png_path = os.path.join(os.path.dirname(svg_path), f"inspection_{attempt_name}.png")
            cairosvg.svg2png(url=svg_path, write_to=png_path)
            with open(png_path, "rb") as f: b64_image = base64.b64encode(f.read()).decode('utf-8')

            prompt = visual_prompts.VISUAL_INSPECTION_PROMPT.format(circuit_idea=circuit_idea, code=code)
            message = HumanMessage(content=[{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_image}"}}])
            
            response = self.inspector_llm.invoke([message])
            parsed_json = self._parse_json_from_response(response.content, attempt_name, "inspection_report")
            
            if "issues" not in parsed_json or not isinstance(parsed_json.get("issues"), list):
                 error_msg = f"AI inspector returned an invalid JSON format. Got: {str(parsed_json)[:200]}"
                 print(error_msg)
                 return [{"problem_description": error_msg, "code_snippet": "", "suggested_fix": ""}]
            return parsed_json.get("issues", [])
        except Exception as e:
            error_msg = f"An unexpected error occurred during inspection: {e}"
            print(error_msg)
            traceback.print_exc()
            return [{"problem_description": error_msg, "code_snippet": "", "suggested_fix": ""}]