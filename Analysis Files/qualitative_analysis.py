"""
Qualitative Analysis: Automated Failure Archetype Detection
============================================================
Parses Output.md trace files to programmatically detect and count
the four failure archetypes identified through manual coding:

  1. Reasoning Leakage     – reasoning text leaks into action execution
  2. Single-Step Stagnation – identical commands repeated across turns
  3. Code Truncation        – generated code cuts off mid-statement
  4. Verification Omission  – [TASK_COMPLETE] emitted inside code blocks

Usage:
    python qualitative_analysis.py [--results-dir ../Results] [--output report.csv]
"""

import os
import re
import csv
import argparse
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from typing import List, Dict, Tuple


# ══════════════════════════════════════════════════════════════
# Data Structures
# ══════════════════════════════════════════════════════════════

@dataclass
class TaskTrace:
    """A single task's execution trace from Output.md."""
    task_id: str
    objective: str
    turns: List[dict] = field(default_factory=list)
    outcome: str = ""
    archetypes: List[str] = field(default_factory=list)


@dataclass
class FileTrace:
    """One Output.md file representing a model×precision×env configuration."""
    filepath: str
    model: str = ""
    precision: str = ""
    environment: str = ""
    tasks: List[TaskTrace] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════
# Parsing
# ══════════════════════════════════════════════════════════════

def _parse_config_from_path(filepath: str) -> Tuple[str, str, str]:
    """Extracts model, precision, environment from the parent folder name."""
    folder = os.path.basename(os.path.dirname(filepath)).lower()

    model_map = {'gemma': 'Gemma-3', 'llama': 'Llama-3.1', 'llma': 'Llama-3.1',
                 'phi': 'Phi-4-Mini', 'qwen': 'Qwen-3.5'}
    model = next((v for k, v in model_map.items() if k in folder), folder.split("_")[0])

    precision = '4-bit' if '4bit' in folder else '8-bit' if '8bit' in folder else 'unknown'

    env_map = {'bash': 'Bash', 'python': 'Python', 'py': 'Python', 'web': 'Web'}
    environment = next((v for k, v in env_map.items() if k in folder), 'unknown')

    return model, precision, environment


def parse_output_md(filepath: str) -> FileTrace:
    """Parses an Output.md trace file into structured TaskTrace objects."""
    model, precision, env = _parse_config_from_path(filepath)
    file_trace = FileTrace(filepath=filepath, model=model,
                           precision=precision, environment=env)

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    # Split by task headers (three possible formats)
    task_splits = re.split(
        r'=== (?:Starting Agentic Loop for Objective|Starting Environment [ABC]): (.+?) ===',
        content
    )

    for i in range(1, len(task_splits), 2):
        objective = task_splits[i].strip()
        task_content = task_splits[i + 1] if i + 1 < len(task_splits) else ""

        # Extract task ID from preceding text
        preamble = task_splits[i - 1] if i > 0 else ""
        task_id_match = re.search(r'Running (?:Bash|Python|Web)(?: Task)?: (\w+)', preamble)
        if not task_id_match:
            task_id_match = re.search(r'((?:bash|py|web)_\d+)', preamble)
        task_id = task_id_match.group(1) if task_id_match else f"task_{i // 2 + 1}"

        task = TaskTrace(task_id=task_id, objective=objective)

        # Parse turns
        turn_splits = re.split(r'--- Turn (\d+)/\d+ ---', task_content)
        for j in range(1, len(turn_splits), 2):
            turn_content = turn_splits[j + 1] if j + 1 < len(turn_splits) else ""
            task.turns.append({
                'turn_num': int(turn_splits[j]),
                'agent_response': _extract_section(r'\[AGENT\]: (.*?)(?=\[CRITIC|\[EXECUTING\]|\Z)', turn_content),
                'executed': _extract_section(r'\[EXECUTING\]: (.*?)(?=\[OUTPUT\]|\Z)', turn_content),
                'output': _extract_section(r'\[OUTPUT\]: (.*?)(?=\n---|\n===|\Z)', turn_content),
                'self_corrected': bool(re.search(r'\[CRITIC SELF-CORRECTION TRIGGERED\]', turn_content)),
                'raw': turn_content,
            })

        # Determine outcome
        if "VERDICT: YES" in task_content:
            task.outcome = "success"
        elif "Max Turns Exceeded" in task_content:
            task.outcome = "max_turns"
        elif "VERDICT: NO" in task_content:
            task.outcome = "judge_rejected"
        else:
            task.outcome = "unknown"

        file_trace.tasks.append(task)

    return file_trace


