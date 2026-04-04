import math, uuid, json, os, hashlib
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum

DEPLOY_SALT = os.environ.get("UMEQAM_MEMORY_SALT", "umeqam_default_salt_2026")

def anonymize(value: str) -> str:
    return hashlib.sha256(f"{value}{DEPLOY_SALT}".encode()).hexdigest()[:16]

def compute_decay(initial: float, decay_rate: float, days_elapsed: float) -> float:
    return round(initial * math.exp(-decay_rate * days_elapsed), 4)

def build_vector(meaning_score=0.0, medical=0.0, legal=0.0, finance=0.0, mental=0.0, certainty=0.0, hedge=0.0, authority=0.0):
    return [meaning_score, medical, legal, finance, mental, certainty, hedge, authority]

def vector_similarity(v1, v2):
    if len(v1) != len(v2): return 0.0
    dot = sum(a*b for a,b in zip(v1,v2))
    mag1 = math.sqrt(sum(a**2 for a in v1)) or 1e-9
    mag2 = math.sqrt(sum(b**2 for b in v2)) or 1e-9
    return round(dot/(mag1*mag2), 4)

@dataclass
class MemoryRecord:
    memory_id: str
    timestamp: str
    ttl_policy: str
    expires_at: str
    domain: str
    epistemic_mode: str
    meaning_score: float
    vector: List[float]
    verdict: str
    G_score: float
    audit_id: str
    is_anomaly: bool
    deviation_score: float
    anomaly_reason: str
    actor_category: str
    zone_category: str
    weight_initial: float
    weight_current: float
    decay_rate: float
    days_elapsed: float
    session_id: str
    sequence_num: int
    prev_memory_id: Optional[str] = None

    def to_dict(self): return asdict(self)

class UMEQAMMemory:
    def __init__(self, max_size=10000):
        self.records: List[MemoryRecord] = []
        self.max_size = max_size
        self.session_id = str(uuid.uuid4())[:8]
        self.sequence = 0
        self._last_maintain = datetime.now(timezone.utc)

    def __len__(self): return len(self.records)
    def clear(self): self.records.clear(); self.sequence = 0

    def store(self, domain, epistemic_mode, meaning_score, medical=0.0, legal=0.0,
              finance=0.0, mental=0.0, certainty=0.0, hedge=0.0, authority=0.0,
              verdict="REVIEW", G_score=0.5, audit_id="", is_anomaly=False,
              deviation_score=0.0, anomaly_reason="", actor="unknown", zone="unknown",
              ttl_policy="session", decay_rate=0.05):
        now = datetime.now(timezone.utc)
        if ttl_policy == "session": expires = now + timedelta(hours=8)
        elif ttl_policy == "permanent": expires = now + timedelta(days=3650)
        else: expires = now + timedelta(days=30) if is_anomaly else now + timedelta(hours=1)
        self.sequence += 1
        prev_id = self.records[-1].memory_id if self.records else None
        record = MemoryRecord(
            memory_id=f"MEM-{str(uuid.uuid4())[:8]}",
            timestamp=now.isoformat(), ttl_policy=ttl_policy,
            expires_at=expires.isoformat(), domain=domain,
            epistemic_mode=epistemic_mode, meaning_score=round(meaning_score,3),
            vector=build_vector(meaning_score,medical,legal,finance,mental,certainty,hedge,authority),
            verdict=verdict, G_score=round(G_score,4),
            audit_id=audit_id or f"UMEQAM-{str(uuid.uuid4())[:8]}",
            is_anomaly=is_anomaly, deviation_score=round(deviation_score,3),
            anomaly_reason=anomaly_reason, actor_category=anonymize(actor),
            zone_category=anonymize(zone), weight_initial=1.0, weight_current=1.0,
            decay_rate=decay_rate, days_elapsed=0.0, session_id=self.session_id,
            sequence_num=self.sequence, prev_memory_id=prev_id)
        self.records.append(record)
        if len(self.records) > self.max_size:
            self.records = self.records[-self.max_size:]
        return record

    def _refresh_decay(self, rec):
        now = datetime.now(timezone.utc)
        created = datetime.fromisoformat(rec.timestamp)
        if created.tzinfo is None: created = created.replace(tzinfo=timezone.utc)
        rec.days_elapsed = (now - created).total_seconds() / 86400
        rec.weight_current = compute_decay(rec.weight_initial, rec.decay_rate, rec.days_elapsed)

    def lookup(self, vector, threshold=0.85, domain=None):
        candidates = [r for r in self.records if domain is None or r.domain == domain]
        if not candidates: candidates = self.records
        best_match, best_score = None, 0.0
        for rec in candidates:
            self._refresh_decay(rec)
            if rec.weight_current < 0.1: continue
            sim = vector_similarity(vector, rec.vector) * rec.weight_current
            if sim > best_score: best_score = sim; best_match = rec
        return best_match if best_score >= threshold else None

    def classify_prerequisite(self, vector, domain):
        DOMAIN_RISK = {"medical":0.9,"legal":0.8,"finance":0.7,"mental":0.95,"general":0.3}
        match = self.lookup(vector, threshold=0.85, domain=domain)
        risk = DOMAIN_RISK.get(domain, 0.5)
        if match and match.is_anomaly and match.deviation_score > 0.7: return "TYPE1"
        if match and match.verdict == "ALLOW" and risk < 0.7: return "TYPE1"
        if match and risk >= 0.8: return "TYPE2"
        if not match: return "TYPE3"
        return "TYPE2"

    def maintain(self):
        now = datetime.now(timezone.utc)
        before = len(self.records)
        for rec in self.records: self._refresh_decay(rec)
        self.records = [r for r in self.records
            if datetime.fromisoformat(r.expires_at).replace(tzinfo=timezone.utc) > now
            and r.weight_current >= 0.1]
        return before - len(self.records)

    def save_to_json(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"session_id":self.session_id,"sequence":self.sequence,
                       "records":[r.to_dict() for r in self.records]}, f, indent=2, default=str)

    def load_from_json(self, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.session_id = data.get("session_id", self.session_id)
        self.sequence = data.get("sequence", 0)
        self.records = [MemoryRecord(**d) for d in data.get("records", [])]

    def stats(self):
        return {"total":len(self.records),
                "active":sum(1 for r in self.records if r.weight_current > 0.1),
                "anomalies":sum(1 for r in self.records if r.is_anomaly),
                "blocks":sum(1 for r in self.records if r.verdict=="BLOCK"),
                "domains":{r.domain:0 for r in self.records}}
