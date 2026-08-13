# finetune_colab.py
# Paste this into a Google Colab notebook

"""
!pip install -q transformers peft trl datasets bitsandbytes accelerate
"""

import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer

# 1. Configuration
model_name = "microsoft/Phi-3.5-mini-instruct"
dataset_path = "dataset.jsonl" # Upload this to colab

# 2. Load Quantized Model
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
)

model = AutoModelForCausalLM.from_pretrained(
    model_name,
    quantization_config=bnb_config,
    device_map="auto",
    trust_remote_code=True
)
tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
tokenizer.pad_token = tokenizer.eos_token

# 3. LoRA Configuration
peft_config = LoraConfig(
    r=64,
    lora_alpha=128,
    target_modules=['q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj'],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM"
)
model = prepare_model_for_kbit_training(model)
model = get_peft_model(model, peft_config)

# 4. Load and Format Dataset
def format_instruction(example):
    prompt = f"<|user|>\n{example['instruction']}\n{example['input']}<|end|>\n<|assistant|>\n{example['output']}<|end|>"
    return {"text": prompt}

dataset = load_dataset('json', data_files=dataset_path, split='train')
dataset = dataset.map(format_instruction)

# 5. Training Arguments
training_args = TrainingArguments(
    output_dir="./results",
    num_train_epochs=3,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    warmup_ratio=0.03,
    logging_steps=10,
    save_strategy="epoch",
    fp16=True,
    optim="paged_adamw_8bit"
)

# 6. Train
trainer = SFTTrainer(
    model=model,
    train_dataset=dataset,
    peft_config=peft_config,
    dataset_text_field="text",
    max_seq_length=2048,
    tokenizer=tokenizer,
    args=training_args
)

print("Starting training...")
trainer.train()

# 7. Save and Merge
print("Saving adapter...")
trainer.model.save_pretrained("novelaw-adapter")

# To merge, you would typically reload the base model in fp16 and merge:
# base_model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float16, device_map="cpu")
# model = PeftModel.from_pretrained(base_model, "novelaw-adapter")
# merged_model = model.merge_and_unload()
# merged_model.save_pretrained("novelaw-merged")
# tokenizer.save_pretrained("novelaw-merged")

# 8. Convert to GGUF (instructions)
# Clone llama.cpp: git clone https://github.com/ggerganov/llama.cpp
# Run: python llama.cpp/convert.py novelaw-merged --outfile novelaw-f16.gguf --outtype f16
# Quantize: ./llama.cpp/quantize novelaw-f16.gguf novelaw-q4_k_m.gguf q4_k_m