def _extract_section(pattern: str, text: str) -> str:
    """Extracts a named section from turn content via regex."""
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""


# ══════════════════════════════════════════════════════════════
# Archetype Detectors
# ══════════════════════════════════════════════════════════════

# Natural-language words that indicate leakage when executed as shell commands
_NL_TOKENS = frozenset({
    'The', 'Let', 'Looking', 'It', 'Since', 'Wait', 'Actually',
    'However', 'This', 'I', 'Now', 'First', 'Next', 'After',
    'Based', 'So', 'Therefore', 'My', 'We', 'block.'
})

_LEAKAGE_PATTERNS = [
    re.compile(r'/bin/sh: \d+: \w+: not found'),
    re.compile(r'/bin/sh: \d+: Syntax error:.*unexpected'),
    re.compile(r'</think>'),
    re.compile(r'</thought>'),
]

_VALID_ENDINGS = ('```', '.', '!', '?', ')', ']', '}', '>',
                  'COMPLETE]', 'SAFE', '/thought>', '/think>')

_REASONING_STARTERS = re.compile(r'^\s*(The|Let|Looking|I need|Wait|Actually)')


def detect_reasoning_leakage(task: TaskTrace) -> int:
    """Archetype 1: Reasoning text leaks into action execution."""
    count = 0
    for turn in task.turns:
        output = turn.get('output', '')
        executed = turn.get('executed', '')

        for pattern in _LEAKAGE_PATTERNS:
            if pattern.search(output):
                word_matches = re.findall(r'/bin/sh: \d+: (\w+): not found', output)
                if any(w in _NL_TOKENS for w in word_matches) or not word_matches:
                    count += 1
                    break

        if '</think>' in executed or '</thought>' in executed:
            count += 1

        exec_lines = executed.split('\n')
        if sum(1 for line in exec_lines if _REASONING_STARTERS.match(line)) >= 2:
            count += 1

    return count


def detect_single_step_stagnation(task: TaskTrace) -> int:
    """Archetype 2: Identical commands repeated across 3+ consecutive turns."""
    if len(task.turns) < 3:
        return 0

    commands = [re.sub(r'\s+', ' ', turn.get('executed', '')).strip() for turn in task.turns]

    # Check 3-consecutive repetition
    for i in range(len(commands) - 2):
        if commands[i] and commands[i] == commands[i + 1] == commands[i + 2]:
            return 1

    # Check near-identical across 4+ turns
    if len(commands) >= 4:
        non_empty = [c for c in commands if c]
        if non_empty:
            most_common_count = Counter(non_empty).most_common(1)[0][1]
            if len(set(non_empty)) <= 2 and most_common_count >= len(commands) - 1:
                return 1

    return 0


def detect_code_truncation(task: TaskTrace) -> int:
    """Archetype 3: Generated code cut off mid-statement (unmatched brackets)."""
    count = 0
    for turn in task.turns:
        agent = turn.get('agent_response', '')
        executed = turn.get('executed', '')

        for text in [executed, agent]:
            if not text:
                continue
            if any(text.count(o) - text.count(c) > 2 for o, c in [('(', ')'), ('[', ']'), ('{', '}')]):
                count += 1
                break

        if agent and len(agent) > 100:
            tail = agent[-50:].strip()
            if tail and not tail.endswith(_VALID_ENDINGS) and re.search(r'\w$', tail):
                count += 1

    return count


def detect_verification_omission(task: TaskTrace) -> int:
    """Archetype 4: [TASK_COMPLETE] emitted inside code blocks or prematurely."""
    count = 0
    for turn in task.turns:
        output = turn.get('output', '')
        agent = turn.get('agent_response', '')

        if '[TASK_COMPLETE]: not found' in output:
            count += 1
            continue

        if '[TASK_COMPLETE]' in agent:
            code_blocks = re.findall(r'```(?:bash|python)?\s*\n(.*?)```', agent, re.DOTALL)
            if any('[TASK_COMPLETE]' in block for block in code_blocks):
                count += 1

        if turn.get('turn_num', 0) == 1 and '[TASK_COMPLETE]' in agent:
            if not output or not output.strip():
                count += 1

    return count


# ══════════════════════════════════════════════════════════════
# Analysis Pipeline
# ══════════════════════════════════════════════════════════════

_DETECTORS = [
    ('reasoning_leakage', detect_reasoning_leakage),
    ('single_step_stagnation', detect_single_step_stagnation),
    ('code_truncation', detect_code_truncation),
    ('verification_omission', detect_verification_omission),
]


