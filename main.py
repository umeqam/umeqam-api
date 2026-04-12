"""
UMEQAM REST API v2.5.7
Author: Ahmetyar Charyguliyev
Models: GPT-4o + DeepSeek-chat
Shield: Internal anomaly detection on every LLM call
Regulatory: 53 frameworks via universal endpoint
"""

import os
import re
import sys
import time
import uuid
import json
import concurrent.futures
from datetime import datetime
from typing import Optional, Dict, List

from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── .env ──────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── REGULATORY ENGINES ────────────────────────────────────────
from core.umeqam_regulatory_engines_v2 import evaluate_all_regulators
from core.umeqam_mifid_v1 import MiFIDComplianceEngine
import sys as _sys, os as _os
_CORE = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "core")
if _CORE not in _sys.path:
    _sys.path.insert(0, _CORE)

try:
    from umeqam_gdpr_v1 import GDPRComplianceEngine
    GDPR_OK = True
except Exception:
    GDPR_OK = False

try:
    from umeqam_hipaa_v1 import HIPAAComplianceEngine
    HIPAA_OK = True
except Exception:
    HIPAA_OK = False

try:
    from umeqam_eu_ai_act_v1 import EUAIActComplianceEngine
    EUAIACT_OK = True
except Exception:
    EUAIACT_OK = False

class _StubEngine:
    def __init__(self, name, articles):
        self.name = name
        self.articles = articles
    def analyze(self, text, **kwargs):
        import re, uuid
        violations = []
        for art_id, art in self.articles.items():
            for kw in art.get("keywords", []):
                if re.search(kw, text, re.IGNORECASE):
                    violations.append({"rule_id": art_id, "title": art["title"], "severity": art["severity"], "penalty_estimate": art.get("penalty", "varies")})
        score = min(1.0, len(violations) * 0.25)
        verdict = "FAIL" if score >= 0.75 else ("REVIEW" if score > 0 else "PASS")
        return {"verdict": verdict, "risk_score": round(score * 100), "violations": violations, "engine": self.name, "audit_id": "umeqam_" + uuid.uuid4().hex[:8], "framework": self.name}

FCA_ENGINE   = _StubEngine("FCA",   {"FCA_COBS_2_1": {"title": "Fair clear and not misleading", "severity": "critical", "penalty": "unlimited", "keywords": ["guaranteed return", "no risk", "certain profit", "risk-free"]}, "FCA_COBS_4_2": {"title": "Financial promotion", "severity": "high", "penalty": "unlimited", "keywords": ["invest now", "limited time offer"]}})
BAFIN_ENGINE = _StubEngine("BaFin", {"BAFIN_WpHG_63": {"title": "General behavioural obligations", "severity": "critical", "penalty": "EUR 5,000,000", "keywords": ["guaranteed profit", "no risk investment", "kein risiko"]}})
AMF_ENGINE   = _StubEngine("AMF",   {"AMF_RG_533_13": {"title": "Fair treatment of clients", "severity": "critical", "penalty": "EUR 100,000,000", "keywords": ["guaranteed return", "rendement garanti", "sans risque"]}})
SEC_ENGINE   = _StubEngine("SEC",   {"SEC_10B5_1": {"title": "Rule 10b-5 fraud prohibition", "severity": "critical", "penalty": "USD 5,000,000", "keywords": ["insider tip", "guaranteed stock gain", "certain to rise", "100% profit"]}})
FINRA_ENGINE = _StubEngine("FINRA", {"FINRA_2010": {"title": "Standards of commercial honor", "severity": "critical", "penalty": "USD 1,000,000", "keywords": ["guaranteed return", "cant lose", "100% safe investment"]}})
FDA_ENGINE   = _StubEngine("FDA",   {"FDA_SAMD_1": {"title": "Software as Medical Device", "severity": "critical", "penalty": "USD 1,900,000", "keywords": ["diagnose cancer", "definitive diagnosis", "100% accurate diagnosis", "certain disease"]}})

# ── UNIVERSAL REGULATORY DB ───────────────────────────────────
_REG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "all_regulators.json")
try:
    with open(_REG_PATH, encoding="utf-8") as _f:
        _REG_DB = json.load(_f)
    REG_DB_OK = True
except Exception:
    _REG_DB = {}
    REG_DB_OK = False

# ── SHIELD ────────────────────────────────────────────────────
try:
    from umeqam_shield_internal import analyze as _shield_analyze
    SHIELD_OK = True
except Exception:
    SHIELD_OK = False

# ── UNIFIED MODULE (R-ME + Signal Stack + Engine + Logic Core + R-Method) ──
try:
    from umeqam_unified import full_pipeline as _unified_pipeline
    UNIFIED_OK = True
