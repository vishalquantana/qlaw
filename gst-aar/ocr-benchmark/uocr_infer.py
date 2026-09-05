#!/usr/bin/env python3
"""Run Baidu Unlimited-OCR (transformers path) on the benchmark PDF, on MPS/CPU.

Model: baidu/Unlimited-OCR (Deepseek-V2-based VLM, 6.67 GB bf16).
Usage: python uocr_infer.py [page_numbers...]   (1-based; default: full doc)
"""
import os
import sys
import time
from pathlib import Path

import torch

BASE = Path(__file__).parent
PDF = BASE.parent / "data" / "pdfs" / "Rajasthan" / "9-order_allen_institute_30_july_2026.pdf"
OUT = BASE / "texts" / "_unlimited-ocr_full.txt"

def load_model():
    from transformers import AutoModel, AutoTokenizer, AutoConfig

    # Compat: Unlimited-OCR's config (forked from DeepSeek-OCR) predates strict
    # attribute access in transformers 4.5x. Fill every attribute the modeling
    # code reads but the shipped config.json doesn't declare, with DeepSeek-V2
    # defaults, so nothing falls through as a missing key.
    model_path = sorted(Path(os.path.expanduser(
        "~/.cache/huggingface/hub/models--baidu--Unlimited-OCR/snapshots")).iterdir())[0]
    config = AutoConfig.from_pretrained(str(model_path), trust_remote_code=True)
    defaults = {
        "attention_bias": False, "attention_dropout": 0.0, "aux_loss_alpha": 0.001,
        "cache_implementation": None, "ep_size": 1, "hidden_act": "silu",
        "initializer_range": 0.02, "max_position_embeddings": 163840,
        "moe_layer_freq": 1, "n_group": 1, "n_positions": 163840,
        "num_labels": 3, "output_attentions": False, "output_hidden_states": False,
        "pad_token_id": 1, "problem_type": None, "rms_norm_eps": 1e-6,
        "routed_scaling_factor": 1.0, "seq_aux": True, "scoring_func": "sigmoid",
        "n_routed_experts": 64, "n_shared_experts": 2, "num_experts_per_tok": 6,
        "kv_lora_rank": 512, "q_lora_rank": 1536, "qk_nope_head_dim": 128,
        "qk_rope_head_dim": 64, "v_head_dim": 128, "moe_intermediate_size": 1407,
        "norm_topk_prob": True, "use_mla": True, "num_key_value_heads": 16,
        "rope_scaling": {"rope_type": "default", "rope_theta": 10000}, "sliding_window": None, "topk_group": 1,
        "topk_method": "greedy", "use_cache": True, "use_return_dict": True,
    }
    for k, v in defaults.items():
        if not hasattr(config, k):
            setattr(config, k, v)
        lc = getattr(config, "language_config", None)
        if isinstance(lc, dict):
            lc.setdefault(k, v)
        elif lc is not None and not hasattr(lc, k):
            setattr(lc, k, v)

    pages_wanted = set(int(x) for x in sys.argv[1:]) if len(sys.argv) > 1 else None

    print("loading model...", flush=True)
    t0 = time.time()
    tokenizer = AutoTokenizer.from_pretrained(str(model_path), trust_remote_code=True)
    model = AutoModel.from_pretrained(
        str(model_path), trust_remote_code=True, config=config,
        torch_dtype=torch.bfloat16,
        attn_implementation="eager",
    )
    # MPS crashes in this model's vision encoder (garbage gather index); allow
    # forcing CPU via env (UOCR_DEVICE=cpu)
    device = os.environ.get("UOCR_DEVICE") or ("mps" if torch.backends.mps.is_available() else "cpu")
    model = model.eval().to(device)
    # The published checkpoint ships a corrupted position_ids buffer in the
    # vision encoder (garbage ints instead of arange -> embedding IndexError).
    # Rebuild every one deterministically.
    for name, mod in model.named_modules():
        if hasattr(mod, "position_ids") and hasattr(mod, "position_embedding"):
            n = mod.position_embedding.weight.shape[0]
            mod.position_ids = torch.arange(n).unsqueeze(0).to(device)
    print(f"model on {device} in {time.time()-t0:.1f}s", flush=True)
    return model, tokenizer, device


def main():
    model, tokenizer, device = load_model()
    pages_wanted = set(int(x) for x in sys.argv[1:]) if len(sys.argv) > 1 else None

    import fitz
    doc = fitz.open(PDF)
    import tempfile
    tmp = tempfile.mkdtemp(prefix="uocr_")
    all_text = []
    total = 0.0
    for i, page in enumerate(doc):
        n = i + 1
        if pages_wanted and n not in pages_wanted:
            continue
        img = os.path.join(tmp, f"p{n:02d}.png")
        page.get_pixmap(dpi=200).save(img)
        t0 = time.time()
        try:
            res = model.infer(
                tokenizer, prompt="<image>document parsing.",
                image_file=img, output_path=str(BASE / "uocr-out"),
                base_size=1024, image_size=1024, crop_mode=bool(int(os.environ.get("UOCR_CROP", "0"))),
                max_length=8192, no_repeat_ngram_size=35, ngram_window=128,
                save_results=True,
            )
            dt = time.time() - t0
            total += dt
            # infer() writes the result to output_path/<img>.md (save_results) or
            # returns text; prefer the file so we capture exactly what it produced
            md = (BASE / "uocr-out" / (Path(img).stem + ".md"))
            text = md.read_text(encoding="utf-8") if md.exists() else (res if isinstance(res, str) else "")
            all_text.append(text)
            print(f"page {n}: {dt:.1f}s, {len(text)} chars", flush=True)
        except Exception as e:
            if os.environ.get("UOCR_TRACE"):
                raise
            print(f"page {n}: ERROR {type(e).__name__}: {str(e)[:200]}", flush=True)
        break_check = False

    if not pages_wanted:
        OUT.write_text("\n\n".join(all_text), encoding="utf-8")
        full = OUT.read_text()
        print(f"\nTOTAL: {total:.1f}s, {len(full)} chars", flush=True)
        for fact in ["RAJ/AAR", "AAVCA8216C1ZI", "13/2020", "30.07.2026"]:
            print(f"  {fact}: {'HIT' if fact in full else 'MISS'}", flush=True)
        hindi = sum(1 for c in full if "\u0900" <= c <= "\u097F")
        print(f"  Devanagari chars: {hindi}", flush=True)

if __name__ == "__main__":
    main()
