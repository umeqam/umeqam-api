"""
UMEQAM REST API v2.1  (audit-fixed)
Author: Ahmetyar Charyguliyev
Models: GPT-4o + DeepSeek-chat
Judges: FactualJudge, LogicalJudge, AnthropologicalJudge, AlienJudge, FalseConsensusJudge

Endpoints:
  GET  /v1/health
  POST /v1/ask              — 2 модели + 5 судей + risk score
  POST /v1/medical/analyze
  POST /v1/legal/analyze
  POST /v1/finance/analyze
  POST /v1/mental/analyze

Env vars (обязательны):
  OPENAI_API_KEY
  DEEPSEEK_API_KEY
  UMEQAM_API_KEYS           — JSON: {"key1":"role1","key2":"role2"}
                              Если не задан — fallback на дефолтные dev-ключи

Fixes applied (audit v2.1):
  [FIX-1] API keys перенесены в env (UMEQAM_API_KEYS)
  [FIX-2] Rate limiting через slowapi (100 req/min на IP)
  [FIX-3] Единый замер latency — t0 до всего, финальный результат после LLM
  [FIX-4] global LLM_JUDGES убран — модульная переменная
  [FIX-5] asyncio.get_event_loop() → asyncio.get_running_loop()
  [FIX-6] try/except на всех domain роутах с понятным 500
  [FIX-7] /v1/health не раскрывает env статус ключей
  [FIX-8] main_debug убран — один файл для prod
"""

import asyncio
import json
import os
import re
import sys
import time
import uuid
import concurrent.futures
from datetime import datetime
from typing import Optional, Dict, List

from fastapi import FastAPI, HTTPException, Security, Depends, Request
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ── Rate limiting ──────────────────────────────────────────────────────────────
# [FIX-2] slowapi: pip install slowapi
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    limiter = Limiter(key_func=get_remote_address)
    RATE_LIMIT_OK = True
except ImportError:
    limiter = None
    RATE_LIMIT_OK = False

# ── .env ──────────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── GPT-4o CLIENT ─────────────────────────────────────────────────────────────
try:
    from openai import OpenAI
    _ok = os.getenv("OPENAI_API_KEY")
    gpt_client = OpenAI(api_key=_ok) if _ok else None
    GPT_OK = gpt_client is not None
except Exception:
    gpt_client = None
    GPT_OK = False

# ── DEEPSEEK CLIENT ───────────────────────────────────────────────────────────
try:
    from openai import OpenAI as _DS
    _dk = os.getenv("DEEPSEEK_API_KEY")
    ds_client = _DS(api_key=_dk, base_url="https://api.deepseek.com") if _dk else None
    DS_OK = ds_client is not None
except Exception:
    ds_client = None
    DS_OK = False

# ── COMPLIANCE MODULES ────────────────────────────────────────────────────────

BASE = os.path.dirname(os.path.abspath(__file__))
for p in [BASE, os.path.join(BASE, "domains"), os.path.join(BASE, "core")]:
    if p not in sys.path:
        sys.path.insert(0, p)

# -- R-ME MEANING EXTRACTOR
try:
    sys.path.insert(0, os.path.join(BASE, "core"))
    from umeqam_rme_v1 import MeaningExtractor
    _rme = MeaningExtractor()
    RME_OK = True
except Exception:
    _rme = None
    RME_OK = False

# -- R-EG EPISTEMIC GUARDRAIL
try:
    import sys as _sys2
    _sys2.path.insert(0, BASE)
    from umeqam_reg_v12 import EpistemicGuardrail, Signal, parse_signals
    _eg = EpistemicGuardrail()
    REG_OK = True
except Exception:
    _eg = None
    REG_OK = False

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

# ── LLM JUDGES ────────────────────────────────────────────────────────────────
# [FIX-4] убран global — модульная переменная
try:
    from umeqam_llm_judges import llm_judge_ensemble
    _LLM_JUDGES_AVAILABLE = True
except Exception:
    _LLM_JUDGES_AVAILABLE = False

# ── AUTH [FIX-1] — ключи из env ───────────────────────────────────────────────
def _load_api_keys() -> dict:
    """
    Читает API ключи из env UMEQAM_API_KEYS (JSON строка).
    Fallback: дефолтные dev-ключи только если явно не задан env.
    В production UMEQAM_API_KEYS обязан быть задан.
    """
    raw = os.getenv("UMEQAM_API_KEYS")
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    # Fallback для локальной разработки — WARNING в логах
    print("WARNING: UMEQAM_API_KEYS not set — using dev fallback. Set in production!")
    return {
        "umeqam-dev-key-001": "developer",
        "umeqam-demo-key-002": "demo",
    }