except Exception:
    UNIFIED_OK = False

def _run_shield(prompt, response, domain="general", t0=None, t1=None):
    if not SHIELD_OK:
        return None
    try:
        return _shield_analyze(prompt=prompt, response=response, domain=domain,
                               start_time=t0, end_time=t1)
    except Exception:
        return None

# ── GPT-4o CLIENT ─────────────────────────────────────────────
try:
    from openai import OpenAI
    _ok = os.getenv("OPENAI_API_KEY")
    gpt_client = OpenAI(api_key=_ok) if _ok else None
    GPT_OK = gpt_client is not None
except Exception:
    gpt_client = None
    GPT_OK = False

# ── DEEPSEEK CLIENT ───────────────────────────────────────────
try:
    from openai import OpenAI as _DS
    _dk = os.getenv("DEEPSEEK_API_KEY")
    ds_client = _DS(api_key=_dk, base_url="https://api.deepseek.com") if _dk else None
    DS_OK = ds_client is not None
except Exception:
    ds_client = None
    DS_OK = False

# ── COMPLIANCE MODULES ────────────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
for p in [BASE, os.path.join(BASE, "domains"), os.path.join(BASE, "core")]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from umeqam_medical import MedicalJudgeCouncil
    MEDICAL_OK = True
except ImportError:
    MEDICAL_OK = False

try:
    from umeqam_legal import LegalJudgeCouncil
    LEGAL_OK = True
except ImportError:
    LEGAL_OK = False

try:
    from umeqam_finance import FinanceJudgeCouncil
    FINANCE_OK = True
except ImportError:
    FINANCE_OK = False

try:
    from umeqam_mental import MentalJudgeCouncil
    MENTAL_OK = True
except ImportError:
    MENTAL_OK = False

# ── AUTH ──────────────────────────────────────────────────────
API_KEYS = {
    "umeqam-dev-key-001":  "developer",
    "umeqam-demo-key-002": "demo",
    "umeqam-admin-secret-2026": "admin",
}
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(API_KEY_HEADER)):
    if not api_key or api_key not in API_KEYS:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key

# ── JUDGES ────────────────────────────────────────────────────
SYSTEM_PROMPT = "Answer in English only. Be concise and direct."

def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())

def _word_overlap(a: str, b: str) -> float:
    wa = set(_normalize(a).split())
    wb = set(_normalize(b).split())
    if not wa and not wb: return 1.0
    if not wa or not wb:  return 0.0
    return len(wa & wb) / len(wa | wb)

def _avg_overlap(answers: dict) -> float:
    vals = [v for v in answers.values() if not v.startswith("[")]
    if len(vals) < 2: return 0.0
    scores = []
    for i in range(len(vals)):
        for j in range(i + 1, len(vals)):
            scores.append(_word_overlap(vals[i], vals[j]))
    return sum(scores) / len(scores)

HEDGE_WORDS = ["maybe", "perhaps", "possibly", "might", "unclear", "uncertain",
               "not sure", "i think", "i believe", "probably", "could be",
               "can't predict", "cannot predict", "hard to say", "difficult to say",
               "speculative", "inherently uncertain", "no way to know",
               "impossible to predict", "i cannot", "i can't", "it's unclear"]
AUTHORITY_PATTERNS = ["everyone knows", "it is known", "obviously", "clearly", "of course"]
RECENCY_PATTERNS   = ["recently", "just", "latest", "current", "now", "as of",
                      "as of my last", "last update", "knowledge cutoff", "my knowledge"]
CUTOFF_PATTERNS    = ["as of my last", "my knowledge cutoff", "last update", "last knowledge",
                      "as of october", "as of 2023", "as of 2024", "may be outdated",
                      "verify with", "check a reliable", "more recent information"]
JUDGE_WEIGHTS = {
    "FALSE_CONSENSUS_OUTDATED":  3.0,
    "false_consensus":           2.0,
    "cutoff_detected":           2.0,
    "self_contradiction":        1.5,
    "authority_bias":            1.0,
    "hedging":                   0.5,
    "strong_logical_divergence": 0.3,
    "length_anomaly":            0.2,
}

class FactualJudge:
    def evaluate(self, question, answers):
        alarms = []
        vals = [v for v in answers.values() if not v.startswith("[")]
        if len(vals) < 2:
            return {"judge": "FactualJudge", "alarms": ["insufficient_models"], "similarity": 0.0}
        similarity = _avg_overlap(answers)
        if similarity > 0.85:
            alarms.append(f"semantic_agreement (similarity={similarity:.2f})")
        negations = [bool(re.search(r"\bnot\b|\bno\b", v, re.I)) for v in vals]
        if len(set(negations)) > 1:
            alarms.append("self_contradiction")
        return {"judge": "FactualJudge", "alarms": alarms, "similarity": round(similarity, 3)}

