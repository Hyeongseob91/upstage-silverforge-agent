#!/usr/bin/env python3
"""ArXiv 논문 다운로드 스크립트"""

import urllib.request
import time
from pathlib import Path

# 유명한 AI/ML 논문 19개 (다양한 주제)
PAPERS = [
    # Transformers & LLM
    ("1706.03762", "attention_is_all_you_need"),      # Attention Is All You Need
    ("1810.04805", "bert"),                           # BERT
    ("2005.14165", "gpt3"),                           # GPT-3
    ("2302.13971", "llama"),                          # LLaMA
    ("2307.09288", "llama2"),                         # LLaMA 2

    # Vision
    ("1512.03385", "resnet"),                         # ResNet
    ("2010.11929", "vit"),                            # Vision Transformer
    ("2103.14030", "swin_transformer"),               # Swin Transformer

    # Multimodal
    ("2103.00020", "clip"),                           # CLIP
    ("2204.14198", "flamingo"),                       # Flamingo

    # Diffusion & Generation
    ("2006.11239", "ddpm"),                           # DDPM (Diffusion)
    ("2112.10752", "stable_diffusion"),               # Stable Diffusion (LDM)

    # RL & Agents
    ("1312.5602", "dqn"),                             # DQN
    ("1707.06347", "ppo"),                            # PPO

    # NLP
    ("1301.3781", "word2vec"),                        # Word2Vec
    ("1409.0473", "seq2seq_attention"),               # Seq2Seq with Attention

    # Recent/Misc
    ("2305.10601", "tree_of_thoughts"),               # Tree of Thoughts
    ("2210.03629", "react"),                          # ReAct
    ("2201.11903", "chain_of_thought"),               # Chain of Thought
]

def download_paper(arxiv_id: str, name: str, output_dir: Path) -> bool:
    """단일 논문 다운로드"""
    url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    output_path = output_dir / f"{name}.pdf"

    if output_path.exists():
        print(f"  ⏭️  {name}.pdf (already exists)")
        return True

    try:
        print(f"  ⬇️  {name}.pdf ...", end=" ", flush=True)
        urllib.request.urlretrieve(url, output_path)
        print("✅")
        return True
    except Exception as e:
        print(f"❌ {e}")
        return False

def main():
    output_dir = Path(__file__).parent / "raw_data"
    output_dir.mkdir(exist_ok=True)

    print(f"📥 Downloading {len(PAPERS)} papers to {output_dir}\n")

    success = 0
    for arxiv_id, name in PAPERS:
        if download_paper(arxiv_id, name, output_dir):
            success += 1
        time.sleep(1)  # Rate limiting

    print(f"\n✅ Downloaded {success}/{len(PAPERS)} papers")

if __name__ == "__main__":
    main()