def analyze_file(file_trace: FileTrace) -> Dict:
    """Runs all archetype detectors on every task in a file trace."""
    results = {
        'model': file_trace.model, 'precision': file_trace.precision,
        'environment': file_trace.environment,
        'total_tasks': len(file_trace.tasks), 'successes': 0, 'failures': 0,
        'reasoning_leakage': 0, 'single_step_stagnation': 0,
        'code_truncation': 0, 'verification_omission': 0,
        'task_details': [],
    }

    for task in file_trace.tasks:
        if task.outcome == "success":
            results['successes'] += 1
        else:
            results['failures'] += 1

        task_archetypes = []
        for key, detector in _DETECTORS:
            hit_count = detector(task)
            results[key] += hit_count
            if hit_count:
                task_archetypes.append(f"{key}({hit_count})")

        results['task_details'].append({
            'task_id': task.task_id, 'outcome': task.outcome,
            'turns': len(task.turns), 'archetypes': task_archetypes,
            'self_corrections': sum(1 for t in task.turns if t.get('self_corrected')),
        })

    return results


def find_output_files(results_dir: str) -> List[str]:
    """Recursively finds all Output.md files under the results directory."""
    output_files = []
    for root, _, files in os.walk(results_dir):
        for f in files:
            if f == "Output.md":
                output_files.append(os.path.join(root, f))
    return sorted(output_files)


# ══════════════════════════════════════════════════════════════
# Reporting
# ══════════════════════════════════════════════════════════════

_ARCHETYPE_LABELS = {
    'leakage': 'Reasoning Leakage',
    'stagnation': 'Single-Step Stagnation',
    'truncation': 'Code Truncation',
    'omission': 'Verification Omission',
}

# Paper-reported manual counts for comparison
_PAPER_COUNTS = {
    'Reasoning Leakage': 58,
    'Single-Step Stagnation': 62,
    'Code Truncation': 27,
    'Verification Omission': 18,
}


def print_summary_report(all_results: List[Dict]):
    """Formats and prints the full summary report to console."""
    print("\n" + "=" * 80)
    print("  QUALITATIVE FAILURE ARCHETYPE ANALYSIS REPORT")
    print("=" * 80)

    model_agg = defaultdict(lambda: {
        'leakage': 0, 'stagnation': 0, 'truncation': 0,
        'omission': 0, 'tasks': 0, 'successes': 0,
    })
    totals = {'leakage': 0, 'stagnation': 0, 'truncation': 0, 'omission': 0}

    for r in all_results:
        m = r['model']
        model_agg[m]['leakage'] += r['reasoning_leakage']
        model_agg[m]['stagnation'] += r['single_step_stagnation']
        model_agg[m]['truncation'] += r['code_truncation']
        model_agg[m]['omission'] += r['verification_omission']
        model_agg[m]['tasks'] += r['total_tasks']
        model_agg[m]['successes'] += r['successes']
        for key in totals:
            totals[key] += r[f"{'reasoning_' if key == 'leakage' else 'single_step_' if key == 'stagnation' else 'code_' if key == 'truncation' else 'verification_'}{key}"]

    # Recalculate totals correctly
    totals = {'leakage': 0, 'stagnation': 0, 'truncation': 0, 'omission': 0}
    for r in all_results:
        totals['leakage'] += r['reasoning_leakage']
        totals['stagnation'] += r['single_step_stagnation']
        totals['truncation'] += r['code_truncation']
        totals['omission'] += r['verification_omission']

    # Summary table
    print(f"\n{'Model':<15} {'Tasks':>6} {'Succ%':>6} {'Leak':>6} {'Stag':>6} {'Trunc':>6} {'Omit':>6}")
    print("-" * 57)
    for model in sorted(model_agg):
        d = model_agg[model]
        pct = (d['successes'] / d['tasks'] * 100) if d['tasks'] > 0 else 0
        print(f"{model:<15} {d['tasks']:>6} {pct:>5.1f}% {d['leakage']:>6} "
              f"{d['stagnation']:>6} {d['truncation']:>6} {d['omission']:>6}")

    grand_tasks = sum(v['tasks'] for v in model_agg.values())
    grand_succ = sum(v['successes'] for v in model_agg.values())
    print("-" * 57)
    print(f"{'TOTAL':<15} {grand_tasks:>6} {grand_succ / grand_tasks * 100:>5.1f}% "
          f"{totals['leakage']:>6} {totals['stagnation']:>6} "
          f"{totals['truncation']:>6} {totals['omission']:>6}")

    # Per-config breakdown
    print(f"\n{'=' * 80}")
    print("  PER-CONFIGURATION BREAKDOWN")
    print(f"{'=' * 80}")
    print(f"\n{'Config':<35} {'Succ':>5} {'Fail':>5} {'Leak':>5} {'Stag':>5} {'Trunc':>5} {'Omit':>5}")
    print("-" * 72)
    for r in sorted(all_results, key=lambda x: (x['model'], x['precision'], x['environment'])):
        config = f"{r['model']} {r['precision']} {r['environment']}"
        print(f"{config:<35} {r['successes']:>5} {r['failures']:>5} "
              f"{r['reasoning_leakage']:>5} {r['single_step_stagnation']:>5} "
              f"{r['code_truncation']:>5} {r['verification_omission']:>5}")

    # Dominant archetype per model
    print(f"\n{'=' * 80}")
    print("  DOMINANT FAILURE ARCHETYPES BY MODEL")
    print(f"{'=' * 80}\n")
    for model in sorted(model_agg):
        d = model_agg[model]
        counts = {k: d[k] for k in ['leakage', 'stagnation', 'truncation', 'omission']}
        dominant = max(counts, key=counts.get)
        print(f"  {model}: {_ARCHETYPE_LABELS[dominant]} (n={counts[dominant]})")
        active = {_ARCHETYPE_LABELS[k]: v for k, v in sorted(counts.items(), key=lambda x: -x[1]) if v > 0}
        if active:
            print(f"    Distribution: {', '.join(f'{k}={v}' for k, v in active.items())}")
        print()

    # Comparison with paper
    print(f"{'=' * 80}")
    print("  COMPARISON WITH PAPER-REPORTED COUNTS")
    print(f"{'=' * 80}\n")

    detected = {
        'Reasoning Leakage': totals['leakage'],
        'Single-Step Stagnation': totals['stagnation'],
        'Code Truncation': totals['truncation'],
        'Verification Omission': totals['omission'],
    }
    print(f"  {'Archetype':<30} {'Paper':>8} {'Detected':>10} {'Delta':>8}")
    print(f"  {'-' * 58}")
    for arch, paper_n in _PAPER_COUNTS.items():
        det_n = detected[arch]
        print(f"  {arch:<30} {paper_n:>8} {det_n:>10} {det_n - paper_n:>+8}")
    print("\n  Note: Differences expected — heuristic vs. manual coding.")