class LogicalJudge:
    def evaluate(self, question, answers):
        alarms = []
        similarity = _avg_overlap(answers)
        if similarity < 0.15:
            alarms.append(f"strong_logical_divergence (similarity={similarity:.2f})")
        elif similarity < 0.35:
            alarms.append(f"mild_logical_divergence (similarity={similarity:.2f})")
        return {"judge": "LogicalJudge", "alarms": alarms}

class AnthropologicalJudge:
    def evaluate(self, question, answers):
        alarms = []
        text = " ".join(answers.values()).lower()
        q = question.lower()
        for p in AUTHORITY_PATTERNS:
            if p in text or p in q:
                alarms.append(f"authority_bias ({p!r})")
                break
        for p in RECENCY_PATTERNS:
            if p in text:
                alarms.append(f"recency_bias ({p!r})")
                break
        hedge_hits = [w for w in HEDGE_WORDS if w in text]
        if hedge_hits:
            alarms.append(f"hedging ({', '.join(hedge_hits[:3])})")
        cutoff_hits = [p for p in CUTOFF_PATTERNS if p in text]
        if cutoff_hits:
            alarms.append(f"cutoff_detected ({cutoff_hits[0]!r})")
        return {"judge": "AnthropologicalJudge", "alarms": alarms}

class AlienJudge:
    def evaluate(self, question, answers):
        alarms = []
        vals = [v for v in answers.values() if not v.startswith("[")]
        if not vals:
            return {"judge": "AlienJudge", "alarms": []}
        lengths = [len(v) for v in vals]
        diff = max(lengths) - min(lengths)
        if diff > 300:
            alarms.append(f"length_anomaly (diff={diff})")
        elif diff > 150:
            alarms.append(f"mild_length_anomaly (diff={diff})")
        if len(question) > 40 and all(ll < 20 for ll in lengths):
            alarms.append("all_answers_too_short")
        return {"judge": "AlienJudge", "alarms": alarms}

class FalseConsensusJudge:
    def evaluate(self, question, answers):
        alarms = []
        similarity = _avg_overlap(answers)
        text = " ".join(answers.values()).lower()
        hedge_hits  = [w for w in HEDGE_WORDS if w in text]
        cutoff_hits = [p for p in CUTOFF_PATTERNS if p in text]
        both_short  = all(len(v) < 30 for v in answers.values())
        if cutoff_hits and similarity > 0.4:
            alarms.append(f"FALSE_CONSENSUS_OUTDATED (sim={similarity:.2f}, cutoff={cutoff_hits[0]!r})")
        elif similarity > 0.5:
            if hedge_hits:
                alarms.append(f"false_consensus_uncertain (sim={similarity:.2f})")
            elif both_short:
                alarms.append(f"false_consensus_short (sim={similarity:.2f})")
            else:
                alarms.append(f"possible_false_consensus (sim={similarity:.2f})")
        return {"judge": "FalseConsensusJudge", "alarms": alarms, "similarity": round(similarity, 3)}

class JudgeCouncil:
    def __init__(self):
        self.judges = [FactualJudge(), LogicalJudge(), AnthropologicalJudge(),
                       AlienJudge(), FalseConsensusJudge()]
    def evaluate(self, question, answers):
        return [j.evaluate(question, answers) for j in self.judges]

def compute_risk(answers: dict, judge_results: list) -> float:
    vals = [v for v in answers.values() if not v.startswith("[")]
    lengths = [len(v) for v in vals] if vals else [0]
    diff = max(lengths) - min(lengths) if len(lengths) > 1 else 0
    model_disagreement = 1.0 if len(set(vals)) > 1 else 0.0
    length_penalty = min(diff * 0.005, 1.0)
    judge_score = 0.0
    for jr in judge_results:
        for alarm in jr.get("alarms", []):
            for key, weight in JUDGE_WEIGHTS.items():
                if key in alarm:
                    judge_score += weight
                    break
    return round(model_disagreement + length_penalty + judge_score, 3)

# ── MODEL CALLS WITH SHIELD ───────────────────────────────────
def call_gpt(question: str) -> str:
    if not GPT_OK:
        return "[GPT-4o: OPENAI_API_KEY not set]"
    try:
        t0 = time.time()
        resp = gpt_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": question},
            ],
            max_tokens=800,
            temperature=0.3,
        )
        t1 = time.time()
        result = resp.choices[0].message.content.strip()
        s = _run_shield(question, result, "general", t0, t1)
        if s:
            if s["verdict"] == "BLOCKED":
                return "[SHIELD BLOCKED] audit_id=" + s["audit_id"] + " flags=" + str(s["flags"])
            elif s["verdict"] == "SUSPICIOUS":
                result += " [SHIELD:SUSPICIOUS risk=" + str(s["risk_score"]) + " audit_id=" + s["audit_id"] + "]"
        return result
    except Exception as e:
        return f"[GPT-4o error: {e}]"

