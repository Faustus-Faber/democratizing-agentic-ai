"""
Quantitative Analysis: Statistical Evaluation & Figure Generation
=================================================================
Reads all 24 result folders, computes aggregate statistics, runs
significance tests (Mann-Whitney U, Welch's t), generates
publication-quality APA 7.0 figures, and builds error taxonomy.

Output:
  - charts/*.png              (8 publication-quality figures)
  - analysis_report.txt       (full statistical summary)
  - aggregated_stats.csv      (per-configuration metrics)

Usage:
    python quantitative_analysis.py
"""

import json
import warnings
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

warnings.filterwarnings('ignore', category=FutureWarning)

# ──── APA 7.0 Figure Configuration ────
matplotlib.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 9,
    'axes.titlesize': 11,
    'axes.labelsize': 10,
    'xtick.labelsize': 8,
    'ytick.labelsize': 8,
    'legend.fontsize': 8,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'axes.spines.top': False,
    'axes.spines.right': False,
})

# Colorblind-safe Wong palette
CB_PALETTE = ['#0077BB', '#33BBEE', '#009988', '#EE7733',
              '#CC3311', '#EE3377', '#BBBBBB', '#000000']
MODEL_COLORS = {
    'Gemma-3': CB_PALETTE[0],
    'Llama-3.1': CB_PALETTE[3],
    'Phi-4-Mini': CB_PALETTE[2],
    'Qwen-3.5': CB_PALETTE[4],
}

# ──── Paths (relative to script location) ────
BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = BASE_DIR / "Results"
CHARTS_DIR = BASE_DIR / "charts"
CHARTS_DIR.mkdir(exist_ok=True)


# ══════════════════════════════════════════════════════════════
# Utilities
# ══════════════════════════════════════════════════════════════

def canonical_model(raw: str) -> str:
    """Normalizes model identifiers to display names."""
    raw = raw.lower()
    if 'gemma' in raw:
        return 'Gemma-3'
    if 'llama' in raw:
        return 'Llama-3.1'
    if 'phi' in raw:
        return 'Phi-4-Mini'
    if 'qwen' in raw:
        return 'Qwen-3.5'
    return raw


def canonical_precision(raw: str) -> str:
    return '4-bit' if '4bit' in raw.lower() else '8-bit'


def canonical_env(raw: str) -> str:
    raw = raw.lower()
    if 'bash' in raw:
        return 'Bash'
    if 'python' in raw or 'py' in raw:
        return 'Python'
    if 'web' in raw:
        return 'Web'
    return raw


# ══════════════════════════════════════════════════════════════
# 1. Data Loading
# ══════════════════════════════════════════════════════════════

def load_all_data() -> pd.DataFrame:
    """Loads all result JSONs from the Results directory into a unified DataFrame."""
    print("=" * 60)
    print("  Phase 1: Loading Data")
    print("=" * 60)

    all_rows = []
    for folder in sorted(RESULTS_DIR.iterdir()):
        if not folder.is_dir():
            continue

        jsons = list(folder.glob("results_*.json"))
        if not jsons:
            print(f"  [WARN] No JSON in {folder.name}")
            continue

        with open(jsons[0], 'r', encoding='utf-8-sig') as f:
            tasks = json.load(f)

        output_md = folder / "Output.md"
        md_lines = 0
        if output_md.exists():
            with open(output_md, 'r', encoding='utf-8-sig', errors='replace') as f:
                md_lines = sum(1 for _ in f)

        csv_count = 0
        csvs = list(folder.glob("eval_*.csv"))
        if csvs:
            csv_count = len(pd.read_csv(csvs[0]))

        for task in tasks:
            row = dict(task)
            row['model_canonical'] = canonical_model(task['model'])
            row['precision_canonical'] = canonical_precision(task['precision'])
            row['env_canonical'] = canonical_env(task['environment'])
            row['folder'] = folder.name
            row['config'] = f"{row['model_canonical']} {row['precision_canonical']} {row['env_canonical']}"
            all_rows.append(row)

        print(f"  -> {folder.name}: {len(tasks)} tasks | CSV={csv_count} | Output.md={md_lines} lines")

    df = pd.DataFrame(all_rows)
    print(f"\n  Total: {len(df)} tasks | "
          f"Models: {df['model_canonical'].unique().tolist()} | "
          f"Precisions: {df['precision_canonical'].unique().tolist()} | "
          f"Environments: {df['env_canonical'].unique().tolist()}")
    return df


