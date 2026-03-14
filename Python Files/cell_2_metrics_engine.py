# %% [markdown]
# # Cell 2: Evaluation Metrics Engine
# Computes the novel metrics proposed in the paper:
# SDM (Stability Decay Metric), QHR (Quantization-Hallucination Ratio),
# PRE (Precision-Reasoning Efficiency), and Thinking Integrity.

# %% Cell 2: Metrics Engine
import torch


def calculate_sdm(turns_taken: int, max_turns: int, success: bool) -> float:
    """Stability Decay Metric: penalizes multi-turn inefficiency.
    1.0 = solved in 1 turn, 0.0 = failed."""
    if success:
        return 1.0 - ((turns_taken - 1) / max_turns)
    return 0.0


def calculate_pre(success_rate: float, bit_depth: int) -> float:
    """Precision-Reasoning Efficiency: success normalized by compression level."""
    if bit_depth <= 0:
        return 0.0
    return success_rate / bit_depth


def calculate_qhr(hallucination_count: int, total_turns: int) -> float:
    """Quantization-Hallucination Ratio: format/parser errors per turn."""
    if total_turns == 0:
        return 0.0
    return hallucination_count / total_turns


def get_vram_usage_gb() -> float:
    """Returns current VRAM allocated by PyTorch in GB."""
    if torch.cuda.is_available():
        return torch.cuda.memory_allocated() / (1024 ** 3)
    return 0.0


def measure_thinking_integrity(agent_response: str) -> bool:
    """Checks if the model maintained the forced <thought>...</thought> structure."""
    return "<thought>" in agent_response and "</thought>" in agent_response