def call_deepseek(question: str) -> str:
    if not DS_OK:
        return "[DeepSeek: DEEPSEEK_API_KEY not set]"
    try:
        t0 = time.time()
        resp = ds_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": question},
            ],
            max_tokens=800,
            temperature=0.3,
        )
        t1 = time.time()
        result = resp.choices[0].message.content.strip()
        s = _run_shield(question, result, "general", t0, t1)
        if s:
            if s["verdict"] == "BLOCKED":
                return "[SHIELD BLOCKED] audit_id=" + s["audit_id"] + " flags=" + str(s["flags"])
            elif s["verdict"] == "SUSPICIOUS":
                result += " [SHIELD:SUSPICIOUS risk=" + str(s["risk_score"]) + " audit_id=" + s["audit_id"] + "]"
        return result
    except Exception as e:
        return f"[DeepSeek error: {e}]"

# ── FASTAPI ───────────────────────────────────────────────────
app = FastAPI(
    title="UMEQAM API",
    description="GPT-4o + DeepSeek · 5 Judges · Risk Score · Shield · 53 Regulators",
    version="2.5.7",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── SCHEMAS ───────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str = Field(..., example="Who is the current president of the USA?")

class ComplianceRequest(BaseModel):
    content: str = Field(..., example="Patient should take 500mg aspirin daily.")
    context: Optional[str] = None
    jurisdiction: Optional[str] = Field(default="EU")
    strict_mode: Optional[bool] = Field(default=True)
    answers: Optional[Dict[str, str]] = None

class UniversalRegRequest(BaseModel):
    content: str = Field(..., example="Patient data shared without consent")
    framework: str = Field(..., example="HIPAA")
    jurisdiction: Optional[str] = Field(default=None)

# ── HELPERS ───────────────────────────────────────────────────
def _build_answers(req: ComplianceRequest) -> dict:
    return req.answers if req.answers else {"input": req.content}

def _fmt(raw: dict, layer: str, latency: float) -> dict:
    if "judge_results" in raw:
        passed  = sum(1 for jr in raw["judge_results"] if not jr.get("alarms"))
        total   = len(raw["judge_results"])
        score   = round(passed / max(total, 1), 3)
        rec     = raw.get("recommendation", "")
        verdict = "FAIL" if "BLOCK" in rec else "REVIEW" if "REVIEW" in rec else "PASS"
        judges  = []
        for i, jr in enumerate(raw["judge_results"]):
            alarms = jr.get("alarms", [])
            v = "PASS" if not alarms else ("FAIL" if len(alarms) >= 2 else "REVIEW")
            judges.append({"judge_id": i+1, "name": jr.get("judge", f"Judge_{i+1}"),
                           "verdict": v, "confidence": round(0.90 - len(alarms)*0.1, 3),
                           "alarms": alarms})
        return {"request_id": str(uuid.uuid4()), "layer": layer,
                "overall_verdict": verdict, "compliance_score": score,
                "judges_passed": passed, "judges_total": total, "judges": judges,
                "flags": raw.get("critical_alarms", []), "recommendation": rec,
                "timestamp": datetime.utcnow().isoformat()+"Z",
                "latency_ms": latency, "engine": "real"}
    return {"request_id": str(uuid.uuid4()), "layer": layer,
            "overall_verdict": raw.get("overall_verdict", "REVIEW"),
            "compliance_score": raw.get("compliance_score", 0.5),
            "judges_passed": raw.get("judges_passed", 0),
            "judges_total": raw.get("judges_total", 8),
            "judges": [], "flags": raw.get("flags", ["stub_mode"]),
            "recommendation": "stub - real module not loaded",
            "timestamp": datetime.utcnow().isoformat()+"Z",
            "latency_ms": latency, "engine": "stub"}

def _fmt_reg(result, framework, latency_ms):
    return {"verdict": result.get("verdict", "REVIEW"),
            "risk_score": result.get("risk_score", 50),
            "violations": result.get("violations", []),
            "framework": framework,
            "engine": result.get("engine", framework),
            "audit_id": result.get("audit_id", "umeqam_" + uuid.uuid4().hex[:8]),
            "latency_ms": latency_ms,
            "version": "2.5.7"}

# ── LLM JUDGES ────────────────────────────────────────────────
try:
    from umeqam_llm_judges import llm_judge_ensemble
    LLM_JUDGES = True
except Exception:
    LLM_JUDGES = False

async def run_with_llm_judge(content, domain, keyword_result, latency):
    if not LLM_JUDGES:
        return keyword_result
    import asyncio
    loop = asyncio.get_event_loop()
    try:
        llm_result = await loop.run_in_executor(None, llm_judge_ensemble, content, domain)
        kw_verdict = keyword_result.get("overall_verdict", "PASS")
        llm_verdict = llm_result["final_verdict"]
        final_verdict = "REVIEW" if kw_verdict == "FAIL" and llm_verdict == "PASS" else llm_verdict
        score_map = {"PASS": 0.9, "REVIEW": 0.5, "FAIL": 0.1}
        keyword_result["overall_verdict"] = final_verdict
        keyword_result["compliance_score"] = score_map.get(final_verdict, 0.5)
        keyword_result["llm_verdict"] = llm_verdict
        keyword_result["llm_confidence"] = llm_result["confidence"]
        keyword_result["llm_judges"] = [{"model": j["judge"], "verdict": j["verdict"],
                                          "reason": j.get("reason","")[:100]}
                                         for j in llm_result["judges"]]
        keyword_result["engine"] = "llm_ensemble"
        keyword_result["latency_ms"] = latency
    except Exception as e:
        keyword_result["llm_error"] = str(e)[:100]
    return keyword_result

# ── ROUTES ────────────────────────────────────────────────────

@app.get("/v1/health", tags=["System"])
async def health():
    return {
        "status": "operational",
        "version": "2.5.7",
        "models": {
            "gpt-4o":   "ready" if GPT_OK else "NO KEY - set OPENAI_API_KEY",
            "deepseek": "ready" if DS_OK  else "NO KEY - set DEEPSEEK_API_KEY",
        },
        "shield": "active" if SHIELD_OK else "inactive",
        "unified_pipeline": "active" if UNIFIED_OK else "inactive",
        "regulatory_db": f"{len(_REG_DB)} frameworks" if REG_DB_OK else "not loaded",
        "layers": {
            "medical": "real" if MEDICAL_OK else "stub",
            "legal":   "real" if LEGAL_OK   else "stub",
            "finance": "real" if FINANCE_OK  else "stub",
            "mental":  "real" if MENTAL_OK   else "stub",
        },
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "env_openai":   bool(os.getenv("OPENAI_API_KEY")),
        "env_deepseek": bool(os.getenv("DEEPSEEK_API_KEY")),
    }

@app.post("/v1/ask", tags=["Core"], dependencies=[Depends(verify_api_key)])
async def ask(req: AskRequest):
    t0 = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        f_gpt = ex.submit(call_gpt, req.question)
        f_ds  = ex.submit(call_deepseek, req.question)
        gpt_ans = f_gpt.result()
        ds_ans  = f_ds.result()
    answers = {"gpt-4o": gpt_ans, "deepseek": ds_ans}
    council = JudgeCouncil()
    judge_results = council.evaluate(req.question, answers)
    risk_score = compute_risk(answers, judge_results)
    unified = None
    if UNIFIED_OK:
        try:
            best_answer = gpt_ans if not gpt_ans.startswith("[") else ds_ans
            unified = _unified_pipeline(req.question, best_answer)
        except Exception:
            unified = None
    return {
        "request_id":    str(uuid.uuid4()),
        "question":      req.question,
        "answers":       answers,
        "risk_score":    risk_score,
        "judge_results": judge_results,
        "unified":       unified,
        "latency_ms":    round((time.perf_counter() - t0) * 1000, 1),
        "timestamp":     datetime.utcnow().isoformat() + "Z",
    }

@app.post("/v1/medical/analyze", tags=["Medical"], dependencies=[Depends(verify_api_key)])
async def medical_analyze(req: ComplianceRequest):
    t0 = time.perf_counter()
    raw = MedicalJudgeCouncil().evaluate(req.content, _build_answers(req)) if MEDICAL_OK else {"overall_verdict": "REVIEW", "compliance_score": 0.5, "judges_passed": 4, "judges_total": 8, "flags": ["stub_mode"]}
    result = _fmt(raw, "medical", round((time.perf_counter() - t0) * 1000, 3))
    return await run_with_llm_judge(req.content, "medical", result, round((time.perf_counter() - t0) * 1000, 3))

@app.post("/v1/legal/analyze", tags=["Legal"], dependencies=[Depends(verify_api_key)])
async def legal_analyze(req: ComplianceRequest):
    t0 = time.perf_counter()
    raw = LegalJudgeCouncil().evaluate(req.content, _build_answers(req)) if LEGAL_OK else {"overall_verdict": "REVIEW", "compliance_score": 0.5, "judges_passed": 4, "judges_total": 8, "flags": ["stub_mode"]}
    result = _fmt(raw, "legal", round((time.perf_counter() - t0) * 1000, 3))
    return await run_with_llm_judge(req.content, "legal", result, round((time.perf_counter() - t0) * 1000, 3))

@app.post("/v1/finance/analyze", tags=["Finance"], dependencies=[Depends(verify_api_key)])
async def finance_analyze(req: ComplianceRequest):
    t0 = time.perf_counter()
    raw = FinanceJudgeCouncil().evaluate(req.content, _build_answers(req)) if FINANCE_OK else {"overall_verdict": "REVIEW", "compliance_score": 0.5, "judges_passed": 4, "judges_total": 8, "flags": ["stub_mode"]}
    result = _fmt(raw, "finance", round((time.perf_counter() - t0) * 1000, 3))
    return await run_with_llm_judge(req.content, "finance", result, round((time.perf_counter() - t0) * 1000, 3))

@app.post("/v1/mental/analyze", tags=["Mental Health"], dependencies=[Depends(verify_api_key)])
async def mental_analyze(req: ComplianceRequest):
    t0 = time.perf_counter()
    raw = MentalJudgeCouncil().evaluate(req.content, _build_answers(req)) if MENTAL_OK else {"overall_verdict": "REVIEW", "compliance_score": 0.5, "judges_passed": 4, "judges_total": 8, "flags": ["stub_mode"]}
    result = _fmt(raw, "mental", round((time.perf_counter() - t0) * 1000, 3))
    return await run_with_llm_judge(req.content, "mental", result, round((time.perf_counter() - t0) * 1000, 3))

# ── REGULATORY ENDPOINTS ──────────────────────────────────────

@app.post("/v1/gdpr/analyze", tags=["Regulatory"], dependencies=[Depends(verify_api_key)])
async def gdpr_analyze(req: ComplianceRequest):
    t0 = time.perf_counter()
    if GDPR_OK:
        raw = GDPRComplianceEngine().analyze(req.content)
        result = {"verdict": getattr(raw,"verdict","REVIEW"), "risk_score": int(getattr(raw,"risk_score",0.5)*100), "violations": [{"rule_id":v.rule_id,"title":getattr(v,"rule_title",getattr(v,"title",str(v))),"severity":v.severity} for v in getattr(raw,"violations",[])], "engine":"gdpr_v1"}
    else:
        result = {"verdict":"REVIEW","risk_score":50,"violations":[],"engine":"stub"}
    return _fmt_reg(result, "GDPR", round((time.perf_counter()-t0)*1000,3))

@app.post("/v1/hipaa/analyze", tags=["Regulatory"], dependencies=[Depends(verify_api_key)])
async def hipaa_analyze(req: ComplianceRequest):
    t0 = time.perf_counter()
    if HIPAA_OK:
        raw = HIPAAComplianceEngine().analyze(req.content)
        result = {"verdict": getattr(raw,"verdict","REVIEW"), "risk_score": int(getattr(raw,"risk_score",0.5)*100), "violations": [{"rule_id":v.rule_id,"title":getattr(v,"rule_title",getattr(v,"title",str(v))),"severity":v.severity} for v in getattr(raw,"violations",[])], "engine":"hipaa_v1"}
    else:
        result = {"verdict":"REVIEW","risk_score":50,"violations":[],"engine":"stub"}
    return _fmt_reg(result, "HIPAA", round((time.perf_counter()-t0)*1000,3))

@app.post("/v1/eu_ai_act/analyze", tags=["Regulatory"], dependencies=[Depends(verify_api_key)])
async def eu_ai_act_analyze(req: ComplianceRequest):
    t0 = time.perf_counter()
    if EUAIACT_OK:
        raw = EUAIActComplianceEngine().analyze(req.content)
        result = {"verdict": getattr(raw,"verdict","REVIEW"), "risk_score": int(getattr(raw,"risk_score",0.5)*100), "violations": [{"rule_id":v.rule_id,"title":getattr(v,"rule_title",getattr(v,"title",str(v))),"severity":v.severity} for v in getattr(raw,"violations",[])], "engine":"eu_ai_act_v1"}
    else:
        result = {"verdict":"REVIEW","risk_score":50,"violations":[],"engine":"stub"}
    return _fmt_reg(result, "EU_AI_Act", round((time.perf_counter()-t0)*1000,3))

@app.post("/v1/fca/analyze",   tags=["Regulatory"], dependencies=[Depends(verify_api_key)])
async def fca_analyze(req: ComplianceRequest):
    t0 = time.perf_counter()
    return _fmt_reg(FCA_ENGINE.analyze(req.content), "FCA", round((time.perf_counter()-t0)*1000,3))

@app.post("/v1/bafin/analyze", tags=["Regulatory"], dependencies=[Depends(verify_api_key)])
async def bafin_analyze(req: ComplianceRequest):
    t0 = time.perf_counter()
    return _fmt_reg(BAFIN_ENGINE.analyze(req.content), "BaFin", round((time.perf_counter()-t0)*1000,3))

@app.post("/v1/amf/analyze",   tags=["Regulatory"], dependencies=[Depends(verify_api_key)])
async def amf_analyze(req: ComplianceRequest):
    t0 = time.perf_counter()
    return _fmt_reg(AMF_ENGINE.analyze(req.content), "AMF", round((time.perf_counter()-t0)*1000,3))

@app.post("/v1/sec/analyze",   tags=["Regulatory"], dependencies=[Depends(verify_api_key)])
async def sec_analyze(req: ComplianceRequest):
    t0 = time.perf_counter()
    return _fmt_reg(SEC_ENGINE.analyze(req.content), "SEC", round((time.perf_counter()-t0)*1000,3))

@app.post("/v1/finra/analyze", tags=["Regulatory"], dependencies=[Depends(verify_api_key)])
async def finra_analyze(req: ComplianceRequest):
    t0 = time.perf_counter()
    return _fmt_reg(FINRA_ENGINE.analyze(req.content), "FINRA", round((time.perf_counter()-t0)*1000,3))

@app.post("/v1/fda/analyze",   tags=["Regulatory"], dependencies=[Depends(verify_api_key)])
async def fda_analyze(req: ComplianceRequest):
    t0 = time.perf_counter()
    return _fmt_reg(FDA_ENGINE.analyze(req.content), "FDA", round((time.perf_counter()-t0)*1000,3))

# ── UNIVERSAL REGULATORY (53 frameworks) ─────────────────────

@app.post("/v1/regulatory/analyze", tags=["Regulatory"], dependencies=[Depends(verify_api_key)])
async def universal_regulatory_analyze(req: UniversalRegRequest):
    t0 = time.perf_counter()
    key = req.framework.lower().replace(" ", "_").replace("-", "_")
    reg = _REG_DB.get(key)
    if not reg:
        for k, v in _REG_DB.items():
            if req.framework.lower() in k or k in req.framework.lower():
                reg = v
                break
    if not reg:
        raise HTTPException(status_code=404, detail=f"Framework '{req.framework}' not found. DB has {len(_REG_DB)} frameworks.")
    violations = []
    for trigger in reg.get("ai_output_triggers", []):
        if any(w in req.content.lower() for w in trigger.lower().split() if len(w) > 4):
            violations.append({"rule_id": key.upper()+"_TRIGGER", "title": trigger, "severity": "high"})
    checklist = reg.get("compliance_checklist", [])
    passed = sum(1 for item in checklist if any(w in req.content.lower() for w in item.replace("_"," ").split() if len(w) > 3))
    risk = min(len(violations)*0.25 + (1 - passed/max(len(checklist),1))*0.2, 1.0)
    verdict = "FAIL" if risk >= 0.5 else ("REVIEW" if risk > 0 else "PASS")
    pen = reg.get("penalty_structure", {})
    max_fine = max(pen.get("max_fine_eur", 0), pen.get("max_fine_usd", 0))
    return {
        "verdict":               verdict,
        "risk_score":            round(risk * 100),
        "framework":             reg.get("name", req.framework),
        "jurisdiction":          reg.get("jurisdiction", ""),
        "violations":            violations,
        "relevant_articles":     [a["article"]+": "+a["title"] for a in reg.get("key_articles",[]) if a.get("ai_relevance")=="HIGH"][:3],
        "max_penalty_exposure":  max_fine,
        "penalty_currency":      "EUR" if pen.get("max_fine_eur",0) >= pen.get("max_fine_usd",0) else "USD",
        "defensibility_factors": reg.get("defensibility_factors",[])[:3],
        "compliance_checklist":  checklist,
        "audit_id":              "umeqam_" + uuid.uuid4().hex[:8],
        "latency_ms":            round((time.perf_counter()-t0)*1000, 3),
        "version":               "2.5.7",
    }

@app.get("/v1/regulatory/frameworks", tags=["Regulatory"])
async def list_frameworks():
    return {
        "frameworks": [{"key": k, "name": v.get("name"), "jurisdiction": v.get("jurisdiction"), "domain": v.get("domain"), "max_fine_eur": v.get("penalty_structure",{}).get("max_fine_eur",0), "max_fine_usd": v.get("penalty_structure",{}).get("max_fine_usd",0)} for k, v in _REG_DB.items()],
        "count": len(_REG_DB),
    }


# ── COMPLIANCE CHECK ─────────────────────────────────────────
import numpy as _np
from typing import List as _List

_HEDGE = {"may","might","could","possibly","perhaps","sometimes","often","usually","generally","probably","likely","appears","seems","suggests"}
_ASSERT = {"is","are","was","were","always","never","definitely","certainly","must","will","proven","fact"}
_DANGER = {"kill","harm","suicide","weapon","illegal","fraud","manipulate","exploit"}

class ComplianceRequest(BaseModel):
    answer: str
    knowledge: str = ""
    domain: str = "general"

@app.post("/v1/compliance_check")
async def compliance_check(req: ComplianceRequest):
    import uuid
    words = req.answer.lower().split()
    n = len(words)
    if n < 3:
        a1 = 0.5
    else:
        unique_ratio = len(set(words)) / n
        hedge_ratio = sum(1 for w in words if w in _HEDGE) / n
        assert_ratio = sum(1 for w in words if w in _ASSERT) / n
        bigrams = list(zip(words[:-1], words[1:]))
        bigram_repeat = 1-(len(set(bigrams))/(len(bigrams)+1e-9))
        overlap = len(set(words) & set(req.knowledge.lower().split()))/(len(set(words))+1e-9) if req.knowledge else 0.5
        score = float(_np.mean([1-unique_ratio, _np.clip(assert_ratio*10,0,1), _np.clip(1-hedge_ratio*20,0,1), _np.clip(bigram_repeat*5,0,1), _np.clip(1-overlap*2,0,1)]))
        a1 = 1 - score
    danger_count = sum(1 for w in words if w in _DANGER)
    a2 = 0.0 if danger_count > 0 else 1.0
    a3 = 1.0
    if req.domain == "finance" and any(f in req.answer.lower() for f in ["guaranteed return","no risk","100% profit"]):
        a3 = 0.0
    if req.domain == "medical" and any(f in req.answer.lower() for f in ["cure","guaranteed","no side effects"]):
        a3 = 0.0
    a4 = 1.0 if len(req.answer) > 10 else 0.0
    final_score = round(float(_np.mean([a1, a2, a3, a4])), 4)
    passed = a1 > 0.4 and a2 == 1.0 and a3 == 1.0 and a4 == 1.0
    failed_atoms = []
    if a1 <= 0.4: failed_atoms.append("CONFIDENCE")
    if a2 < 1.0: failed_atoms.append("SAFETY")
    if a3 < 1.0: failed_atoms.append("REGULATORY")
    if a4 < 1.0: failed_atoms.append("TRACEABILITY")
    return {"decision": "PASS" if passed else "FAIL", "score": final_score, "failed_atoms": failed_atoms, "audit_id": str(uuid.uuid4()), "atoms": {"confidence": round(a1,4), "safety": round(a2,4), "regulatory": round(a3,4), "traceability": round(a4,4)}}

# ── RUN ───────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)


# ── REGULATORY CHECK V2 ──
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime

class RegulatoryCheckRequest(BaseModel):
    text: str
    regulators: Optional[List[str]] = None

class RegulatoryCheckResponse(BaseModel):
    text_evaluated: str
    results: Dict
    timestamp: str
    verdict_summary: str

@app.post("/v1/regulatory-check-v2", tags=["Regulatory"], response_model=RegulatoryCheckResponse, dependencies=[Depends(verify_api_key)])
async def regulatory_check_v2(req: RegulatoryCheckRequest):
    results = evaluate_all_regulators(req.text)
    blocked = [r for r, v in results.items() if v.get("verdict") == "BLOCK"]
    review = [r for r, v in results.items() if v.get("verdict") == "REVIEW"]
    parts = []
    if blocked:
        parts.append(f"BLOCKED by: {', '.join(blocked)}")
    if review:
        parts.append(f"REVIEW: {', '.join(review)}")
    summary = " | ".join(parts) if parts else "PASS (all regulators)"
    return RegulatoryCheckResponse(
        text_evaluated=req.text,
        results=results,
        timestamp=datetime.utcnow().isoformat() + "Z",
        verdict_summary=summary,
    )


# -- MIFID II ENDPOINT --
class MiFIDRequest(BaseModel):
    text: str
    jurisdiction: str = "EU"

@app.post("/v1/mifid/analyze", tags=["Regulatory"], dependencies=[Depends(verify_api_key)])
async def mifid_analyze(req: MiFIDRequest):
    engine = MiFIDComplianceEngine()
    result = engine.analyze(req.text, jurisdiction=req.jurisdiction)
    return engine.to_dict(result)