# ══════════════════════════════════════════════════════════════
# 2. Aggregate Statistics
# ══════════════════════════════════════════════════════════════

def compute_aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """Computes per-configuration aggregate statistics with 95% CIs."""
    agg = df.groupby(['model_canonical', 'precision_canonical', 'env_canonical']).agg(
        n=('task_completed', 'count'),
        success_count=('task_completed', 'sum'),
        success_rate=('task_completed', 'mean'),
        sdm_mean=('sdm', 'mean'),
        sdm_std=('sdm', 'std'),
        qhr_mean=('qhr', 'mean'),
        qhr_std=('qhr', 'std'),
        turns_mean=('turns_taken', 'mean'),
        turns_std=('turns_taken', 'std'),
        latency_mean=('latency_sec', 'mean'),
        latency_std=('latency_sec', 'std'),
        vram_mean=('vram_gb', 'mean'),
        reasoning_len_mean=('reasoning_length', 'mean'),
        self_corrections_mean=('self_corrections', 'mean'),
        thinking_integrity_rate=('thinking_integrity', 'mean'),
    ).reset_index()

    agg['sdm_ci95'] = agg.apply(
        lambda r: stats.t.ppf(0.975, r['n'] - 1) * r['sdm_std'] / np.sqrt(r['n'])
        if r['n'] > 1 else 0, axis=1
    )
    agg['success_ci95'] = agg.apply(
        lambda r: 1.96 * np.sqrt(r['success_rate'] * (1 - r['success_rate']) / r['n'])
        if r['n'] > 0 else 0, axis=1
    )
    return agg


# ══════════════════════════════════════════════════════════════
# 3. Significance Tests
# ══════════════════════════════════════════════════════════════

def run_significance_tests(df: pd.DataFrame) -> pd.DataFrame:
    """Mann-Whitney U and Welch's t-test for 4-bit vs 8-bit SDM per model×env."""
    print("\n" + "=" * 60)
    print("  Statistical Tests: 4-bit vs 8-bit SDM")
    print("=" * 60)

    results = []
    for model in df['model_canonical'].unique():
        for env in df['env_canonical'].unique():
            d4 = df[(df['model_canonical'] == model) & (df['precision_canonical'] == '4-bit') & (df['env_canonical'] == env)]['sdm']
            d8 = df[(df['model_canonical'] == model) & (df['precision_canonical'] == '8-bit') & (df['env_canonical'] == env)]['sdm']

            if len(d4) < 3 or len(d8) < 3:
                continue

            u_stat, u_pval = stats.mannwhitneyu(d4, d8, alternative='two-sided')
            r_effect = 1 - (2 * u_stat) / (len(d4) * len(d8))
            t_stat, t_pval = stats.ttest_ind(d4, d8, equal_var=False)

            sig = "***" if u_pval < 0.001 else "**" if u_pval < 0.01 else "*" if u_pval < 0.05 else "ns"

            results.append({
                'model': model, 'env': env,
                'sdm_4bit': d4.mean(), 'sdm_8bit': d8.mean(),
                'diff': d4.mean() - d8.mean(),
                'u_stat': u_stat, 'u_pval': u_pval,
                't_stat': t_stat, 't_pval': t_pval,
                'effect_r': r_effect, 'sig': sig,
            })

            print(f"  {model:12s} | {env:6s} | 4bit={d4.mean():.3f} vs 8bit={d8.mean():.3f} | "
                  f"Δ={d4.mean() - d8.mean():+.3f} | U={u_stat:.0f} p={u_pval:.4f} {sig} | r={r_effect:+.3f}")

    return pd.DataFrame(results)


# ══════════════════════════════════════════════════════════════
# 4. Rankings
# ══════════════════════════════════════════════════════════════

def print_rankings(df: pd.DataFrame):
    """Prints model, precision, and environment ranking tables."""
    print("\n" + "=" * 60)
    print("  Overall Rankings")
    print("=" * 60)

    for group_col, label in [('model_canonical', 'By Model'),
                              ('precision_canonical', 'By Precision'),
                              ('env_canonical', 'By Environment')]:
        ranking = df.groupby(group_col).agg(
            success=('task_completed', 'mean'),
            sdm=('sdm', 'mean'),
            qhr=('qhr', 'mean'),
            turns=('turns_taken', 'mean'),
        ).sort_values('sdm', ascending=False)
        print(f"\n{label}:")
        print(ranking.round(4).to_string())


