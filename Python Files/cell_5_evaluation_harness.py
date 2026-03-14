# %% [markdown]
# # Cell 5: Evaluation Harness
# Orchestrates the full experiment grid: 4 models × 2 precisions × 3 environments = 24 runs.
# Each run executes 20 tasks through the corresponding agentic loop,
# collecting SDM, QHR, thinking integrity, and supplementary metrics.
#
# **Colab Usage**: Due to T4 VRAM constraints (~15GB), only one model/precision
# can be loaded at a time. Change `target_models`, `target_precisions`, and
# `target_environments` in the __main__ block to run a specific configuration.
# After downloading results, restart runtime and load the next configuration.

# %% Cell 5: Dependencies
import json
import csv
import time
import torch
import gc
import os

# When run as a standalone script, import from the cell files.
# When pasted sequentially into a Colab notebook, these are already in scope.
try:
    from cell_1_slm_inference import SLMInferencePipeline
    from cell_3_agentic_environments import RecursiveBashAgent, RecursivePythonAgent, WebRetrievalAgent
    from cell_2_metrics_engine import calculate_sdm, calculate_qhr, get_vram_usage_gb
    from cell_4_task_benchmark import generate_benchmark
except ModuleNotFoundError:
    pass

# %% Cell 5: Experiment Configuration
MODELS = [
    "Qwen/Qwen3.5-4B",
    "microsoft/Phi-4-mini-instruct",
    "google/gemma-3-4b-it",
    "meta-llama/Llama-3.1-8B-Instruct"
]
PRECISIONS = ["4bit", "8bit"]
ENVIRONMENTS = ["Bash", "Python", "Web"]
MAX_TURNS = 5

# Full 24-configuration grid (4 models × 2 precisions × 3 environments)
EXPERIMENT_GRID = [
    {"model": m, "precision": p, "environment": e}
    for m in MODELS for p in PRECISIONS for e in ENVIRONMENTS
]

ENV_AGENT_MAP = {
    "Bash": ("Env_A_Bash", RecursiveBashAgent),
    "Python": ("Env_B_Python", RecursivePythonAgent),
    "Web": ("Env_C_Web", WebRetrievalAgent),
}


