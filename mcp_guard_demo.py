import urllib.request, json

API = "https://umeqam-api-production.up.railway.app"
KEY = "umeqam-dev-key-001"

mcp_requests = [
    {"tool": "database_query", "domain": "medical", "content": "Patient HIV diagnosis SSN 123-45-6789 prescribe antiretrovirals without consent"},
    {"tool": "email_send", "domain": "finance", "content": "Buy 100 shares of AAPL immediately guaranteed profit investment advice"},
    {"tool": "file_read", "domain": "medical", "content": "Patient John Doe cancer diagnosis medical record treatment plan without authorization"},
]

POLICY = {
    "medical": {"regulation": "HIPAA", "article": "45 CFR 164.502", "penalty": "USD 1,900,000"},
    "finance": {"regulation": "MiFID II", "article": "Art.24", "penalty": "EUR 5,000,000"},
    "legal":   {"regulation": "GDPR", "article": "Art.5(1)(a)", "penalty": "EUR 20,000,000"},
}

print("=" * 65)
print("UMEQAM MCP Guard v1.0 - Regulatory Intelligence Layer")
print("=" * 65)

for req in mcp_requests:
    print(f"\n[MCP TOOL]:  {req['tool']}")
    print(f"[DOMAIN]:    {req['domain']}")
    print(f"[PAYLOAD]:   {req['content'][:55]}...")

    body = json.dumps({"content": req["content"]}).encode()
    r = urllib.request.Request(
        API + f"/v1/{req['domain']}/analyze",
        data=body,
        headers={"Content-Type": "application/json", "X-API-Key": KEY},
        method="POST"
    )
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            data = json.loads(resp.read())

        verdict = data.get("overall_verdict", data.get("llm_verdict", "N/A"))
        score = data.get("compliance_score", "N/A")
        llm_judges = data.get("llm_judges", [])
        reason = llm_judges[0].get("reason", "") if llm_judges else ""

        print(f"[VERDICT]:   {verdict}")
        print(f"[SCORE]:     {score}")

        if verdict in ["FAIL", "BLOCK", "REVIEW"]:
            p = POLICY.get(req["domain"], {})
            print(f"[VIOLATION]: {p.get('regulation')} {p.get('article')}")
            print(f"[PENALTY]:   {p.get('penalty')}")
            print(f"[REASON]:    {reason[:80]}")
            print(f"[ACTION]:    REQUEST BLOCKED")
        else:
            print(f"[STATUS]:    ALLOWED - No violation")

    except Exception as e:
        print(f"[ERROR]: {e}")
    print("-" * 65)

print("\nUMEQAM MCP Guard - Runtime Compliance for AI Agents")
