# Democratizing Agentic AI: Quantifying Reasoning Stability of Quantized SLMs in Recursive Agentic Loops on Resource-Constrained Hardware

> **Farhan Zarif** — BRAC University, Dhaka, Bangladesh

[![Paper](https://img.shields.io/badge/Paper-PDF-red.svg)](democratizing_agentic_ai.pdf)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Google%20Colab%20T4-orange.svg)](https://colab.research.google.com/)

---

## Abstract

We present the first systematic evaluation of multi-turn recursive stability in quantized Small Language Models (SLMs) operating as autonomous agents on resource-constrained hardware. We test four SLMs — **Gemma-3-4B**, **Llama-3.1-8B**, **Phi-4-Mini**, and **Qwen-3.5-4B** — under 4-bit NF4 and 8-bit INT8 quantization on a 15 GB VRAM Google Colab T4 GPU. Across **476 agentic tasks** spanning Bash administration, Python debugging, and multi-hop Web synthesis, we introduce two novel evaluation metrics: the **Stability Decay Metric (SDM)** and the **Quantization-Hallucination Ratio (QHR)**. Our results reveal that:

1. **Gemma-3-4B** achieves the highest agentic stability (SDM = 0.403, 53.3% success)
2. **Quantization effects are environment-dependent**: 4-bit outperforms 8-bit in Bash (*p* = 0.044), while 8-bit outperforms 4-bit in Python (*p* = 0.009)
3. **Format/parser errors** — not logical reasoning failures — constitute the dominant failure mode (42.7%)

Through qualitative analysis of 476 reasoning traces, we identify four distinct failure archetypes: *reasoning leakage*, *single-step stagnation*, *code truncation*, and *verification omission*.

---

## Key Findings

| Model | Params | Success Rate | Mean SDM | Dominant Failure |
|:---|:---:|:---:|:---:|:---|
| **Gemma-3-4B** | 4B | **53.3%** | **0.403** | Code Truncation |
| Phi-4-Mini | 3.8B | 30.0% | 0.218 | Verification Omission |
| Qwen-3.5-4B | 4B | 33.3% | 0.190 | Reasoning Leakage |
| Llama-3.1-8B | 8B | 0.86% | 0.005 | Single-Step Stagnation |

> **The Quantization Paradox**: Model size ≠ agentic capability. The largest model (Llama-3.1, 8B) fails catastrophically while smaller 4B models achieve meaningful performance.

---

## Repository Structure

```
.
├── democratizing_agentic_ai.tex    # LaTeX source (NeurIPS format)
├── democratizing_agentic_ai.pdf    # Compiled paper
├── democratizing_agentic_ai.bbl    # Bibliography
├── references.bib                  # BibTeX references
├── neurips_2024.sty                # NeurIPS style file
│
├── Python Files/                   # Evaluation codebase (Colab cells)
│   ├── cell_1_slm_inference.py         # Model loading (HF + bitsandbytes)
│   ├── cell_2_metrics_engine.py        # SDM, QHR, PRE, Thinking Integrity
│   ├── cell_3_agentic_environments.py  # Bash / Python / Web agents
│   ├── cell_4_task_benchmark.py        # 60 agentic tasks (20 per env)
│   └── cell_5_evaluation_harness.py    # 24-config evaluation orchestrator
│
├── Analysis Files/                 # Post-hoc analysis scripts
│   ├── quantitative_analysis.py        # Statistics, significance tests, figures
│   └── qualitative_analysis.py         # Failure archetype detection
│
├── Results/                        # Raw experimental outputs (24 folders)
│   ├── Gemma3_4B_4Bit_Bash/
│   ├── Gemma3_4B_4Bit_Python/
│   ├── ...                             # 24 model×precision×env configs
│   └── Qwen3.5_4B_8bit_Web/
│
├── Datasets/                       # Aggregated evaluation data
│   ├── combined_dataset.csv            # All 476 tasks × 16 features
│   └── qualitative_analysis_results.csv
│
└── charts/                         # Publication-quality figures (APA 7.0)
    ├── fig1_sdm_by_model_precision.png
    ├── fig2_sdm_heatmap.png
    ├── fig3_sdm_boxplot_by_env.png
    ├── fig4_success_rate_comparison.png
    ├── fig5_qhr_comparison.png
    ├── fig6_vram_usage.png
    ├── fig7_latency_comparison.png
    └── fig8_error_taxonomy.png
```

---

## Quick Start

### Requirements

```
torch>=2.0
transformers>=4.40
bitsandbytes>=0.43
accelerate
```

For analysis scripts:
```
pandas
numpy
scipy
matplotlib
```

### Running Inference (Google Colab)

1. Open a **Google Colab** notebook with a **T4 GPU** runtime
2. Copy the contents of each `cell_*.py` file sequentially into notebook cells
3. In `cell_5_evaluation_harness.py`, uncomment **one** `run_evaluation()` call per session:

```python
# Example: Run Gemma-3-4B in 4-bit across all environments
run_evaluation(["google/gemma-3-4b-it"], ["4bit"], ["Bash", "Python", "Web"], BASE_DIR)
```

4. Download the generated CSV/JSON results, restart runtime, and run the next configuration

> ⚠️ The T4 GPU (15 GB VRAM) can only hold **one model** at a time. Restart the runtime between configurations.

### Running Analysis

```bash
cd "Analysis Files"
python quantitative_analysis.py    # Generates 8 figures + report
python qualitative_analysis.py --results-dir ../Results --output report.csv
```

---

## Experimental Setup

| Component | Details |
|:---|:---|
| **Hardware** | NVIDIA T4 GPU (15 GB VRAM), Google Colab free tier |
| **Models** | Gemma-3-4B-IT, Llama-3.1-8B-Instruct, Phi-4-Mini-Instruct, Qwen3.5-4B |
| **Quantization** | 4-bit NF4 (double quant, FP16 compute) · 8-bit INT8 via `bitsandbytes` |
| **Agent Framework** | ReAct-style loop with TOON compression + Actor-Critic self-correction |
| **Turn Limit** | D_max = 5 turns per task |
| **Tasks** | 60 total (20 Bash + 20 Python + 20 Web) |
| **Validation** | LLM-as-a-Judge with ~12% estimated false-negative rate |
| **Experiment Period** | March 3–12, 2026 |

---

## Novel Metrics

### Stability Decay Metric (SDM)

$$\text{SDM} = \mathbb{I}_{success} \times \left(1 - \frac{T - 1}{D_{max}}\right)$$

Penalizes multi-turn inefficiency: **1.0** = solved in 1 turn, **0.0** = failed. $\mathbb{I}_{success} = 1$ if task solved (validated by LLM-as-a-Judge), $T$ = turns used, $D_{max} = 5$.

### Quantization-Hallucination Ratio (QHR)

$$\text{QHR} = \frac{\sum_{t=1}^{T} \mathbb{I}_{parse\ error}(t)}{T}$$

Isolates structural formatting failures from logical reasoning errors.

---

## Failure Archetypes

| Archetype | Primary Model | Count | Description |
|:---|:---|:---:|:---|
| **Reasoning Leakage** | Qwen-3.5 | 58 | Reasoning text leaks into executable code blocks |
| **Single-Step Stagnation** | Llama-3.1 | 62 | Same command repeated across all turns |
| **Code Truncation** | Gemma-3 | 27 | Generated code cut off mid-statement |
| **Verification Omission** | Phi-4-Mini | 18 | Missing `[TASK_COMPLETE]` despite correct execution |

---

## Citation

```bibtex
@article{zarif2026democratizing,
  title={Democratizing Agentic AI: Quantifying Reasoning Stability of 
         Quantized SLMs in Recursive Agentic Loops on 
         Resource-Constrained Hardware},
  author={Zarif, Farhan},
  journal={arXiv preprint},
  year={2026}
}
```

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Acknowledgements

We thank the open-source teams behind Qwen, Llama, Gemma, and Phi, the `bitsandbytes` and HuggingFace communities, and Google Colab for free GPU access.
