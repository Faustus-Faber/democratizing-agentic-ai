# %% [markdown]
# # Cell 3: Agentic Environment Agents
# Three recursive agentic loop implementations for the evaluation:
# - **Environment A**: Bash system administration
# - **Environment B**: Python logic and debugging
# - **Environment C**: Simulated web retrieval with mock knowledge base

# %% Cell 3: Imports
import re
import json
import subprocess
from typing import List, Dict, Tuple, Optional


# %% Cell 3a: Environment A — Recursive Bash Agent
class RecursiveBashAgent:
    """Evaluates SLM stability in multi-turn bash command execution."""

    def __init__(self, llm_generate_function, max_turns=10):
        self.generate = llm_generate_function
        self.max_turns = max_turns
        self.history: List[Dict[str, str]] = []
        self.system_prompt = (
            "You are a Bash System Administrator AI. You must solve the objective by executing bash commands. "
            "You must first think about your plan inside <thought>...</thought> tags. "
            "Then, provide EXACTLY ONE bash command inside a ```bash\n...\n``` block. "
            "I will execute your command and return the terminal output. "
            "If the objective is completely solved, you MUST explicitly output the exact string '[TASK_COMPLETE]'. "
            "If you fail to format this correctly, or refuse to output it, the task will be marked as a failure."
        )

    def _extract_code_block(self, response: str) -> Optional[str]:
        """Extracts the first bash command block from an LLM response."""
        match = re.search(r'```(?:bash|sh|shell)?\s*\n?(.*?)```', response, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        if "<thought>" not in response:
            return response.strip()
        return None

    def _execute(self, command: str) -> Tuple[str, int]:
        """Executes a bash command with timeout and captures output."""
        if not command:
            return "Error: No command provided.", 1
        print(f"\n[EXECUTING]: {command}")
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
        output = result.stdout
        if result.returncode != 0:
            output += "\n" + result.stderr
        return output.strip()[:1000], result.returncode

    def _build_trajectory_context(self, trajectory: list) -> str:
        """Builds sliding-window trajectory context for injection into the next prompt."""
        if not trajectory:
            return "Execution Trajectory: None yet.\n"
        context = "Execution Trajectory:\n"
        for t in trajectory[-2:]:
            action = t['action'].replace('\\n', ' ').strip()
            outcome = str(t['outcome'])[:500].replace('\\n', ' ').strip()
            context += f"  - Turn: {t['turn']}\n    Action: {action}\n    Outcome: {outcome}\n"
        return context

    def _judge_completion(self, objective: str, trajectory: list) -> bool:
        """Uses the SLM as a judge to verify task completion."""
        final_output = str(trajectory[-1]['outcome'])[:1000] if trajectory else "No actions taken."
        judge_prompt = (
            f"Objective: {objective}\n\nFinal Output State:\n{final_output}\n\n"
            "Did the final output successfully satisfy all requirements of the objective? "
            "You are a highly critical judge. Look for explicit proof of success in the output. "
            "If the output shows an error, or if there is no concrete verification that the task was completed, "
            "you MUST answer '[VERDICT: NO]'. "
            "Provide a brief reasoning evaluation first, then definitively state your conclusion "
            "STRICTLY as either '[VERDICT: YES]' or '[VERDICT: NO]'."
        )
        judge_history = [
            {"role": "system", "content": "You are a stark, objective evaluation judge. Your only job is to evaluate if the objective was met based on the provided output. You must NEVER write code. You must provide reasoning followed seamlessly by either '[VERDICT: YES]' or '[VERDICT: NO]'."},
            {"role": "user", "content": judge_prompt}
        ]
        judge_res = str(self.generate(judge_history))
        print(f"[LLM JUDGE]: {judge_res}")
        return "[VERDICT: YES]" in judge_res.upper()

    def run_agentic_loop(self, objective: str) -> dict:
        """Runs the multi-turn recursive loop with trajectory context injection and actor-critic."""
        print(f"=== Starting Agentic Loop for Objective: {objective} ===")

        metrics = {
            "turns_taken": 0, "success": False, "errors_encountered": 0,
            "thinking_integrity": True, "reasoning_length": 0,
            "backtracking_triggered": 0, "self_corrections": 0
        }
        trajectory = []

        for turn in range(self.max_turns):
            print(f"\n--- Turn {turn + 1}/{self.max_turns} ---")

            trajectory_context = self._build_trajectory_context(trajectory)
            dynamic_prompt = (
                f"OBJECTIVE: {objective}\n\n{trajectory_context}\n"
                "Think inside <thought> tags whether the objective is fully solved. "
                "If YES, output [TASK_COMPLETE]. If NO, provide your next bash command inside a ```bash block."
            )

            self.history = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": dynamic_prompt}
            ]

            response = str(self.generate(self.history))
            print(f"[AGENT]: {response}")

            # Track thinking integrity
            thought_match = re.search(r'<thought>(.*?)</thought>', response, re.DOTALL)
            if thought_match:
                metrics["reasoning_length"] += len(thought_match.group(1).strip())
            else:
                metrics["thinking_integrity"] = False

            task_complete_claimed = "[TASK_COMPLETE]" in response

            # Actor-Critic self-correction
            cmd = self._extract_code_block(response)
            if cmd:
                critic_prompt = f"You proposed: `{cmd}`. Identify any syntax/logic flaws. If perfect, output 'SAFE'. Otherwise, provide the corrected block."
                critic_history = self.history + [
                    {"role": "assistant", "content": response},
                    {"role": "user", "content": critic_prompt}
                ]
                critic_response = str(self.generate(critic_history))
                corrected_cmd = self._extract_code_block(critic_response)
                if corrected_cmd and "SAFE" not in critic_response.upper():
                    print(f"[CRITIC SELF-CORRECTION TRIGGERED]: {corrected_cmd}")
                    cmd = corrected_cmd
                    metrics["self_corrections"] += 1

                output, exit_code = self._execute(cmd)

                if exit_code != 0:
                    metrics["errors_encountered"] += 1
                    if trajectory and trajectory[-1].get("exit_code") != 0:
                        metrics["backtracking_triggered"] += 1

                print(f"[OUTPUT]: {output}")
                trajectory.append({
                    "turn": turn + 1, "action": cmd,
                    "outcome": output or "Exited normally", "exit_code": exit_code
                })
            elif not task_complete_claimed:
                print("[ERROR] Agent failed to produce a bash block.")
                metrics["errors_encountered"] += 1
                trajectory.append({
                    "turn": turn + 1, "action": "None",
                    "outcome": "Syntax Hallucination: No bash block found.", "exit_code": 1
                })

            if task_complete_claimed:
                print("Task claimed as complete! Triggering LLM-as-a-Judge validation...")
                metrics["success"] = self._judge_completion(objective, trajectory)
                if not metrics["success"]:
                    print("LLM Judge determined objective was missed.")
                metrics["turns_taken"] = turn + 1
                return metrics

        print("\n=== Agent Halted: Max Turns Exceeded ===")
        metrics["turns_taken"] = self.max_turns
        return metrics


