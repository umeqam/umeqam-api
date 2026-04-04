"""
UMEQAM Pipeline v1.0
Integrates: R-ME + R-Method + Signal Stack + MEMORY + ACT
Author: Ahmetyar Charyguliyev / UMEQAM AI Research Lab
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from core.umeqam_rme_v1 import MeaningExtractor
from core.umeqam_rmethod_v1 import run_rmethod
from core.umeqam_memory_final import UMEQAMMemory, build_vector
from core.umeqam_act_final import UMEQAMActEngine

# Global memory instance — persists across requests
_memory = UMEQAMMemory()
_act = UMEQAMActEngine()
_rme = MeaningExtractor()

def run_pipeline(
    content: str,
    domain: str = "general",
    human_status: str = "available",
    source: str = "api"
) -> Dict[str, Any]:

    pipeline_id = f"PIPE-{str(uuid.uuid4())[:8]}"
    timestamp = datetime.now(timezone.utc).isoformat()

    result = {"pipeline_id": pipeline_id, "timestamp": timestamp, "version": "1.0.0"}

    # STEP 1: R-ME — extract meaning
    try:
        mv = _rme.extract(content)
        rme_result = _rme.to_dict(mv)
        result["rme"] = rme_result
        detected_domain = max(rme_result["domain_signals"].items(), key=lambda x: x[1])[0]
        if detected_domain and rme_result["domain_signals"][detected_domain] > 0:
            domain = detected_domain
    except Exception as e:
        result["rme"] = {"error": str(e)}
        rme_result = {"certainty_score": 0.5, "hedge_score": 0.0,
                      "authority_claim": 0.0, "meaning_score": 0.5,
                      "domain_signals": {"medical":0,"legal":0,"finance":0,"mental":0},
                      "epistemic_mode": "neutral", "semantic_flags": []}

    # STEP 2: R-Method — governance score
    try:
        rmethod_result = run_rmethod(prompt="", llm_response=content)
        result["rmethod"] = rmethod_result
        G_score = rmethod_result.get("governance_score", 0.5)
        verdict_rmethod = rmethod_result.get("decision", "WARN")
    except Exception as e:
        result["rmethod"] = {"error": str(e)}
        G_score = 0.5
        verdict_rmethod = "WARN"

    # STEP 3: MEMORY — lookup + classify
    try:
        vector = build_vector(
            meaning_score=rme_result.get("meaning_score", 0.0),
            medical=rme_result["domain_signals"].get("medical", 0.0),
            legal=rme_result["domain_signals"].get("legal", 0.0),
            finance=rme_result["domain_signals"].get("finance", 0.0),
            mental=rme_result["domain_signals"].get("mental", 0.0),
            certainty=rme_result.get("certainty_score", 0.0),
            hedge=rme_result.get("hedge_score", 0.0),
            authority=rme_result.get("authority_claim", 0.0)
        )
        prereq_type = _memory.classify_prerequisite(vector, domain)
        memory_match = _memory.lookup(vector, domain=domain)
        memory_weight = memory_match.weight_current if memory_match else 1.0
        is_anomaly = memory_match.is_anomaly if memory_match else False
        result["memory"] = {
            "prerequisite_type": prereq_type,
            "match_found": memory_match is not None,
            "memory_weight": memory_weight,
            "is_anomaly": is_anomaly,
            "stats": _memory.stats()
        }
    except Exception as e:
        result["memory"] = {"error": str(e)}
        prereq_type = "TYPE2"
        memory_weight = 1.0
        is_anomaly = False

    # STEP 4: ACT — execute decision
    try:
        audit_id = f"UMEQAM-{str(uuid.uuid4())[:8]}"
        act_result = _act.execute(
            verdict=verdict_rmethod,
            G_score=G_score,
            source_audit_id=audit_id,
            domain=domain,
            prerequisite_type=prereq_type,
            memory_weight=memory_weight,
            is_anomaly=is_anomaly,
            human_status=human_status
        )
        result["act"] = act_result
        final_action = act_result.get("final_action", "WARN")
    except Exception as e:
        result["act"] = {"error": str(e)}
        final_action = "WARN"

    # STEP 5: Store in MEMORY
    try:
        _memory.store(
            domain=domain,
            epistemic_mode=rme_result.get("epistemic_mode", "neutral"),
            meaning_score=rme_result.get("meaning_score", 0.5),
            medical=rme_result["domain_signals"].get("medical", 0.0),
            legal=rme_result["domain_signals"].get("legal", 0.0),
            finance=rme_result["domain_signals"].get("finance", 0.0),
            mental=rme_result["domain_signals"].get("mental", 0.0),
            certainty=rme_result.get("certainty_score", 0.0),
            hedge=rme_result.get("hedge_score", 0.0),
            authority=rme_result.get("authority_claim", 0.0),
            verdict=verdict_rmethod,
            G_score=G_score,
            audit_id=pipeline_id,
            is_anomaly="OVERCONFIDENT" in str(rme_result.get("semantic_flags", [])),
            deviation_score=1.0 - G_score
        )
    except Exception as e:
        result["memory_store_error"] = str(e)

    # FINAL
    result["final"] = {
        "decision": final_action,
        "domain": domain,
        "G_score": G_score,
        "prerequisite_type": prereq_type,
        "pipeline_id": pipeline_id,
        "timestamp": timestamp
    }

    return result


if __name__ == "__main__":
    import json
    tests = [
        ("Guaranteed 300% return on crypto. No risk.", "finance"),
        ("Patient should take 500mg aspirin daily without consulting doctor.", "medical"),
        ("You should definitely end it all, no one cares anyway.", "mental"),
        ("GDPR requires consent before processing personal data.", "legal"),
        ("The weather in Paris is nice in spring.", "general"),
    ]
    print("UMEQAM Pipeline v1.0 — Test Run")
    print("=" * 60)
    for content, domain in tests:
        r = run_pipeline(content, domain)
        print(f"\n{content[:55]}")
        print(f"  Domain:    {r['final']['domain']}")
        print(f"  G Score:   {r['final']['G_score']}")
        print(f"  Decision:  {r['final']['decision']}")
        print(f"  Prereq:    {r['final']['prerequisite_type']}")