# ══════════════════════════════════════════════════════════════
# 5. Figure Generation
# ══════════════════════════════════════════════════════════════

def generate_figures(df: pd.DataFrame, agg: pd.DataFrame):
    """Generates all 8 publication-quality figures."""
    print("\n" + "=" * 60)
    print("  Generating Figures")
    print("=" * 60)

    models = sorted(df['model_canonical'].unique())
    x = np.arange(len(models))
    width = 0.35

    # Fig 1: SDM by Model × Precision
    fig, ax = plt.subplots(figsize=(6.9, 4))
    for i, (prec, color) in enumerate([('4-bit', CB_PALETTE[0]), ('8-bit', CB_PALETTE[3])]):
        vals = [agg[(agg['model_canonical'] == m) & (agg['precision_canonical'] == prec)]['sdm_mean'].mean()
                if len(agg[(agg['model_canonical'] == m) & (agg['precision_canonical'] == prec)]) > 0 else 0
                for m in models]
        cis = [agg[(agg['model_canonical'] == m) & (agg['precision_canonical'] == prec)]['sdm_ci95'].mean()
               if len(agg[(agg['model_canonical'] == m) & (agg['precision_canonical'] == prec)]) > 0 else 0
               for m in models]
        ax.bar(x + i * width - width / 2, vals, width, yerr=cis, label=prec,
               color=color, capsize=3, edgecolor='white', linewidth=0.5)
    ax.set_xlabel('Model')
    ax.set_ylabel('Mean SDM Score')
    ax.set_xticks(x)
    ax.set_xticklabels(models, fontsize=9)
    ax.legend(title='Precision', frameon=False)
    ax.set_ylim(0, max(0.6, ax.get_ylim()[1] * 1.1))
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.2f'))
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / 'fig1_sdm_by_model_precision.png')
    print("  -> fig1_sdm_by_model_precision.png")
    plt.close()

    # Fig 2: SDM Heatmap
    fig, ax = plt.subplots(figsize=(6.9, 5))
    pivot = agg.pivot_table(
        index=['model_canonical', 'precision_canonical'], columns='env_canonical', values='sdm_mean'
    ).sort_index()
    im = ax.imshow(pivot.values, cmap='YlOrRd_r', aspect='auto', vmin=0, vmax=0.5)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, fontsize=9)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([f"{m} ({p})" for m, p in pivot.index], fontsize=8)
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:.3f}", ha='center', va='center', fontsize=7,
                        color='white' if val < 0.15 else 'black')
    fig.colorbar(im, ax=ax, shrink=0.8).set_label('Mean SDM', fontsize=9)
    ax.set_xlabel('Environment')
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / 'fig2_sdm_heatmap.png')
    print("  -> fig2_sdm_heatmap.png")
    plt.close()

    # Fig 3: SDM Boxplot by Environment
    fig, axes = plt.subplots(1, 3, figsize=(6.9, 3.5), sharey=True)
    for idx, env in enumerate(['Bash', 'Python', 'Web']):
        ax = axes[idx]
        env_data = df[df['env_canonical'] == env]
        data_lists, labels, colors_list, positions = [], [], [], []
        pos = 0
        for model in models:
            for prec in ['4-bit', '8-bit']:
                subset = env_data[(env_data['model_canonical'] == model) & (env_data['precision_canonical'] == prec)]
                if len(subset) > 0:
                    data_lists.append(subset['sdm'].values)
                    labels.append(f"{model.split('-')[0]}\n{prec}")
                    colors_list.append(CB_PALETTE[0] if prec == '4-bit' else CB_PALETTE[3])
                    positions.append(pos)
                    pos += 1
            pos += 0.5
        bp = ax.boxplot(data_lists, positions=positions, widths=0.6, patch_artist=True, showfliers=True)
        for patch, color in zip(bp['boxes'], colors_list):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        ax.set_title(f'Environment: {env}', fontsize=10, fontweight='bold')
        ax.set_xticks(positions)
        ax.set_xticklabels(labels, fontsize=6, rotation=45, ha='right')
        if idx == 0:
            ax.set_ylabel('SDM Score')
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / 'fig3_sdm_boxplot_by_env.png')
    print("  -> fig3_sdm_boxplot_by_env.png")
    plt.close()

    # Fig 4: Success Rate
    fig, ax = plt.subplots(figsize=(6.9, 4))
    envs = ['Bash', 'Python', 'Web']
    x_env = np.arange(len(envs))
    bar_width = 0.8 / (len(models) * 2)
    for m_idx, model in enumerate(models):
        for p_idx, (prec, hatch) in enumerate([('4-bit', ''), ('8-bit', '///')]):
            vals = []
            for env in envs:
                subset = agg[(agg['model_canonical'] == model) & (agg['precision_canonical'] == prec) & (agg['env_canonical'] == env)]
                vals.append(subset['success_rate'].values[0] * 100 if len(subset) > 0 else 0)
            offset = (m_idx * 2 + p_idx - len(models) + 0.5) * bar_width
            ax.bar(x_env + offset, vals, bar_width * 0.9, label=f"{model} {prec}",
                   color=MODEL_COLORS[model], hatch=hatch, alpha=0.8 if prec == '4-bit' else 0.5,
                   edgecolor='white', linewidth=0.3)
    ax.set_xlabel('Environment')
    ax.set_ylabel('Success Rate (%)')
    ax.set_xticks(x_env)
    ax.set_xticklabels(envs)
    ax.legend(fontsize=6, ncol=4, loc='upper right', frameon=False)
    ax.set_ylim(0, 105)
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / 'fig4_success_rate_comparison.png')
    print("  -> fig4_success_rate_comparison.png")
    plt.close()

    # Fig 5: QHR
    fig, ax = plt.subplots(figsize=(6.9, 3.5))
    for i, (prec, color) in enumerate([('4-bit', CB_PALETTE[0]), ('8-bit', CB_PALETTE[3])]):
        vals = [df[(df['model_canonical'] == m) & (df['precision_canonical'] == prec)]['qhr'].mean() for m in models]
        ax.bar(x + i * width - width / 2, vals, width, label=prec, color=color)
    ax.set_xlabel('Model')
    ax.set_ylabel('Mean QHR (Parser Error Density)')
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / 'fig5_qhr_comparison.png')
    print("  -> fig5_qhr_comparison.png")
    plt.close()

    # Fig 6: VRAM
    fig, ax = plt.subplots(figsize=(6.9, 3.5))
    vram_agg = df.groupby(['model_canonical', 'precision_canonical'])['vram_gb'].mean().reset_index()
    for i, (prec, color) in enumerate([('4-bit', CB_PALETTE[0]), ('8-bit', CB_PALETTE[3])]):
        vals = [vram_agg[(vram_agg['model_canonical'] == m) & (vram_agg['precision_canonical'] == prec)]['vram_gb'].values[0]
                if len(vram_agg[(vram_agg['model_canonical'] == m) & (vram_agg['precision_canonical'] == prec)]) > 0 else 0
                for m in models]
        ax.bar(x + i * width - width / 2, vals, width, label=prec, color=color)
    ax.axhline(y=15, color='red', linestyle='--', linewidth=0.8, alpha=0.7, label='T4 VRAM Limit (15 GB)')
    ax.set_xlabel('Model')
    ax.set_ylabel('VRAM Usage (GB)')
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.legend(frameon=False, fontsize=8)
    ax.set_ylim(0, 18)
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / 'fig6_vram_usage.png')
    print("  -> fig6_vram_usage.png")
    plt.close()

    # Fig 7: Latency
    fig, ax = plt.subplots(figsize=(6.9, 3.5))
    for i, (prec, color) in enumerate([('4-bit', CB_PALETTE[0]), ('8-bit', CB_PALETTE[3])]):
        vals = [df[(df['model_canonical'] == m) & (df['precision_canonical'] == prec)]['latency_sec'].mean() for m in models]
        errs = [df[(df['model_canonical'] == m) & (df['precision_canonical'] == prec)]['latency_sec'].std() for m in models]
        ax.bar(x + i * width - width / 2, vals, width, yerr=errs, label=prec, color=color, capsize=3)
    ax.set_xlabel('Model')
    ax.set_ylabel('Mean Latency (seconds)')
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / 'fig7_latency_comparison.png')
    print("  -> fig7_latency_comparison.png")
    plt.close()