# %% Cell 3b: Environment B — Recursive Python Agent
class RecursivePythonAgent:
    """Evaluates SLM stability in multi-turn Python code generation and debugging."""

    def __init__(self, llm_generate_function, max_turns=10):
        self.generate = llm_generate_function
        self.max_turns = max_turns
        self.history: List[Dict[str, str]] = []
        self.system_prompt = (
            "You are a Senior Python Developer AI. You must solve the objective by writing and running Python code. "
            "You must first think about your plan inside <thought>...</thought> tags. "
            "Then, provide EXACTLY ONE python script inside a ```python\n...\n``` block. "
            "I will save it to 'temp_script.py', execute it, and return the stdout/stderr. "
            "If the code throws an error, you must analyze the traceback and rewrite the code to fix it. "
            "Once the objective is solved and the code runs successfully, you MUST explicitly output the exact string '[TASK_COMPLETE]'. "
            "If you fail to format this correctly, or refuse to output it, the task will be marked as a failure."
        )

    def _extract_code_block(self, response: str) -> Optional[str]:
        """Extracts the first python code block from an LLM response."""
        match = re.search(r'```(?:python|py)?\s*\n(.*?)(?:```|$)', response, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        if "import" in response or "def " in response:
            return response.replace("<thought>", "").replace("</thought>", "").strip()
        return None

    def _execute(self, code: str) -> Tuple[str, int]:
        """Writes code to temp file and executes it."""
        if not code:
            return "Error: No python code provided.", 1
        with open("temp_script.py", "w") as f:
            f.write(code)
        print(f"\n[EXECUTING Python Script...]")
        result = subprocess.run(["python", "temp_script.py"], capture_output=True, text=True, timeout=15)
        output = result.stdout
        if result.returncode != 0:
            output += "\n" + result.stderr
        return output.strip()[:1500], result.returncode

    def _build_trajectory_context(self, trajectory: list) -> str:
        """Builds sliding-window trajectory context for injection into the next prompt."""
        if not trajectory:
            return "Execution Trajectory: None yet.\n"
        context = "Execution Trajectory:\n"
        for t in trajectory[-2:]:
            action = t['action'].replace('\\n', ' ').strip()
            outcome = str(t['outcome'])[:500].replace('\\n', ' ').strip()
            context += f"  - Turn: {t['turn']}\n    Action: {action}\n    Outcome: {outcome}\n"
        return context

    def _judge_completion(self, objective: str, trajectory: list) -> bool:
        """Uses the SLM as a judge to verify task completion."""
        final_output = str(trajectory[-1]['outcome'])[:1000] if trajectory else "No actions taken."
        judge_prompt = (
            f"Objective: {objective}\n\nFinal Output State:\n{final_output}\n\n"
            "Did the final output successfully satisfy all requirements of the objective? "
            "You are a highly critical judge. Look for explicit proof of success in the output "
            "(e.g., correct printed values, no tracebacks). "
            "If the output shows an error, or if there is no concrete verification that the code logic worked as requested, "
            "you MUST answer '[VERDICT: NO]'. "
            "Provide a brief reasoning evaluation first, then definitively state your conclusion "
            "STRICTLY as either '[VERDICT: YES]' or '[VERDICT: NO]'."
        )
        judge_history = [
            {"role": "system", "content": "You are a stark, objective evaluation judge. Your only job is to evaluate if the objective was met based on the provided output. You must NEVER write code. You must provide reasoning followed seamlessly by either '[VERDICT: YES]' or '[VERDICT: NO]'."},
            {"role": "user", "content": judge_prompt}
        ]
        judge_res = str(self.generate(judge_history))
        print(f"[LLM JUDGE]: {judge_res}")
        return "[VERDICT: YES]" in judge_res.upper()

    def run_agentic_loop(self, objective: str) -> dict:
        """Runs the multi-turn recursive loop with trajectory context injection and actor-critic."""
        print(f"=== Starting Environment B: {objective} ===")

        metrics = {
            "turns_taken": 0, "success": False, "errors_encountered": 0,
            "thinking_integrity": True, "reasoning_length": 0,
            "backtracking_triggered": 0, "self_corrections": 0
        }
        trajectory = []

        for turn in range(self.max_turns):
            print(f"\n--- Turn {turn + 1}/{self.max_turns} ---")

            trajectory_context = self._build_trajectory_context(trajectory)
            dynamic_prompt = (
                f"OBJECTIVE: {objective}\n\n{trajectory_context}\n"
                "Think inside <thought> tags whether the code has successfully solved the objective. "
                "If YES, output [TASK_COMPLETE]. If NO, provide your next python script inside a ```python block."
            )

            self.history = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": dynamic_prompt}
            ]

            response = str(self.generate(self.history))
            print(f"[AGENT]: {response}")

            thought_match = re.search(r'<thought>(.*?)</thought>', response, re.DOTALL)
            if thought_match:
                metrics["reasoning_length"] += len(thought_match.group(1).strip())
            else:
                metrics["thinking_integrity"] = False

            task_complete_claimed = "[TASK_COMPLETE]" in response

            code = self._extract_code_block(response)
            if code:
                critic_prompt = f"You proposed: `{code}`. Identify any syntax/logic flaws. If perfect, output 'SAFE'. Otherwise, provide the corrected block."
                critic_history = self.history + [
                    {"role": "assistant", "content": response},
                    {"role": "user", "content": critic_prompt}
                ]
                critic_response = str(self.generate(critic_history))
                corrected_code = self._extract_code_block(critic_response)
                if corrected_code and "SAFE" not in critic_response.upper():
                    print(f"[CRITIC SELF-CORRECTION TRIGGERED]: \n{corrected_code}")
                    code = corrected_code
                    metrics["self_corrections"] += 1

                output, exit_code = self._execute(code)

                if exit_code != 0:
                    metrics["errors_encountered"] += 1
                    if trajectory and trajectory[-1].get("exit_code") != 0:
                        metrics["backtracking_triggered"] += 1

                print(f"[OUTPUT]: {output}")
                trajectory.append({
                    "turn": turn + 1, "action": "Python Script Executed",
                    "outcome": output or "Exited normally", "exit_code": exit_code
                })
            elif not task_complete_claimed:
                print("[ERROR] Agent failed to produce Python code.")
                metrics["errors_encountered"] += 1
                trajectory.append({
                    "turn": turn + 1, "action": "None",
                    "outcome": "Syntax Hallucination: No python block found.", "exit_code": 1
                })

            if task_complete_claimed:
                print("Task claimed as complete! Triggering LLM-as-a-Judge validation...")
                metrics["success"] = self._judge_completion(objective, trajectory)
                if not metrics["success"]:
                    print("LLM Judge determined objective was missed.")
                metrics["turns_taken"] = turn + 1
                return metrics

        print("\n=== Agent Halted: Max Turns Exceeded ===")
        metrics["turns_taken"] = self.max_turns
        return metrics