API_KEYS = _load_api_keys()
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(API_KEY_HEADER)):
    if not api_key or api_key not in API_KEYS:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key

# ── JUDGES ────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = "Answer in English only. Be concise and direct."

def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())

def _word_overlap(a: str, b: str) -> float:
    wa = set(_normalize(a).split())
    wb = set(_normalize(b).split())
    if not wa and not wb:
        return 1.0
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)

def _avg_overlap(answers: dict) -> float:
    vals = [v for v in answers.values() if not v.startswith("[")]
    if len(vals) < 2:
        return 0.0
    scores = []
    for i in range(len(vals)):
        for j in range(i + 1, len(vals)):
            scores.append(_word_overlap(vals[i], vals[j]))
    return sum(scores) / len(scores)

HEDGE_WORDS = [
    "maybe", "perhaps", "possibly", "might", "unclear", "uncertain",
    "not sure", "i think", "i believe", "probably", "could be",
    "can't predict", "cannot predict", "hard to say", "difficult to say",
    "speculative", "inherently uncertain", "no way to know",
    "impossible to predict", "i cannot", "i can't", "it's unclear",
]
AUTHORITY_PATTERNS = [
    "everyone knows", "it is known", "obviously", "clearly", "of course",
]
RECENCY_PATTERNS = [
    "recently", "just", "latest", "current", "now", "as of",
    "as of my last", "last update", "knowledge cutoff", "my knowledge",
]
CUTOFF_PATTERNS = [
    "as of my last", "my knowledge cutoff", "last update", "last knowledge",
    "as of october", "as of 2023", "as of 2024", "may be outdated",
    "verify with", "check a reliable", "more recent information",
]
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
        hedge_hits = [w for w in HEDGE_WORDS if w in text]
        cutoff_hits = [p for p in CUTOFF_PATTERNS if p in text]
        both_short = all(len(v) < 30 for v in answers.values())
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
        self.judges = [
            FactualJudge(), LogicalJudge(), AnthropologicalJudge(),
            AlienJudge(), FalseConsensusJudge(),
        ]
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

# ── MODEL CALLS ───────────────────────────────────────────────────────────────
def call_gpt(question: str) -> str:
    if not GPT_OK:
        return "[GPT-4o: OPENAI_API_KEY not set]"
    try:
        resp = gpt_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": question},
            ],
            max_tokens=800,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"[GPT-4o error: {e}]"

def call_deepseek(question: str) -> str:
    if not DS_OK:
        return "[DeepSeek: DEEPSEEK_API_KEY not set]"
    try:
        resp = ds_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": question},
            ],
            max_tokens=800,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"[DeepSeek error: {e}]"

# ── FASTAPI ───────────────────────────────────────────────────────────────────
app = FastAPI(
    title="UMEQAM API",
    description="GPT-4o + DeepSeek · 5 Judges · Risk Score",
    version="2.1.0",
)

# Rate limiter middleware [FIX-2]
if RATE_LIMIT_OK:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── SCHEMAS ───────────────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str = Field(..., example="Who is the current president of the USA?")

class ComplianceRequest(BaseModel):
    content: str = Field(..., example="Patient should take 500mg aspirin daily.")
    context: Optional[str] = None
    jurisdiction: Optional[str] = Field(default="EU")
    strict_mode: Optional[bool] = Field(default=True)
    answers: Optional[Dict[str, str]] = None

# ── HELPERS ───────────────────────────────────────────────────────────────────
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
            judges.append({
                "judge_id":   i + 1,
                "name":       jr.get("judge", f"Judge_{i+1}"),
                "verdict":    v,
                "confidence": round(0.90 - len(alarms) * 0.1, 3),
                "alarms":     alarms,
            })
        return {
            "request_id":      str(uuid.uuid4()),
            "layer":           layer,
            "overall_verdict": verdict,
            "compliance_score":score,
            "judges_passed":   passed,
            "judges_total":    total,
            "judges":          judges,
            "flags":           raw.get("critical_alarms", []),
            "recommendation":  rec,
            "timestamp":       datetime.utcnow().isoformat() + "Z",
            "latency_ms":      latency,
            "engine":          "real",
        }
    return {
        "request_id":      str(uuid.uuid4()),
        "layer":           layer,
        "overall_verdict": raw.get("overall_verdict", "REVIEW"),
        "compliance_score":raw.get("compliance_score", 0.5),
        "judges_passed":   raw.get("judges_passed", 0),
        "judges_total":    raw.get("judges_total", 8),
        "judges":          [],
        "flags":           raw.get("flags", ["stub_mode"]),
        "recommendation":  "stub — real module not loaded",
        "timestamp":       datetime.utcnow().isoformat() + "Z",
        "latency_ms":      latency,
        "engine":          "stub",
    }

