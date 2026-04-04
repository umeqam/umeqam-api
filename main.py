from fastapi import FastAPI
from pydantic import BaseModel
import sys
import os
sys.path.insert(0, os.getcwd())
from core.models import DomainResult

app = FastAPI(
    title="UMEQAM AI Safety",
    description="Epistemic Intelligence Engine v2.0",
    version="2.0.0"
)

class RequestModel(BaseModel):
    content: str

class RMethodModel(BaseModel):
    prompt: str
    response: str
    js_divergence: float = 0.03
    adversarial_pressure: float = 0.05
    memory_drift: float = 0.2

class FullModel(BaseModel):
    content: str
    jurisdiction: str = "EU"
    domain_weights: dict = {"medical": 0.30, "legal": 0.35, "finance": 0.25, "mental": 0.10}

# ─────────────────────────────────────────────
# HEALTH
# ─────────────────────────────────────────────
@app.get("/v1/health")
def health():
    return {
        "status": "ok",
        "version": "2.0.0",
        "endpoints": [
            "/v1/health",
            "/v1/analyze",
            "/v1/rmethod",
            "/v1/signals",
            "/v1/divergent",
            "/v1/full"
        ]
    }

# ─────────────────────────────────────────────
# ANALYZE — существующий обновлённый
# ─────────────────────────────────────────────
@app.post("/v1/analyze")
def aggregated_analyze(req: RequestModel):
    print("=== ANALYZE ===", repr(req.content[:80]))
    results = {}
    domains = ["medical", "legal", "finance", "mental"]
    for domain_name in domains:
        try:
            module = __import__(f"domains.{domain_name}.judge", fromlist=[""])
            CouncilClass = getattr(module, f"{domain_name.capitalize()}JudgeCouncil")
            council = CouncilClass()
            result = council.analyze(req.content)
            results[domain_name] = result
        except Exception as e:
            results[domain_name] = DomainResult(
                decision="REVIEW", score=40.0,
                reasons=[f"Domain error: {str(e)}"],
                confidence=0.4, domain=domain_name
            )
    try:
        from core.risk_engine import GlobalRiskEngine
        engine = GlobalRiskEngine()
        final_decision = engine.decide(results)
        overall_score = engine.get_overall_score(results)
        return {
            "decision": final_decision,
            "score": round(overall_score, 1),
            "version": "2.0.0",
            "results": {k: v.model_dump() for k, v in results.items()}
        }
    except Exception as e:
        return {"decision": "REVIEW", "score": 50.0, "error": str(e)}