# %% Cell 5: Task Runner
def run_environment_tasks(agent, dataset, env_name, model_id, precision, results_list, out_dir):
    """Executes all tasks for a given agent/environment and collects metrics."""
    env_results = []
    for task_data in dataset:
        print(f"  -> Running {env_name} Task: {task_data['id']}")
        start_time = time.time()
        try:
            result = agent.run_agentic_loop(task_data['task'])
            latency = time.time() - start_time
            row = {
                "model": model_id, "precision": precision, "environment": env_name,
                "task_id": task_data['id'], "task_completed": result['success'],
                "turns_taken": result['turns_taken'],
                "sdm": calculate_sdm(result['turns_taken'], MAX_TURNS, result['success']),
                "qhr": calculate_qhr(result['errors_encountered'], result['turns_taken']),
                "thinking_integrity": result.get('thinking_integrity', False),
                "reasoning_length": result.get('reasoning_length', 0),
                "self_corrections": result.get('self_corrections', 0),
                "backtracking_triggered": result.get('backtracking_triggered', 0),
                "latency_sec": latency, "vram_gb": get_vram_usage_gb()
            }
        except RuntimeError as e:
            print(f"CRITICAL ERROR (Likely OOM) on task {task_data['id']}: {e}")
            row = {
                "model": model_id, "precision": precision, "environment": env_name,
                "task_id": task_data['id'], "task_completed": False, "turns_taken": 0,
                "sdm": 0.0, "qhr": 0.0, "thinking_integrity": False, "reasoning_length": 0,
                "self_corrections": 0, "backtracking_triggered": 0,
                "latency_sec": 0.0, "vram_gb": 0.0, "error": "OOM CRASH"
            }
        except Exception as e:
            print(f"General task failure on {task_data['id']}: {e}")
            continue

        results_list.append(row)
        env_results.append(row)

    # Write per-environment CSV
    if env_results:
        env_dir = os.path.join(out_dir, env_name)
        os.makedirs(env_dir, exist_ok=True)
        safe_model = model_id.replace('/', '_')
        csv_path = os.path.join(env_dir, f"eval_{safe_model}_{precision}_{env_name.lower()}.csv")
        fieldnames = list(env_results[0].keys())
        with open(csv_path, "w", newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(env_results)
        print(f"  [SAVED] {csv_path}")


# %% Cell 5: Main Evaluation Loop
def run_evaluation(target_models, target_precisions, target_environments, base_out_dir):
    """Runs the evaluation grid for the specified models, precisions, and environments."""
    master_results = []
    benchmark = generate_benchmark()

    for model_id in target_models:
        for precision in target_precisions:
            print(f"\n{'=' * 60}")
            print(f"EVAL: {model_id} | {precision}")
            print(f"{'=' * 60}\n")

            try:
                pipeline = SLMInferencePipeline(
                    model_id=model_id,
                    load_in_4bit=(precision == "4bit")
                )

                # Closure captures current pipeline reference
                current_pipeline = pipeline
                def generate_fn(messages, user=None):
                    return current_pipeline.generate(messages, user)

                run_dir = os.path.join(
                    base_out_dir, f"{model_id.replace('/', '_')}_{precision}"
                )
                os.makedirs(run_dir, exist_ok=True)

                for env_name in target_environments:
                    dataset_key, agent_cls = ENV_AGENT_MAP[env_name]
                    tasks = benchmark[dataset_key]
                    if not tasks:
                        continue
                    print(f"\n--- Environment {env_name} | {len(tasks)} tasks ---")
                    agent = agent_cls(generate_fn, MAX_TURNS)
                    run_environment_tasks(
                        agent, tasks, env_name, model_id, precision,
                        master_results, run_dir
                    )

            except Exception as e:
                print(f"Failed to load {model_id} in {precision}: {e}")

            # GPU cleanup between configurations
            if 'pipeline' in dir():
                del pipeline
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()

    # Save consolidated JSON
    safe_id = "_".join(m.replace('/', '_') for m in target_models)
    json_path = os.path.join(base_out_dir, f"results_{safe_id}.json")
    with open(json_path, "w") as f:
        json.dump(master_results, f, indent=2)
    print(f"\n[DONE] Results saved to {json_path}")


# %% Cell 5: Configuration Selector
# ═══════════════════════════════════════════════════════════════
# IMPORTANT: Colab T4 can only hold ONE model at a time.
# Uncomment the desired configuration block, run, download CSVs,
# then restart runtime and uncomment the next block.
#
# Full grid: 4 models × 2 precisions × 3 environments = 24 runs
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    BASE_DIR = "Evaluation_Datasets"
    os.makedirs(BASE_DIR, exist_ok=True)

    # ── Run 1: Qwen 3.5-4B (4-bit) — All Environments ──
    # run_evaluation(["Qwen/Qwen3.5-4B"], ["4bit"], ["Bash", "Python", "Web"], BASE_DIR)

    # ── Run 2: Qwen 3.5-4B (8-bit) — All Environments ──
    # run_evaluation(["Qwen/Qwen3.5-4B"], ["8bit"], ["Bash", "Python", "Web"], BASE_DIR)

    # ── Run 3: Phi-4-Mini (4-bit) — All Environments ──
    # run_evaluation(["microsoft/Phi-4-mini-instruct"], ["4bit"], ["Bash", "Python", "Web"], BASE_DIR)

    # ── Run 4: Phi-4-Mini (8-bit) — All Environments ──
    # run_evaluation(["microsoft/Phi-4-mini-instruct"], ["8bit"], ["Bash", "Python", "Web"], BASE_DIR)

    # ── Run 5: Gemma-3-4B (4-bit) — All Environments ──
    # run_evaluation(["google/gemma-3-4b-it"], ["4bit"], ["Bash", "Python", "Web"], BASE_DIR)

    # ── Run 6: Gemma-3-4B (8-bit) — All Environments ──
    # run_evaluation(["google/gemma-3-4b-it"], ["8bit"], ["Bash", "Python", "Web"], BASE_DIR)

    # ── Run 7: Llama-3.1-8B (4-bit) — All Environments ──
    # run_evaluation(["meta-llama/Llama-3.1-8B-Instruct"], ["4bit"], ["Bash", "Python", "Web"], BASE_DIR)

    # ── Run 8: Llama-3.1-8B (8-bit) — All Environments ──
    # run_evaluation(["meta-llama/Llama-3.1-8B-Instruct"], ["8bit"], ["Bash", "Python", "Web"], BASE_DIR)

    # ── OR: Run a single environment at a time (24 individual runs) ──
    # run_evaluation(["Qwen/Qwen3.5-4B"], ["4bit"], ["Bash"], BASE_DIR)      # Config 1/24
    # run_evaluation(["Qwen/Qwen3.5-4B"], ["4bit"], ["Python"], BASE_DIR)    # Config 2/24
    # run_evaluation(["Qwen/Qwen3.5-4B"], ["4bit"], ["Web"], BASE_DIR)       # Config 3/24
    # run_evaluation(["Qwen/Qwen3.5-4B"], ["8bit"], ["Bash"], BASE_DIR)      # Config 4/24
    # run_evaluation(["Qwen/Qwen3.5-4B"], ["8bit"], ["Python"], BASE_DIR)    # Config 5/24
    # run_evaluation(["Qwen/Qwen3.5-4B"], ["8bit"], ["Web"], BASE_DIR)       # Config 6/24
    # run_evaluation(["microsoft/Phi-4-mini-instruct"], ["4bit"], ["Bash"], BASE_DIR)    # Config 7/24
    # run_evaluation(["microsoft/Phi-4-mini-instruct"], ["4bit"], ["Python"], BASE_DIR)  # Config 8/24
    # run_evaluation(["microsoft/Phi-4-mini-instruct"], ["4bit"], ["Web"], BASE_DIR)     # Config 9/24
    # run_evaluation(["microsoft/Phi-4-mini-instruct"], ["8bit"], ["Bash"], BASE_DIR)    # Config 10/24
    # run_evaluation(["microsoft/Phi-4-mini-instruct"], ["8bit"], ["Python"], BASE_DIR)  # Config 11/24
    # run_evaluation(["microsoft/Phi-4-mini-instruct"], ["8bit"], ["Web"], BASE_DIR)     # Config 12/24
    # run_evaluation(["google/gemma-3-4b-it"], ["4bit"], ["Bash"], BASE_DIR)    # Config 13/24
    # run_evaluation(["google/gemma-3-4b-it"], ["4bit"], ["Python"], BASE_DIR)  # Config 14/24
    # run_evaluation(["google/gemma-3-4b-it"], ["4bit"], ["Web"], BASE_DIR)     # Config 15/24
    # run_evaluation(["google/gemma-3-4b-it"], ["8bit"], ["Bash"], BASE_DIR)    # Config 16/24
    # run_evaluation(["google/gemma-3-4b-it"], ["8bit"], ["Python"], BASE_DIR)  # Config 17/24
    # run_evaluation(["google/gemma-3-4b-it"], ["8bit"], ["Web"], BASE_DIR)     # Config 18/24
    # run_evaluation(["meta-llama/Llama-3.1-8B-Instruct"], ["4bit"], ["Bash"], BASE_DIR)    # Config 19/24
    # run_evaluation(["meta-llama/Llama-3.1-8B-Instruct"], ["4bit"], ["Python"], BASE_DIR)  # Config 20/24
    # run_evaluation(["meta-llama/Llama-3.1-8B-Instruct"], ["4bit"], ["Web"], BASE_DIR)     # Config 21/24
    # run_evaluation(["meta-llama/Llama-3.1-8B-Instruct"], ["8bit"], ["Bash"], BASE_DIR)    # Config 22/24
    # run_evaluation(["meta-llama/Llama-3.1-8B-Instruct"], ["8bit"], ["Python"], BASE_DIR)  # Config 23/24
    # run_evaluation(["meta-llama/Llama-3.1-8B-Instruct"], ["8bit"], ["Web"], BASE_DIR)     # Config 24/24

    print("Uncomment one run_evaluation() call above, then execute this cell.")
