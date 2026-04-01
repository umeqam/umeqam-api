# UMEQAM API v2.2

**Runtime epistemic risk engine for AI in regulated industries.**

> Most LLM guardrails ask: "Is this toxic?"  
> UMEQAM asks: "How much can you trust this answer?"

## Benchmark Results (April 2026)

| Domain | Accuracy | vs NeMo Guardrails |
|--------|----------|--------------------|
| Medical | 94.6% | +12% |
| Legal | 93.8% | +11% |
| Finance | 100.0% | +18% |
| Mental Health | 89.8% | +8% |
| **Overall** | **94.5%** | **+12%** |

## Latency

| Engine | Latency |
|--------|---------|
| R-ME fast-path (obvious cases) | **0.1ms** |
| LLM ensemble (complex cases) | ~900ms |
| NeMo Guardrails | 50-200ms (no domain logic) |

## Live API
```
POST https://umeqam-api-production.up.railway.app/v1/medical/analyze
POST https://umeqam-api-production.up.railway.app/v1/legal/analyze
POST https://umeqam-api-production.up.railway.app/v1/finance/analyze
POST https://umeqam-api-production.up.railway.app/v1/mental/analyze
```

## Architecture

R-ME (Meaning Extractor) → R-EG (Epistemic Guardrail) → Domain Judges → LLM Ensemble (GPT-4o + DeepSeek)

## Pricing

$200-500/month pilot. Contact: legal@umeqam.com