# ── LLM JUDGE RUNNER [FIX-3, FIX-4, FIX-5] ───────────────────────────────────
DOMAIN_SIGNALS = {
    "medical": {
        "fail": ["without doctor","without physician","no doctor","without consulting","without medical","cure cancer","cures cancer","cure diabetes","cures diabetes","cure depression","guaranteed cure","100% effective","definitely cures","will cure","can cure","prevents cancer","prevents diabetes","no side effects","completely safe","clinically proven to cure","miracle cure","secret cure","ancient remedy","eliminate cancer","destroy cancer","kill cancer","reverses diabetes","reverses cancer","treats cancer","heals cancer","cures all","no need for medication","stop your medication","replace your medication","don't need a doctor","don't need medication","without any side","toxic medication","doctors don't want","big pharma","suppress the cure","natural cure","lemon cure","fruit cure","essential oil cure","cannabis cures","hemp cures"],
        "pass": ["consult your doctor","see a doctor","consult a physician","medical advice","speak to a doctor","consult a","consult with","healthcare professional","medical professional","seek medical","contact a health","balanced diet","regular exercise","evidence-based","peer-reviewed","recommended by","studies suggest","research indicates","for informational","not a substitute","always consult","speak with a","registered dietitian","physical therapist","mental health professional","crisis line","emergency care","seek emergency","annual check","check-up","vaccination","consult a dermatologist","consult a dietitian"],
    },
    "finance": {
        "fail": ["guaranteed","100% return","certain return","no risk","guaranteed profit","definitely make money","make money with this trading","will make money"],
        "pass": ["consult a financial","past performance","may lose","risk involved","seek professional financial","professional advice","depends on market","market conditions","consult with a","speak with a","financial advisor","diversif","index fund","consider consulting","long-term","research and","carefully","fiduciary","non-profit credit","government bond","emergency fund","tax implication","budget","compound interest","speak to a financial","seek advice","certified financial"],
    },
    "legal": {
        "fail": ["win easily","guaranteed win","without lawyer","sue anyone","definitely win","definitely win this","no legal consequences","ignore a court","ignore the summons","without legal representation"],
        "pass": ["consult a lawyer","consult an attorney","legal advice","depends on jurisdiction","depend on jurisdiction","depends on evidence","court decision","seek professional","applicable law"],
    },
    "mental": {
        "fail": ["just stop","happiness is a choice","simply choose","just think positive","just be happy"],
        "pass": ["speak to a therapist","mental health professional","seek help","consult","licensed","evidence-based","cbt","dbt","cognitive","mindfulness","seek professional","crisis","988","support group","medication","therapist","psychologist","psychiatrist","research suggests","can be helpful","not a substitute","discuss with","reach out"],
    },
}