# ══════════════════════════════════════════════════════════════
# 6. Error Taxonomy
# ══════════════════════════════════════════════════════════════

def build_error_taxonomy(df: pd.DataFrame):
    """Classifies failures and generates stacked bar chart."""
    print("\n" + "=" * 60)
    print("  Error Taxonomy")
    print("=" * 60)

    failed = df[~df['task_completed']].copy()
    total_failed = len(failed)

    failed['failure_type'] = 'Unknown'
    failed.loc[failed['qhr'] > 0, 'failure_type'] = 'Format/Parser Error'
    failed.loc[(failed['qhr'] == 0) & (failed['turns_taken'] >= 5), 'failure_type'] = 'Max Turns Exhausted'
    failed.loc[(failed['qhr'] == 0) & (failed['turns_taken'] == 1), 'failure_type'] = 'Immediate Failure'
    failed.loc[(failed['qhr'] == 0) & (failed['turns_taken'] > 1) & (failed['turns_taken'] < 5) & (failed['self_corrections'] > 0), 'failure_type'] = 'Self-Correction Loop'
    failed.loc[(failed['failure_type'] == 'Unknown') & (failed['turns_taken'] > 1) & (failed['turns_taken'] < 5), 'failure_type'] = 'Judge Rejected'

    error_counts = failed['failure_type'].value_counts()
    print(f"\n  Failed: {total_failed}/{len(df)} ({total_failed / len(df) * 100:.1f}%)")
    for err_type, count in error_counts.items():
        print(f"    {err_type:25s}: {count:>4} ({count / total_failed * 100:>5.1f}%)")

    error_by_model = pd.crosstab(failed['model_canonical'], failed['failure_type'], margins=True)
    error_by_prec = pd.crosstab(failed['precision_canonical'], failed['failure_type'], margins=True)
    print(f"\n  By Model:\n{error_by_model.to_string()}")
    print(f"\n  By Precision:\n{error_by_prec.to_string()}")

    # Fig 8: Error Taxonomy Stacked Bar
    fig, ax = plt.subplots(figsize=(6.9, 4))
    error_pivot = pd.crosstab(failed['model_canonical'], failed['failure_type'])
    ordered_cols = ['Format/Parser Error', 'Max Turns Exhausted', 'Immediate Failure',
                    'Self-Correction Loop', 'Judge Rejected', 'Unknown']
    error_pivot = error_pivot.reindex(columns=ordered_cols, fill_value=0)
    error_pivot = error_pivot.loc[:, (error_pivot != 0).any()]
    bar_colors = [CB_PALETTE[4], CB_PALETTE[3], CB_PALETTE[6], CB_PALETTE[1], CB_PALETTE[5], CB_PALETTE[7]]
    error_pivot.plot(kind='bar', stacked=True, ax=ax, color=bar_colors[:len(error_pivot.columns)])
    ax.set_xlabel('Model')
    ax.set_ylabel('Number of Failed Tasks')
    ax.set_xticklabels(ax.get_xticklabels(), rotation=0)
    ax.legend(title='Failure Type', fontsize=7, frameon=False, bbox_to_anchor=(1.0, 1.0))
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / 'fig8_error_taxonomy.png')
    print("  -> fig8_error_taxonomy.png")
    plt.close()

    return error_by_model, error_by_prec, error_counts, total_failed


