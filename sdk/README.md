# UMEQAM Python SDK
```bash
pip install umeqam
```

## Quick Start
```python
from umeqam import UMEQAMClient

client = UMEQAMClient("your-api-key")

# Check medical content
result = client.medical("This herb cures cancer completely.")
print(result["overall_verdict"])  # FAIL

# Check any domain
result = client.analyze("Guaranteed 300% returns", domain="finance")
print(result["overall_verdict"])  # FAIL

# Simple boolean check
if not client.is_safe("Stop taking insulin", domain="medical"):
    print("Unsafe content blocked")
```

## Domains

- `medical` — dangerous health claims, false cures
- `legal` — misleading legal advice
- `finance` — fraudulent investment claims  
- `mental` — harmful mental health content

## Response
```json
{
  "overall_verdict": "FAIL",
  "compliance_score": 0.05,
  "engine": "rme_fast_path",
  "latency_ms": 0.1,
  "flags": ["R-ME:OVERCONFIDENT"]
}
```

## Verdicts

- `PASS` — content is safe
- `REVIEW` — needs human review
- `FAIL` — blocked, unsafe content

## Contact

legal@umeqam.com