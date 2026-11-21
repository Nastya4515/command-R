"""QLoRA-дообучение модели извлечения (RTX 2060 Super 8 ГБ).

База: Qwen2.5-3B-Instruct в 4-бит (bitsandbytes nf4) + LoRA.
Turing (RTX 20xx) не поддерживает bf16 — только fp16.
Обучение только на ответе (completion-only): промпт не участвует в лоссе.

Запуск: python -m pipeline.train_sft [--epochs 3] [--out models/extractor-v1]
"""
from __future__ import annotations

import argparse
import logging

import torch
from datasets import load_dataset
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import SFTConfig, SFTTrainer

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

BASE_MODEL = "Qwen/Qwen2.5-3B-Instruct"


def main() -> None:
    parser = argparse.ArgumentParser(description="QLoRA-дообучение экстрактора")
    parser.add_argument("--data", default="data/sft", help="каталог с train.jsonl/val.jsonl")
    parser.add_argument("--out", default="models/extractor-v1")
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--lr", type=float, default=1e-4)
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise SystemExit("CUDA недоступна — проверь драйвер (nvidia-smi) и перезагрузи ПК")

    quant = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,  # Turing: bf16 нет
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL, quantization_config=quant, device_map="auto",
        torch_dtype=torch.float16)
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

    dataset = load_dataset("json", data_files={
        "train": f"{args.data}/train.jsonl", "val": f"{args.data}/val.jsonl"})

    lora = LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
    )

    sft_config = SFTConfig(
        output_dir=args.out,
        num_train_epochs=args.epochs,
        learning_rate=args.lr,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=8,   # эффективный батч 16
        per_device_eval_batch_size=2,
        eval_strategy="epoch",
        save_strategy="epoch",
        logging_steps=20,
        fp16=True,
        gradient_checkpointing=True,
        max_length=1024,
        packing=False,
        assistant_only_loss=True,        # лосс только по ответу ассистента
        dataset_kwargs={"skip_prepare_dataset": False},
        report_to=[],
        seed=42,
    )

    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=dataset["train"],
        eval_dataset=dataset["val"],
        processing_class=tokenizer,
        peft_config=lora,
    )
    trainer.train()
    trainer.save_model(args.out)
    tokenizer.save_pretrained(args.out)
    log.info("Адаптер сохранён в %s", args.out)


if __name__ == "__main__":
    main()
