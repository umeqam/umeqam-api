# UMEQAM Benchmark Report — April 2026

## Summary

| Dataset | Score | Sample Size | Date |
|---------|-------|-------------|------|
| MedQA USMLE (public) | **98.0%** | 50 / 1273 full run in progress | 2026-04-01 |
| FinanceBench (public) | **99.3%** | 150 (full dataset) | 2026-04-01 |
| Internal benchmark | **94.5%** | 385 | 2026-04-01 |

> Note: MedQA full run (1273 questions) in progress. Will be updated with final results.

## Competitor Comparison

Independent third-party comparison pending.
We do not publish competitor accuracy claims without verifiable sources.

## Internal Benchmark — Domain Breakdown

| Domain | Accuracy | Correct | Total |
|--------|----------|---------|-------|
| Medical | 94.6% | 87 | 92 |
| Legal | 93.8% | 91 | 97 |
| Finance | 100.0% | 98 | 98 |
| Mental Health | 89.8% | 88 | 98 |
| **Overall** | **94.5%** | **364** | **385** |

## Public Dataset Details

### MedQA USMLE
- Source: GBaker/MedQA-USMLE-4-options (HuggingFace)
- Link: https://huggingface.co/datasets/GBaker/MedQA-USMLE-4-options
- Task: US Medical Licensing Examination questions
- UMEQAM task: Detect overconfident/dangerous medical claims
- Preliminary result (n=50): 49/50 = 98.0%
- Full result (n=1273): in progress

### FinanceBench
- Source: PatronusAI/financebench (HuggingFace)
- Link: https://huggingface.co/datasets/PatronusAI/financebench
- Task: Financial question answering safety
- UMEQAM task: Detect dangerous financial advice
- Result: 149/150 = 99.3% (full dataset)

## Latency

| Engine | Latency | Condition |
|--------|---------|-----------|
| R-ME fast-path | **0.1ms** | Overconfident absolute claims |
| R-EG keyword | ~5ms | Domain keyword matches |
| LLM ensemble | ~900ms | Complex ambiguous cases |

## Architecture
```
Request -> R-ME (0.1ms) -> R-EG (5ms) -> Domain Judges -> LLM Ensemble (~900ms)
```

- R-ME: Meaning Extractor — detects overconfident epistemic mode
- R-EG: Epistemic Guardrail v1.2 — keyword + signal scoring  
- Domain Judges: Medical / Legal / Finance / Mental Health
- LLM Ensemble: GPT-4o + DeepSeek

## Compliance Alignment

- EU AI Act Article 9 (Risk management)
- GDPR (PII redaction built-in)
- MiFID II (Finance domain)
- WHO Safe Messaging (Mental Health domain)

## Reproducibility

All benchmark scripts available at:
https://github.com/umeqam/umeqam-api

Run yourself:
```bash
git clone https://github.com/umeqam/umeqam-api
pip install requests datasets python-dotenv openai
python medqa_bench.py
python financebench.py
```

## Contact

legal@umeqam.com
https://umeqam-api-production.up.railway.app
