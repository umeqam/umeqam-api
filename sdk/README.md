# UMEQAM Python SDK

Runtime epistemic risk engine for AI in regulated industries.

## Installation
```bash
pip install umeqam
```

## Quick Start
```python
from umeqam import UMEQAMClient

client = UMEQAMClient("your-api-key")

result = client.medical("This herb cures cancer completely.")
print(result["overall_verdict"])  # FAIL
print(result["latency_ms"])       # 0.1
```

## Domains

### Medical
```python
# FAIL — absolute cure claim
client.medical("Garlic makes you immune to all diseases.")

# FAIL — dangerous self-treatment
client.medical("Stop taking insulin, use honey instead.")

# PASS — safe advice
client.medical("Consult your doctor before changing medication.")
```

### Legal
```python
# FAIL — dangerous legal overconfidence
client.legal("You can sue anyone and win easily without a lawyer.")

# PASS — appropriate advice
client.legal("You should consult a licensed attorney for legal advice.")
```

### Finance
```python
# FAIL — fraudulent investment claim
client.finance("Guaranteed 300% crypto return, zero risk.")

# PASS — appropriate disclaimer
client.finance("Past performance does not guarantee future results.")
```

### Mental Health
```python
# FAIL — dismissive of mental illness
client.mental("Just stop being sad and think positive.")

# PASS — appropriate support
client.mental("Speaking with a therapist can help with depression.")
```

## LangChain Integration
```python
from umeqam.langchain import UMEQAMLangChainGuard
from langchain_openai import ChatOpenAI

guard = UMEQAMLangChainGuard(api_key="your-key", domain="medical")
llm = ChatOpenAI(callbacks=[guard])

# All LLM outputs are automatically checked
response = llm.invoke("What cures cancer?")
```

## Simple Guard
```python
from umeqam.langchain import UMEQAMGuard

guard = UMEQAMGuard(api_key="your-key", domain="finance")

try:
    guard.check("Guaranteed 500% returns!")
except ValueError as e:
    print(e)  # UMEQAM blocked: FAIL - overconfident absolute claim
```

## Response Format
```json
{
  "overall_verdict": "FAIL",
  "compliance_score": 0.05,
  "engine": "rme_fast_path",
  "latency_ms": 0.1,
  "flags": ["R-ME:OVERCONFIDENT", "HIGH_CERTAINTY_NO_HEDGE"],
  "recommendation": "FAIL - overconfident absolute claim detected"
}
```

## Verdicts

| Verdict | Meaning |
|---------|---------|
| `PASS` | Content is safe |
| `REVIEW` | Needs human review |
| `FAIL` | Blocked — unsafe content |

## API Keys

Get your API key: legal@umeqam.com

## Links

- API: https://umeqam-api-production.up.railway.app
- Docs: https://github.com/umeqam/umeqam-api
- Benchmarks: https://github.com/umeqam/umeqam-api/blob/master/BENCHMARK_REPORT.md