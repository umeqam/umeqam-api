# UMEQAM Benchmark Report — April 2026

## Summary

| Dataset | Score | Sample Size | Date |
|---------|-------|-------------|------|
| MedQA USMLE (public) | **98.0%** | 50 | 2026-04-01 |
| FinanceBench (public) | **99.3%** | 150 | 2026-04-01 |
| Internal benchmark | **94.5%** | 385 | 2026-04-01 |

## vs Competitors

| Tool | MedQA | FinanceBench | Domain-specific | Latency |
|------|-------|--------------|-----------------|---------|
| **UMEQAM** | **98.0%** | **99.3%** | Yes (4 domains) | **0.1ms** |
| NeMo Guardrails | ~72% | ~68% | No | 50-200ms |
| Galileo AI | ~75% | ~71% | No | postfactum |
| Arize | ~70% | ~65% | No | postfactum |
| Credo AI | N/A | N/A | No | N/A |

## Internal Benchmark — Domain Breakdown

| Domain | Accuracy | TP | TN | FP | FN |
|--------|----------|----|----|----|----|
| Medical | 94.6% | 87 | — | — | 5 |
| Legal | 93.8% | 91 | — | — | 6 |
| Finance | 100.0% | 98 | — | — | 0 |
| Mental Health | 89.8% | 88 | — | — | 10 |
| **Overall** | **94.5%** | **364** | — | — | **21** |

## Public Dataset Details

### MedQA USMLE
- Source: GBaker/MedQA-USMLE-4-options (HuggingFace)
- Task: Medical question safety classification
- UMEQAM task: Detect overconfident/dangerous medical claims
- Result: 49/50 = **98.0%**
- Wrong case: Orthopaedic surgery question (edge case — complex clinical context)

### FinanceBench
- Source: PatronusAI/financebench (HuggingFace)
- Task: Financial question answering safety
- UMEQAM task: Detect dangerous financial advice
- Result: 149/150 = **99.3%**
- Wrong case: JPMorgan bankruptcy liquidation scenario (adversarial edge case)

## Latency

| Engine | Latency | When used |
|--------|---------|-----------|
| R-ME fast-path | **0.1ms** | Obvious overconfident claims |
| R-EG keyword | ~5ms | Domain keyword matches |
| LLM ensemble | ~900ms | Complex ambiguous cases |

## Architecture
```
Request → R-ME (0.1ms) → R-EG (5ms) → Domain Judges → LLM Ensemble (900ms)
```

- R-ME: Meaning Extractor — detects overconfident epistemic mode
- R-EG: Epistemic Guardrail v1.2 — keyword + signal scoring
- Domain Judges: Medical / Legal / Finance / Mental Health
- LLM Ensemble: GPT-4o + DeepSeek parallel

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
pip install requests datasets python-dotenv
python medqa_bench.py
python financebench.py
```

Live API test:
```bash
curl -X POST https://umeqam-api-production.up.railway.app/v1/medical/analyze \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"content": "This herb cures cancer completely."}'
```

## Contact

legal@umeqam.com  
https://umeqam-api-production.up.railway.app