# %% Cell 3c: Mock Knowledge Base for Environment C
KNOWLEDGE_DB = [
    {"keys": ["qlora", "paper", "author"], "content": "The QLoRA paper was published in 2023. Primary authors are Tim Dettmers, Artidoro Pagnoni, Ari Holtzman, and Luke Zettlemoyer."},
    {"keys": ["dettmers", "tim", "university", "affiliation"], "content": "Tim Dettmers is a researcher affiliated with the University of Washington."},
    {"keys": ["gemma", "3", "size", "parameter"], "content": "Google Gemma 3 model sizes include 4B, 12B, and 27B parameters."},
    {"keys": ["llama", "3.1", "size", "parameter"], "content": "Meta Llama 3.1 models come in 8B, 70B, and 405B parameter sizes."},
    {"keys": ["dpo", "direct preference optimization"], "content": "Direct Preference Optimization (DPO) aligns language models with human preferences directly."},
    {"keys": ["replace", "rlhf", "earlier", "reinforcement learning"], "content": "DPO was specifically designed to replace Reinforcement Learning from Human Feedback (RLHF)."},
    {"keys": ["llama 2", "architecture", "gqa", "attention"], "content": "LLaMA 2 used Grouped Query Attention (GQA) only in its larger 70B models."},
    {"keys": ["llama 3", "architecture", "gqa", "difference"], "content": "LLaMA 3 improved inference scalability by using Grouped Query Attention (GQA) across all model sizes (8B and 70B)."},
    {"keys": ["moe", "mixture of experts", "gating", "mechanism"], "content": "Mixture of Experts (MoE) uses a 'router' or 'gating network' that calculates softmax probabilities to dynamically route each token to the top-K expert networks."},
    {"keys": ["flashattention 2", "flash attention", "improved"], "content": "FlashAttention 2 improved on the original by parallelizing across the sequence length dimension, significantly increasing hardware utilization speeds."},
    {"keys": ["qwen", "3.5", "flash"], "content": "The Qwen 3.5 architecture natively utilizes FlashAttention 2 to handle its expanded context windows."},
    {"keys": ["nf4", "quantization", "bitsandbytes", "datatype", "definition"], "content": "NF4 (NormalFloat4) is a data type utilized by bitsandbytes for 4-bit quantization."},
    {"keys": ["nf4", "distribution", "optimized"], "content": "NF4 is mathematically optimized for zero-centered, normally distributed weights."},
    {"keys": ["react", "testing framework", "evaluates"], "content": "The ReAct testing framework evaluates Large Language Models as autonomous agents capable of interleaving reasoning and action."},
    {"keys": ["react", "paper", "components", "core", "summarize"], "content": "The ReAct paper's two core components are generating reasoning traces (thoughts) and taking task-specific actions (like API calls) in an interleaved loop."},
    {"keys": ["phi-4", "phi-4-mini", "context", "window", "length"], "content": "The microsoft/phi-4-mini model has a context window length of 128k tokens."},
    {"keys": ["gemma-3-4b", "gemma 3", "context", "window", "compare"], "content": "The Google gemma-3-4b model features a context window length of 128k tokens."},
    {"keys": ["colab", "gpu", "free tier", "hardware", "upgraded"], "content": "Google Colab previously upgraded free tier users from legacy K80s to NVIDIA T4 GPUs."},
    {"keys": ["t4", "colab", "primary", "still"], "content": "NVIDIA T4s are still the primary free tier GPU on Google Colab."},
    {"keys": ["safetensors", "huggingface", "format", "what"], "content": "Safetensors is a new format developed by HuggingFace for storing tensors."},
    {"keys": ["safetensors", "secure", "pickle", "bin", "pt", "traditional"], "content": "Safetensors is more secure than PyTorch pickle (.pt/.bin) files because it structurally prevents arbitrary code execution upon loading."},
    {"keys": ["rotary position embeddings", "rope", "what"], "content": "Rotary Position Embeddings (RoPE) encode position information into attention layers by applying rotation matrices."},
    {"keys": ["rope", "foundational model", "popularized", "first"], "content": "RoPE was popularized globally by the 'RoFormer' foundational model as an alternative to absolute embeddings."},
    {"keys": ["fp16", "bf16", "int8", "compute types", "inference", "difference"], "content": "FP16, BF16, and INT8 are low-precision compute types used in deep learning inference."},
    {"keys": ["bf16", "b", "stand for"], "content": "The 'B' in BF16 stands for 'Brain', referencing its creation by Google Brain as Bfloat16."},
    {"keys": ["speculative decoding", "purpose", "large language models"], "content": "The primary purpose of Speculative Decoding is to accelerate LLM inference speeds by predicting tokens ahead using a small draft model."},
    {"keys": ["speculative decoding", "quality", "affect", "speed"], "content": "Speculative Decoding does not affect the final output quality, providing mathematically identical outputs but faster."},
    {"keys": ["lmsys", "chatbot arena", "what"], "content": "The LMSys Chatbot Arena is an open leaderboard where humans evaluate LLMs blindly by voting."},
    {"keys": ["chatbot arena", "leaderboard", "#1", "2024", "end"], "content": "At the end of 2024, the #1 ranked model on the LMSys Chatbot Arena leaderboard was OpenAI's GPT-4o."},
    {"keys": ["continuous batching", "in-flight", "vllm", "inference", "means"], "content": "Continuous Batching (in-flight batching) in vLLM optimizes batch grouping at the iteration sequence level."},
    {"keys": ["continuous batching", "throughput", "why", "improve"], "content": "It improves throughput by allowing new generation requests to be instantly inserted into an executing batch as soon as earlier requests finish, maintaining 100% GPU utilization."},
    {"keys": ["system prompt", "user prompt", "differently", "interacting"], "content": "A System Prompt establishes persistent behavioral instructions naturally overriding User Prompts which contain individual queries."},
    {"keys": ["system prompt", "chat templates", "format"], "content": "Chat templates format system prompts using specific control tokens, often enveloped by <|system|> tags to distinguish them mechanically."},
    {"keys": ["deepseek-r1", "architecture", "differs", "fundamental"], "content": "The DeepSeek-R1 architecture differs fundamentally by leaning intensely on GRPO reinforcement learning phases."},
    {"keys": ["deepseek", "chain-of-thought", "tokens", "auto-regressive"], "content": "Unlike standard auto-regressive responses, DeepSeek-R1 natively emits long chain-of-thought reasoning tokens explicitly inside <think> tags before providing the final user answer."},
    {"keys": ["small models", "10b", "contextual myopia", "forgetting", "struggle"], "content": "Small models struggle with 'Contextual Myopia' where they 'forget' their system prompts over long conversations."},
    {"keys": ["contextual myopia", "why", "struggle", "forgetting"], "content": "This phenomenon occurs because limited attention head capacity and fewer parameter matrices cause the embeddings of early system instructions to be heavily diluted when recent user queries flood the limited attention window."},
    {"keys": ["model collapse", "ai research"], "content": "Model Collapse is a statistical phenomenon in AI generative models."},
    {"keys": ["model collapse", "synthetic data", "causes", "purely"], "content": "Training models purely on synthetic data generated by previous generation models causes Model Collapse, as it loses original data distribution tails over generations."}
]


