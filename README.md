# UMEQAM — Runtime Epistemic Risk Engine

> Most LLM guardrails ask: "Is this toxic?"  
> UMEQAM asks: "How much can you trust this answer?"

Runtime compliance layer for AI in regulated industries. Per-response verdict: **PASS / REVIEW / FAIL**.

## Live Demo

Try it without any login: **https://umeqam.com/umeqam_demo.html**

## Benchmark Results

| Dataset | Score | Sample Size |
|---------|-------|-------------|
| MedQA USMLE (public) | **98.7%** | 1,273 (full test set) |
| FinanceBench (public) | **99.3%** | 150 (full dataset) |
| Internal 4-domain benchmark | **94.5%** | 385 |

All benchmarks are fully reproducible. Run them yourself:
```bash
git clone https://github.com/umeqam/umeqam-api
cd umeqam-api
pip install requests datasets python-dotenv openai

# Set your API keys in .env
cp .env.example .env

# Run MedQA benchmark (1,273 questions)
python medqa_bench.py

# Run FinanceBench (150 questions)
python financebench.py
```

## Install
```bash
pip install umeqam
```

## Quick Start
```python
from umeqam import UMEQAMClient

client = UMEQAMClient("your-api-key")

result = client.finance("Guaranteed 300% return, no risk involved.")
print(result["overall_verdict"])  # FAIL
print(result["latency_ms"])       # 0.7
```

## Domains

- **Medical** — dangerous health claims, false cures
- **Legal** — misleading legal advice  
- **Finance** — fraudulent investment claims
- **Mental Health** — harmful content

## Architecture
```
Request → R-ME (0.1ms) → R-EG (5ms) → Domain Judges → LLM Ensemble (~900ms)
```

- **R-ME** — Meaning Extractor, detects overconfident epistemic mode
- **R-EG** — Epistemic Guardrail v1.2, keyword + signal scoring
- **Domain Judges** — Medical / Legal / Finance / Mental Health
- **LLM Ensemble** — GPT-4o + DeepSeek parallel

## API
```bash
POST https://umeqam-api-production.up.railway.app/v1/finance/analyze
POST https://umeqam-api-production.up.railway.app/v1/medical/analyze
POST https://umeqam-api-production.up.railway.app/v1/legal/analyze
POST https://umeqam-api-production.up.railway.app/v1/mental/analyze

Headers:
  X-API-Key: your-key
  Content-Type: application/json

Body:
  {"content": "your AI response here"}
```

## Pricing

| Plan | Requests/month | Price |
|------|---------------|-------|
| Starter | 10,000 | $200/month |
| Growth | 50,000 | $500/month |
| Enterprise | Unlimited | Contact us |

Pilot: **legal@umeqam.com**

## Compliance

- EU AI Act Articles 9, 12, 13, 15
- GDPR (PII redaction built-in)
- MiFID II (Finance domain)
- WHO Safe Messaging (Mental Health)

## Links

- Benchmark report: [BENCHMARK_REPORT.md](./BENCHMARK_REPORT.md)
- PyPI: [pypi.org/project/umeqam](https://pypi.org/project/umeqam)
- Live API: [umeqam-api-production.up.railway.app](https://umeqam-api-production.up.railway.app)
- Contact: legal@umeqam.com