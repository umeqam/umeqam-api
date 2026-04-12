"""
Adapter layer: exposes legacy analyze(prompt, response, domain, start_time, end_time)
API expected by main.py, backed by real InternalShield v2 (S1-S12).
"""
import uuid
from umeqam_internal_shield_v2 import InternalShield, ShieldStatus

_shield = InternalShield()

_VERDICT_MAP = {
    ShieldStatus.CLEAN: "CLEAN",
    ShieldStatus.SUSPICIOUS: "SUSPICIOUS",
    ShieldStatus.BLOCKED: "BLOCKED",
}

def analyze(prompt: str = "", response: str = "", domain: str = "general",
            start_time=None, end_time=None, **kwargs):
    audit_id = uuid.uuid4().hex[:16]
    status, risk, signals, explanation = _shield.evaluate(
        response=response or "",
        query=prompt or "",
        domain=domain or "general",
        audit_id=audit_id,
    )
    flags = []
    for name, sig in (signals or {}).items():
        try:
            if getattr(sig, "triggered", False) or getattr(sig, "score", 0) > 0.5:
                flags.append(name)
        except Exception:
            pass
    return {
        "verdict": _VERDICT_MAP.get(status, str(status)),
        "risk_score": round(float(risk), 4),
        "audit_id": audit_id,
        "flags": flags,
        "explanation": explanation,
        "signals_count": len(signals) if signals else 0,
    }