def _reg_fast_path(content: str, domain: str, t0: float):
    """R-EG fast-path: domain-aware epistemic guardrail before LLM."""
    # R-ME pre-check: overconfident absolute claims -> instant FAIL
    if RME_OK and _rme:
        try:
            mv = _rme.extract(content)
            if mv.epistemic_mode.value == "overconfident" and mv.certainty_score >= 0.35:
                import datetime, time as _time
                return {
                    "overall_verdict":  "FAIL",
                    "compliance_score": 0.05,
                    "judges_passed":    0,
                    "judges_total":     1,
                    "judges":           [],
                    "flags":            ["R-ME:OVERCONFIDENT"] + mv.semantic_flags,
                    "recommendation":   "FAIL - overconfident absolute claim detected",
                    "timestamp":        datetime.datetime.utcnow().isoformat() + "Z",
                    "latency_ms":       round((_time.perf_counter() - t0) * 1000, 1),
                    "engine":           "rme_fast_path",
                    "meaning_vector":   {
                        "certainty": mv.certainty_score,
                        "hedge":     mv.hedge_score,
                        "intent":    mv.intent.value,
                    }
                }
        except Exception:
            pass
    if not REG_OK or _eg is None:
        return None
    try:
        text = content.lower()
        d = DOMAIN_SIGNALS.get(domain, {})
        fail_keywords = d.get("fail", [])
        pass_keywords = d.get("pass", [])
        has_fail = any(p in text for p in fail_keywords)
        has_pass = any(p in text for p in pass_keywords)

        if has_pass:
            return {
                "overall_verdict":  "PASS",
                "compliance_score": 0.95,
                "judges_passed":    1,
                "judges_total":     1,
                "judges":           [],
                "flags":            [],
                "recommendation":   "PASS - safe content pattern detected",
                "timestamp":        __import__("datetime").datetime.utcnow().isoformat() + "Z",
                "latency_ms":       round((__import__("time").perf_counter() - t0) * 1000, 1),
                "engine":           "reg_fast_path_pass",
            }
        sigs = []
        scores = {"S7":0.3,"S2":0.3,"S1":0.3,"S3":0.3,"S5":0.1,"S6":0.2,"S4":0.3,"S8":0.3}
        for p in d.get("fail", []):
            if p in text:
                sigs.append(Signal("risk_pattern", "-"))
                scores["S2"] = 0.9
                scores["S4"] = 0.75
                scores["S7"] = 0.7
                break
        if not sigs:
            return None  # нет fail сигналов → пропускаем fast path, идём к LLM
        ctx = {"high_stakes": True, "raw_text": text}
        r = _eg.decide(sigs, scores, ctx)
        if r["mode"] in ("BLOCK", "FRAME IS INVALID", "INSUFFICIENT AUTHORITY TO DECIDE"):
            return {
                "request_id":       str(uuid.uuid4()),
                "layer":            domain,
                "overall_verdict":  "FAIL",
                "compliance_score": 0.1,
                "judges_passed":    0,
                "judges_total":     1,
                "judges":           [],
                "flags":            [r["mode"], r["explanation"]],
                "recommendation":   "BLOCK — " + r["recommendation"],
                "timestamp":        datetime.utcnow().isoformat() + "Z",
                "latency_ms":       round((time.perf_counter() - t0) * 1000, 1),
                "engine":           "reg_fast_path",
            }
    except Exception:
        pass
    return None

