# %% [markdown]
# # Cell 1: SLM Inference Pipeline
# Loads a quantized SLM via HuggingFace Transformers + bitsandbytes.
# Supports 4-bit (NF4) and 8-bit (INT8) quantization for T4 GPU deployment.

# %% Cell 1: Dependencies & Authentication
import torch
import os
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

try:
    from google.colab import userdata
    HF_TOKEN = userdata.get('HF_TOKEN')
    import huggingface_hub
    huggingface_hub.login(HF_TOKEN)
    print("Logged into HuggingFace via Colab Secrets.")
except ImportError:
    print("Not running in Colab. Set HUGGING_FACE_HUB_TOKEN for gated models.")
except Exception as e:
    print(f"Warning: Could not fetch HF_TOKEN: {e}")


# %% Cell 1: SLM Inference Pipeline
class SLMInferencePipeline:
    """Unified inference pipeline for all evaluated SLMs under quantization."""

    def __init__(self, model_id: str, load_in_4bit: bool = True):
        self.model_id = model_id

        if load_in_4bit:
            self.quant_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16
            )
            print(f"Loading {model_id} in 4-bit NF4...")
        else:
            self.quant_config = BitsAndBytesConfig(load_in_8bit=True)
            print(f"Loading {model_id} in 8-bit INT8...")

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_id, trust_remote_code=True
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            quantization_config=self.quant_config,
            device_map="auto",
            trust_remote_code=True
        )
        vram = torch.cuda.memory_allocated() / (1024**3)
        print(f"Model loaded. VRAM: {vram:.2f} GB")

    def format_prompt(self, messages_or_system, user_prompt=None) -> str:
        """Formats prompt using the model's native chat template."""
        if isinstance(messages_or_system, list):
            messages = messages_or_system
        else:
            messages = [
                {"role": "system", "content": messages_or_system},
                {"role": "user", "content": user_prompt}
            ]
        return self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

    def generate(self, messages_or_system, user_prompt=None, max_new_tokens=400) -> str:
        """Generate a response from the quantized model."""
        prompt_text = self.format_prompt(messages_or_system, user_prompt)
        inputs = self.tokenizer(prompt_text, return_tensors="pt").to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                pad_token_id=self.tokenizer.eos_token_id
            )

        input_length = inputs["input_ids"].shape[1]
        return self.tokenizer.decode(outputs[0][input_length:], skip_special_tokens=True)