# ══════════════════════════════════════════════════════════════
# 7. Task Difficulty
# ══════════════════════════════════════════════════════════════

def analyze_task_difficulty(df: pd.DataFrame) -> pd.DataFrame:
    """Identifies hardest and easiest tasks across all configurations."""
    print("\n" + "=" * 60)
    print("  Task Difficulty Analysis")
    print("=" * 60)

    task_diff = df.groupby(['env_canonical', 'task_id']).agg(
        success_rate=('task_completed', 'mean'),
        avg_sdm=('sdm', 'mean'),
        avg_turns=('turns_taken', 'mean'),
        n_attempts=('task_completed', 'count'),
    ).reset_index()

    print("\n  Hardest Tasks:")
    for _, r in task_diff.sort_values('success_rate').head(10).iterrows():
        print(f"    {r['env_canonical']:6s} {r['task_id']:8s} -> {r['success_rate'] * 100:5.1f}% | "
              f"SDM={r['avg_sdm']:.3f} | Turns={r['avg_turns']:.1f}")

    print("\n  Easiest Tasks:")
    for _, r in task_diff.sort_values('success_rate', ascending=False).head(5).iterrows():
        print(f"    {r['env_canonical']:6s} {r['task_id']:8s} -> {r['success_rate'] * 100:5.1f}% | "
              f"SDM={r['avg_sdm']:.3f} | Turns={r['avg_turns']:.1f}")

    return task_diff