# ─────────────────────────────────────────────
# R-METHOD — governance score
# ─────────────────────────────────────────────
@app.post("/v1/rmethod")
def rmethod_analyze(req: RMethodModel):
    print("=== R-METHOD ===", repr(req.prompt[:60]))
    try:
        from core.umeqam_rmethod_v1 import run_rmethod
        result = run_rmethod(
            prompt=req.prompt,
            llm_response=req.response,
            js_divergence=req.js_divergence,
            adversarial_pressure=req.adversarial_pressure,
            memory_drift=req.memory_drift
        )
        return {
            "status": "ok",
            "version": "2.0.0",
            "module": "R-Method v1.1",
            **result
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

# ─────────────────────────────────────────────
# SIGNALS — Signal Stack v1.2
# ─────────────────────────────────────────────
class SignalModel(BaseModel):
    s1: float = 0.0
    s2: float = 0.0
    s3: float = 0.0
    s5: float = 0.0
    s7: float = 0.0
    s4: float = 0.0
    s6: float = 0.0
    s8: float = 0.0
    source_quality: float = 1.0

@app.post("/v1/signals")
def signal_stack(req: SignalModel):
    print("=== SIGNAL STACK ===")
    try:
        from core.umeqam_signal_stack import run_signal_stack
        decision, score, details = run_signal_stack(
            s1=req.s1, s2=req.s2, s3=req.s3,
            s5=req.s5, s7=req.s7, s4=req.s4,
            s6=req.s6, s8=req.s8,
            source_quality=req.source_quality
        )
        return {
            "status": "ok",
            "version": "2.0.0",
            "module": "Signal Stack v1.2",
            "decision": decision,
            "score": round(score, 4),
            "details": details
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

# ─────────────────────────────────────────────
# DIVERGENT — DIV Module v1.0
# ─────────────────────────────────────────────
class DivModel(BaseModel):
    content: str
    jurisdiction: str = "EU"
    path_count: int = 5

@app.post("/v1/divergent")
def divergent_analyze(req: DivModel):
    print("=== DIV MODULE ===", repr(req.content[:60]))
    try:
        from core.umeqam_rme_v1 import MeaningExtractor
        extractor = MeaningExtractor()
        mv = extractor.extract(req.content)
        meaning = extractor.to_dict(mv)
        return {
            "status": "ok",
            "version": "2.0.0",
            "module": "DIV v1.0",
            "jurisdiction": req.jurisdiction,
            "meaning": meaning,
            "note": "Full DIV paths via /v1/full endpoint",
            "dominant_domain": max(
                meaning["domain_signals"].items(),
                key=lambda x: x[1]
            )[0] if any(v > 0 for v in meaning["domain_signals"].values()) else "general"
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

# ─────────────────────────────────────────────
# FULL — полный стек
# ─────────────────────────────────────────────
@app.post("/v1/full")
def full_analyze(req: FullModel):
    print("=== FULL PIPELINE ===", repr(req.content[:60]))
    result = {}

    # Step 1: R-ME
    try:
        from core.umeqam_rme_v1 import MeaningExtractor
        extractor = MeaningExtractor()
        mv = extractor.extract(req.content)
        meaning = extractor.to_dict(mv)
        result["rme"] = meaning
    except Exception as e:
        result["rme"] = {"error": str(e)}

    # Step 2: R-Method
    try:
        from core.umeqam_rmethod_v1 import run_rmethod
        rmethod = run_rmethod(prompt="", llm_response=req.content)
        result["rmethod"] = rmethod
    except Exception as e:
        result["rmethod"] = {"error": str(e)}

    # Step 3: Domain analysis
    domain_results = {}
    domains = ["medical", "legal", "finance", "mental"]
    for domain_name in domains:
        try:
            module = __import__(f"domains.{domain_name}.judge", fromlist=[""])
            CouncilClass = getattr(module, f"{domain_name.capitalize()}JudgeCouncil")
            council = CouncilClass()
            dr = council.analyze(req.content)
            domain_results[domain_name] = dr.model_dump()
        except Exception as e:
            domain_results[domain_name] = {"decision": "REVIEW", "score": 40.0, "error": str(e)}
    result["domains"] = domain_results

    # Step 4: Final decision
    try:
        from core.risk_engine import GlobalRiskEngine
        from core.models import DomainResult
        engine = GlobalRiskEngine()
        dr_objects = {}
        for k, v in domain_results.items():
            if "error" not in v:
                dr_objects[k] = DomainResult(**{
                    "decision": v.get("decision", "REVIEW"),
                    "score": v.get("score", 40.0),
                    "reasons": v.get("reasons", []),
                    "confidence": v.get("confidence", 0.4),
                    "domain": k
                })
        final_decision = engine.decide(dr_objects) if dr_objects else "REVIEW"
        overall_score = engine.get_overall_score(dr_objects) if dr_objects else 50.0
        result["final"] = {
            "decision": final_decision,
            "score": round(overall_score, 1),
            "governance_score": result.get("rmethod", {}).get("governance_score", 0.0),
            "jurisdiction": req.jurisdiction,
            "version": "2.0.0"
        }
    except Exception as e:
        result["final"] = {"decision": "REVIEW", "score": 50.0, "error": str(e)}

    return {"status": "ok", "version": "2.0.0", "module": "UMEQAM FULL", **result}

print("UMEQAM v2.0.0 — 5 endpoints loaded")

# ─────────────────────────────────────────────
# PIPELINE v1.0 — full integrated stack
# ─────────────────────────────────────────────
class PipelineModel(BaseModel):
    content: str
    domain: str = "general"
    human_status: str = "available"

@app.post("/v1/pipeline")
def pipeline_analyze(req: PipelineModel):
    print("=== PIPELINE ===", repr(req.content[:60]))
    try:
        import sys
        sys.path.insert(0, os.getcwd())
        from core.umeqam_pipeline import run_pipeline
        result = run_pipeline(
            content=req.content,
            domain=req.domain,
            human_status=req.human_status
        )
        return result
    except Exception as e:
        return {"status": "error", "error": str(e)}
