# SilverForge

[![한국어](https://img.shields.io/badge/lang-한국어-blue.svg)](README.ko.md)

**Convert PDF to Structured Markdown** - Ground Truth Data Generation Tool for VLM/SLM Training

> Upstage Ambassador Season 2 Project

## Problem Statement

High-quality **Ground Truth (GT) data** is essential for training VLM (Vision Language Model) and SLM (Small Language Model). Traditional LaTeX → Pandoc conversion has significant limitations:

| Method | Coverage | Table Recognition | Limitation |
|--------|----------|-------------------|------------|
| LaTeX → Pandoc | 40-50% | Incomplete | Requires LaTeX source |
| PyMuPDF | 60-70% | Not supported | Structure loss |
| **Upstage Document Parse** | **100%** | **Perfect** | - |

## Solution

**SilverForge** leverages [Upstage Document Parse](https://console.upstage.ai/) API to:

1. **Direct PDF Parsing** - 100% coverage without LaTeX source
2. **Perfect Table Recognition** - Traditional: 0 tables → SilverForge: 10 tables
3. **Heading Hierarchy Restoration** - 95%+ accuracy with rule-based approach

```
PDF → parse_pdf() → Raw Markdown → refine_headings() → Silver Markdown
         ↑                              ↑
    Upstage API                   Rule-based (regex)
```

## Benchmark Results

**Test Document**: "Attention Is All You Need" (Vaswani et al., 2017)

| Metric | LaTeX+Pandoc | SilverForge |
|--------|--------------|-------------|
| Table Recognition | 0 | **10** |
| Heading Restoration | Manual required | **95%+ Auto** |
| Formula Preservation | Partial | **Complete** |
| Source Required | LaTeX required | **PDF only** |

## Quick Start

### Installation

```bash
# Using uv (recommended)
uv pip install -e .

# Using pip
pip install -e .
```

### Environment Setup

```bash
cp .env.example .env
# Add your UPSTAGE_API_KEY to .env file
```

### Usage

```python
from silverforge import process

# PDF → Silver Markdown (one-step)
silver_md = process("paper.pdf")

# Or step-by-step
from silverforge import parse_pdf, refine_headings

raw_md = parse_pdf("paper.pdf")      # Upstage API call
silver_md = refine_headings(raw_md)  # Heading restoration
```

### CLI Example

```bash
python example.py paper.pdf
# -> Creates paper_silver.md
```

### Web UI Console

```bash
# Run Streamlit UI (recommended)
python run_ui.py
# -> http://localhost:8502

# Run FastAPI server (for API usage)
python run_ui.py --api
# -> http://localhost:8000
# -> API docs: http://localhost:8000/docs
```

**UI Features:**
- Multiple PDF upload (Drag & Drop)
- Sequential processing with real-time progress
- Quality score display (Curator Agent)
- Result preview (popup)
- Individual/bulk download (ZIP)

## Dataset Curator Agent

An Agent that automatically evaluates the quality of Silver data.

```python
from silverforge import curate

result = curate(silver_md)
print(result)
# {
#   "pass": True,
#   "overall_score": 85,
#   "recommendation": "Ready for chunking - all checks passed"
# }
```

### Quality Check Items

1. **Text Quality**: CER/WER calculation (compared to original)
2. **Structure Quality**: Heading hierarchy, table structure, formula blocks
3. **Semantic Quality**: Logic/completeness/coherence evaluation based on Solar Pro2

```bash
python example_curate.py results/attention_paper.md
```

## Project Structure

```
silverforge/
├── silverforge/
│   ├── __init__.py      # exports
│   ├── core.py          # parsing (parse_pdf, refine_headings)
│   ├── curator.py       # quality check (curate)
│   ├── api.py           # FastAPI backend
│   └── app.py           # Streamlit UI
├── run_ui.py            # UI launcher script
├── example.py           # parsing example
├── example_curate.py    # quality check example
└── results/
    └── attention_paper.md  # PoC output
```

## API Reference

### Core Functions

#### `parse_pdf(pdf_path: str) -> str`
Parse PDF file using Upstage Document Parse API and return raw markdown

#### `refine_headings(markdown: str) -> str`
Restore heading hierarchy using rule-based approach

#### `process(pdf_path: str) -> str`
Convenience function combining `parse_pdf` + `refine_headings`

### Curator Functions

#### `curate(silver_md: str, original_text: str = None) -> dict`
Full quality evaluation (text + structure + semantic)

#### `evaluate_structure(silver_md: str) -> dict`
Structure quality evaluation (heading, table, formula)

#### `evaluate_semantic(silver_md: str) -> dict`
Semantic quality evaluation based on Solar Pro2

## Acknowledgements

- [Upstage](https://upstage.ai/) - Document Parse API, Solar Pro2
- Upstage Ambassador Season 2 Program

## License

MIT