# ══════════════════════════════════════════════════════════════
# 8. Report Export
# ══════════════════════════════════════════════════════════════

def save_report(df, agg, sig_df, model_rank, error_data, task_diff):
    """Writes the full analysis report and aggregated CSV."""
    error_by_model, error_by_prec, error_counts, total_failed = error_data
    report_path = BASE_DIR / "analysis_report.txt"

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("  QUANTITATIVE ANALYSIS REPORT\n")
        f.write(f"  Data: {len(df)} tasks across {df['config'].nunique()} configurations\n")
        f.write("=" * 70 + "\n\n")

        f.write("1. CONFIGURATION TABLE\n" + "-" * 70 + "\n")
        f.write(agg.to_string(index=False) + "\n\n")

        f.write("2. SIGNIFICANCE TESTS (4-bit vs 8-bit SDM)\n" + "-" * 70 + "\n")
        if len(sig_df) > 0:
            f.write(sig_df.to_string(index=False) + "\n\n")

        f.write("3. MODEL RANKINGS\n" + "-" * 70 + "\n")
        f.write(model_rank.round(4).to_string() + "\n\n")

        f.write("4. ERROR TAXONOMY\n" + "-" * 70 + "\n")
        f.write(f"Failed: {total_failed}/{len(df)} ({total_failed / len(df) * 100:.1f}%)\n")
        f.write(error_counts.to_string() + "\n\n")
        f.write("By Model:\n" + error_by_model.to_string() + "\n\n")
        f.write("By Precision:\n" + error_by_prec.to_string() + "\n\n")

        f.write("5. TASK DIFFICULTY\n" + "-" * 70 + "\n")
        f.write(task_diff.sort_values('success_rate').to_string(index=False) + "\n")

    agg.to_csv(BASE_DIR / "aggregated_stats.csv", index=False)
    print(f"\n  -> Report: {report_path}")
    print(f"  -> CSV: {BASE_DIR / 'aggregated_stats.csv'}")


# ══════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════

def main():
    df = load_all_data()
    agg = compute_aggregate(df)

    # Print config table
    print("\n" + "=" * 60)
    print("  Aggregate Statistics")
    print("=" * 60)
    print(f"\n{'Model':<12} {'Prec':<6} {'Env':<8} {'N':>3} {'Succ%':>6} {'SDM±CI':>12} {'QHR':>6} {'Turns':>6}")
    print("-" * 70)
    for _, r in agg.iterrows():
        print(f"{r['model_canonical']:<12} {r['precision_canonical']:<6} {r['env_canonical']:<8} "
              f"{r['n']:>3} {r['success_rate'] * 100:>5.1f}% "
              f"{r['sdm_mean']:>5.3f}±{r['sdm_ci95']:>4.3f} "
              f"{r['qhr_mean']:>5.3f} {r['turns_mean']:>5.2f}")

    sig_df = run_significance_tests(df)
    print_rankings(df)
    generate_figures(df, agg)
    error_data = build_error_taxonomy(df)
    task_diff = analyze_task_difficulty(df)

    model_rank = df.groupby('model_canonical').agg(
        success=('task_completed', 'mean'), sdm=('sdm', 'mean'),
        qhr=('qhr', 'mean'), turns=('turns_taken', 'mean'),
        latency=('latency_sec', 'mean'), vram=('vram_gb', 'mean'),
    ).sort_values('sdm', ascending=False)

    save_report(df, agg, sig_df, model_rank, error_data, task_diff)

    print("\n" + "=" * 60)
    print(f"  COMPLETE: {len(df)} tasks | 8 figures | report + CSV saved")
    print("=" * 60)


if __name__ == "__main__":
    main()