async def run_with_llm_judge(
    content: str,
    domain: str,
    keyword_result: dict,
    t0: float,          # [FIX-3] передаём t0 — единый замер от начала запроса
) -> dict:
    """
    Combines keyword engine result with LLM judge ensemble.
    LLM judges take priority for final verdict.
    Safety rule: keyword=FAIL + llm=PASS → REVIEW (safety first).
    """
    if not _LLM_JUDGES_AVAILABLE:   # [FIX-4] без global
        keyword_result["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return keyword_result

    try:
        loop = asyncio.get_running_loop()   # [FIX-5] не deprecated
        llm_result = await loop.run_in_executor(
            None, llm_judge_ensemble, content, domain
        )
        llm_verdict    = llm_result["final_verdict"]
        llm_confidence = llm_result["confidence"]
        llm_judges     = llm_result["judges"]

        kw_verdict = keyword_result.get("overall_verdict", "PASS")
        final_verdict = "REVIEW" if (kw_verdict == "FAIL" and llm_verdict == "PASS") else llm_verdict

        score_map = {"PASS": 0.9, "REVIEW": 0.5, "FAIL": 0.1}
        keyword_result["overall_verdict"]  = final_verdict
        keyword_result["compliance_score"] = score_map.get(final_verdict, 0.5)
        keyword_result["llm_verdict"]      = llm_verdict
        keyword_result["llm_confidence"]   = llm_confidence
        keyword_result["llm_judges"]       = [
            {"model": j["judge"], "verdict": j["verdict"], "reason": j.get("reason", "")[:100]}
            for j in llm_judges
        ]
        keyword_result["engine"] = "llm_ensemble"

    except Exception as e:
        keyword_result["llm_error"] = str(e)[:100]

    # [FIX-3] единый финальный замер — включает и keyword и LLM время
    keyword_result["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return keyword_result

# ── ROUTES ────────────────────────────────────────────────────────────────────

@app.get("/v1/health", tags=["System"])
async def health():
    # [FIX-7] убраны env_openai / env_deepseek — не раскрываем наличие ключей
    return {
        "status":    "operational",
        "version":   "2.1.0",
        "models": {
            "gpt-4o":   "ready" if GPT_OK else "unavailable",
            "deepseek": "ready" if DS_OK  else "unavailable",
        },
        "layers": {
            "medical": "real" if MEDICAL_OK else "stub",
            "legal":   "real" if LEGAL_OK   else "stub",
            "finance": "real" if FINANCE_OK  else "stub",
            "mental":  "real" if MENTAL_OK   else "stub",
        },
        "llm_ensemble": "ready" if _LLM_JUDGES_AVAILABLE else "stub",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.post("/v1/ask", tags=["Core"], dependencies=[Depends(verify_api_key)])
async def ask(request: Request, req: AskRequest):
    """
    Главный эндпоинт UMEQAM.
    1. GPT-4o + DeepSeek отвечают параллельно
    2. 5 судей анализируют оба ответа
    3. Возвращает risk_score + judge_results
    Rate limit: 100/minute per IP
    """
    # [FIX-2] rate limit только если slowapi установлен
    if RATE_LIMIT_OK:
        await limiter._check_request_limit(request, "100/minute")

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

    return {
        "request_id":    str(uuid.uuid4()),
        "question":      req.question,
        "answers":       answers,
        "risk_score":    risk_score,
        "judge_results": judge_results,
        "latency_ms":    round((time.perf_counter() - t0) * 1000, 1),
        "timestamp":     datetime.utcnow().isoformat() + "Z",
    }


@app.post("/v1/medical/analyze", tags=["Medical"], dependencies=[Depends(verify_api_key)])
async def medical_analyze(req: ComplianceRequest):
    t0 = time.perf_counter()
    fast = _reg_fast_path(req.content, "medical", t0)
    if fast: return fast
    try:
        raw = MedicalJudgeCouncil().evaluate(req.content, _build_answers(req)) if MEDICAL_OK else {
            "overall_verdict": "REVIEW", "compliance_score": 0.5,
            "judges_passed": 4, "judges_total": 8, "flags": ["stub_mode"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MedicalJudgeCouncil error: {str(e)[:200]}")
    result = _fmt(raw, "medical", 0)
    return await run_with_llm_judge(req.content, "medical", result, t0)


@app.post("/v1/legal/analyze", tags=["Legal"], dependencies=[Depends(verify_api_key)])
async def legal_analyze(req: ComplianceRequest):
    t0 = time.perf_counter()
    fast = _reg_fast_path(req.content, "legal", t0)
    if fast: return fast
    try:
        raw = LegalJudgeCouncil().evaluate(req.content, _build_answers(req)) if LEGAL_OK else {
            "overall_verdict": "REVIEW", "compliance_score": 0.5,
            "judges_passed": 4, "judges_total": 8, "flags": ["stub_mode"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LegalJudgeCouncil error: {str(e)[:200]}")
    result = _fmt(raw, "legal", 0)
    return await run_with_llm_judge(req.content, "legal", result, t0)


@app.post("/v1/finance/analyze", tags=["Finance"], dependencies=[Depends(verify_api_key)])
async def finance_analyze(req: ComplianceRequest):
    t0 = time.perf_counter()
    fast = _reg_fast_path(req.content, "finance", t0)
    if fast: return fast
    try:
        raw = FinanceJudgeCouncil().evaluate(req.content, _build_answers(req)) if FINANCE_OK else {
            "overall_verdict": "REVIEW", "compliance_score": 0.5,
            "judges_passed": 4, "judges_total": 8, "flags": ["stub_mode"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"FinanceJudgeCouncil error: {str(e)[:200]}")
    result = _fmt(raw, "finance", 0)
    return await run_with_llm_judge(req.content, "finance", result, t0)


@app.post("/v1/mental/analyze", tags=["Mental Health"], dependencies=[Depends(verify_api_key)])
async def mental_analyze(req: ComplianceRequest):
    t0 = time.perf_counter()
    try:                                        # [FIX-6]
        raw = MentalJudgeCouncil().evaluate(req.content, _build_answers(req)) if MENTAL_OK else {
            "overall_verdict": "REVIEW", "compliance_score": 0.5,
            "judges_passed": 4, "judges_total": 8, "flags": ["stub_mode"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MentalJudgeCouncil error: {str(e)[:200]}")
    fast = _reg_fast_path(req.content, "mental", t0)
    if fast: return fast
    result = _fmt(raw, "mental", 0)
    return await run_with_llm_judge(req.content, "mental", result, t0)    # [FIX-3]


# ── RUN ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)