def export_csv(all_results: List[Dict], output_path: str):
    """Exports per-task archetype results to CSV."""
    rows = []
    for r in all_results:
        for task in r['task_details']:
            rows.append({
                'model': r['model'], 'precision': r['precision'],
                'environment': r['environment'],
                'task_id': task['task_id'], 'outcome': task['outcome'],
                'turns': task['turns'],
                'self_corrections': task['self_corrections'],
                'archetypes': '; '.join(task['archetypes']) if task['archetypes'] else 'none',
                'reasoning_leakage': int(any('leakage' in a for a in task['archetypes'])),
                'stagnation': int(any('stagnation' in a for a in task['archetypes'])),
                'truncation': int(any('truncation' in a for a in task['archetypes'])),
                'verification_omission': int(any('omission' in a for a in task['archetypes'])),
            })

    if not rows:
        print("  No data to export.")
        return

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n  -> Exported: {output_path}")


# ══════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Qualitative failure archetype analysis of SLM agentic traces"
    )
    parser.add_argument('--results-dir', default='../Results',
                        help='Directory containing model result folders with Output.md files')
    parser.add_argument('--output', default='qualitative_analysis_results.csv',
                        help='Output CSV path')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Print per-task archetype details')
    args = parser.parse_args()

    output_files = find_output_files(args.results_dir)
    if not output_files:
        print(f"ERROR: No Output.md files found in '{args.results_dir}'")
        print(f"  Expected: {args.results_dir}/<ModelConfig>/Output.md")
        return

    print(f"Found {len(output_files)} Output.md trace files")

    all_results = []
    for filepath in output_files:
        file_trace = parse_output_md(filepath)
        result = analyze_file(file_trace)
        all_results.append(result)

        config = f"{result['model']} {result['precision']} {result['environment']}"
        total_arch = sum(result[k] for k, _ in _DETECTORS)
        print(f"  Analyzed: {config:<35} tasks={result['total_tasks']:>3}, archetypes={total_arch:>3}")

        if args.verbose:
            for td in result['task_details']:
                if td['archetypes']:
                    print(f"    {td['task_id']}: {td['outcome']} -> {', '.join(td['archetypes'])}")

    print_summary_report(all_results)
    export_csv(all_results, args.output)

    print(f"\n{'=' * 80}")
    print("  Analysis complete.")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