# %% Cell 3c: Environment C — Web Retrieval Agent
class WebRetrievalAgent:
    """Evaluates SLM stability in simulated web search with multi-hop reasoning."""

    def __init__(self, llm_generate_function, max_turns=10):
        self.generate = llm_generate_function
        self.max_turns = max_turns
        self.history: List[Dict[str, str]] = []
        self.system_prompt = (
            "You are an Open-Domain Research Agent. You must answer the user's complex question. "
            "You cannot answer from memory. You MUST search the database first. "
            "Think inside <thought>...</thought> tags.\n"
            "You have TWO actions available. You must output EXACTLY ONE JSON block ```json\n...\n``` containing one of these actions:\n"
            '1. To search: {"action": "search", "query": "Subject"}\n'
            '2. To submit final answer: {"action": "answer", "text": "Your detailed exact final answer"}\n'
            "Search multiple times if needed. When you have the complete answer, use the 'answer' action.\n"
            "If you fail to format your actions as JSON, the task will be marked as a failure."
        )

    def _extract_json(self, response: str) -> Optional[dict]:
        """Extracts a JSON action block from the LLM response."""
        match = re.search(r'```(?:json)?\s*\n(.*?)(?:```|$)', response, re.DOTALL | re.IGNORECASE)
        target_str = match.group(1).strip() if match else response.strip()
        try:
            start_idx = target_str.find('{')
            end_idx = target_str.rfind('}')
            if start_idx != -1 and end_idx != -1:
                return json.loads(target_str[start_idx:end_idx + 1])
            return json.loads(target_str)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON syntax formatting."}

    def _execute_search(self, query: str) -> str:
        """Searches the mock KNOWLEDGE_DB using keyword matching."""
        if not query:
            return "Search query empty."

        query_lower = query.lower()
        results: List[Tuple[int, str]] = []

        for item in KNOWLEDGE_DB:
            score = sum(
                1 for kw in item["keys"]
                if re.search(r'\b' + re.escape(kw.lower()) + r'\b', query_lower)
            )
            if score > 0:
                results.append((score, item["content"]))

        if not results:
            query_words = set(re.findall(r'\w{4,}', query_lower))
            for item in KNOWLEDGE_DB:
                score = sum(
                    1 for kw in item["keys"]
                    if set(re.findall(r'\w{4,}', kw.lower())).intersection(query_words)
                )
                if score > 0:
                    results.append((score, item["content"]))

        if not results:
            return f"No results found for '{query}'. Try a different keyword."

        results.sort(key=lambda x: x[0], reverse=True)
        top_results = [res[1] for res in results[:2]]
        return "Search Results:\n- " + "\n- ".join(top_results)

    def _build_trajectory_context(self, trajectory: list) -> str:
        """Builds trajectory context from full history (no windowing for web) for prompt injection."""
        if not trajectory:
            return "Execution Trajectory: None yet.\n"
        context = "Execution Trajectory:\n"
        for t in trajectory:
            action = str(t['action']).replace('\\n', ' ').strip()
            outcome = str(t['outcome'])[:500].replace('\\n', ' ').strip()
            context += f"  - Turn: {t['turn']}\n    Action: {action}\n    Outcome: {outcome}\n"
        return context

    def _judge_completion(self, objective: str, final_answer: str) -> bool:
        """Uses the SLM as a judge to verify the web answer."""
        judge_prompt = (
            f"Objective: {objective}\n\nFinal Output State:\n{final_answer[-1000:]}\n\n"
            "Does this final response definitively and correctly answer the specific objective? "
            "You are a highly critical judge. If the answer is vague, hallucinates facts not found in the search context, "
            "or misses the core question, you MUST answer '[VERDICT: NO]'. "
            "Provide a brief reasoning evaluation first, then definitively state your conclusion "
            "STRICTLY as either '[VERDICT: YES]' or '[VERDICT: NO]'."
        )
        judge_history = [
            {"role": "system", "content": "You are a stark, objective evaluation judge. Your only job is to evaluate if the objective was met based on the provided output. You must NEVER write code. You must provide reasoning followed seamlessly by either '[VERDICT: YES]' or '[VERDICT: NO]'."},
            {"role": "user", "content": judge_prompt}
        ]
        judge_res = str(self.generate(judge_history))
        print(f"[LLM JUDGE]: {judge_res}")
        return "[VERDICT: YES]" in judge_res.upper()

    def run_agentic_loop(self, objective: str) -> dict:
        """Runs the multi-turn web retrieval loop with trajectory context injection and actor-critic."""
        print(f"=== Starting Environment C: {objective} ===")

        metrics = {
            "turns_taken": 0, "success": False, "errors_encountered": 0,
            "thinking_integrity": True, "reasoning_length": 0,
            "backtracking_triggered": 0, "self_corrections": 0
        }
        trajectory = []

        for turn in range(self.max_turns):
            print(f"\n--- Turn {turn + 1}/{self.max_turns} ---")

            trajectory_context = self._build_trajectory_context(trajectory)
            dynamic_prompt = (
                f"OBJECTIVE: {objective}\n\n{trajectory_context}\n"
                "Think inside <thought> tags whether you have gathered all necessary information. "
                "If YES, output the 'answer' JSON action. If NO, output the 'search' JSON action."
            )

            self.history = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": dynamic_prompt}
            ]

            response = str(self.generate(self.history))
            print(f"[AGENT]: {response}")

            thought_match = re.search(r'<thought>(.*?)</thought>', response, re.DOTALL)
            if thought_match:
                metrics["reasoning_length"] += len(thought_match.group(1).strip())
            else:
                metrics["thinking_integrity"] = False

            action_json = self._extract_json(response)

            # Handle answer action
            if action_json and action_json.get("action") == "answer":
                print("Task claimed as complete! Triggering LLM-as-a-Judge validation...")
                final_text = action_json.get("text", str(action_json))
                metrics["success"] = self._judge_completion(objective, final_text)
                if not metrics["success"]:
                    print("LLM Judge determined objective was missed.")
                metrics["turns_taken"] = turn + 1
                return metrics

            # Handle search action
            if action_json and "action" in action_json:
                critic_prompt = f"You proposed: `{json.dumps(action_json)}`. Identify any syntax/logic flaws. If perfect, output 'SAFE'. Otherwise, provide the corrected JSON block."
                critic_history = self.history + [
                    {"role": "assistant", "content": response},
                    {"role": "user", "content": critic_prompt}
                ]
                critic_response = str(self.generate(critic_history))
                corrected_json = self._extract_json(critic_response)
                if corrected_json and "SAFE" not in critic_response.upper() and "error" not in corrected_json:
                    print(f"[CRITIC SELF-CORRECTION TRIGGERED]: \n{corrected_json}")
                    action_json = corrected_json
                    metrics["self_corrections"] += 1

                if "error" in action_json:
                    output, exit_code = action_json["error"], 1
                else:
                    output = self._execute_search(action_json.get("query", ""))
                    exit_code = 0 if "Search Results:" in output else 1

                if exit_code != 0:
                    metrics["errors_encountered"] += 1
                    if trajectory and trajectory[-1].get("exit_code") != 0:
                        metrics["backtracking_triggered"] += 1

                print(f"[OUTPUT]: {output}")
                trajectory.append({
                    "turn": turn + 1,
                    "action": f"Web Search: {action_json.get('query', '')}",
                    "outcome": output, "exit_code": exit_code
                })
            else:
                print("[ERROR] Agent failed to produce valid JSON.")
                metrics["errors_encountered"] += 1
                trajectory.append({
                    "turn": turn + 1, "action": "None",
                    "outcome": "Syntax Hallucination: No json block found.", "exit_code": 1
                })

        metrics["turns_taken"] = self.max_turns
        return metrics
