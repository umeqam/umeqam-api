"""
UMEQAM R-ME v1.0 - Meaning Extractor
"""
import re
from dataclasses import dataclass, field
from typing import List, Dict
from enum import Enum

class IntentType(Enum):
    QUERY = "query"
    ASSERTION = "assertion"
    INSTRUCTION = "instruction"
    REQUEST = "request"
    UNKNOWN = "unknown"

class EpistemicMode(Enum):
    CERTAIN = "certain"
    UNCERTAIN = "uncertain"
    OVERCONFIDENT = "overconfident"
    HEDGED = "hedged"
    NEUTRAL = "neutral"

@dataclass
class MeaningVector:
    raw_text: str
    intent: IntentType
    epistemic_mode: EpistemicMode
    domain_signals: Dict[str, float]
    certainty_score: float
    hedge_score: float
    authority_claim: float
    semantic_flags: List[str] = field(default_factory=list)
    meaning_score: float = 0.0

CERTAINTY_MARKERS = ["definitely","certainly","guaranteed","always","never","100%","proven","obviously","clearly","without doubt","absolutely","sure","certain","no risk","safe to","will definitely","guaranteed to","immune to","cures","cure all","reverse","reverses","heal completely","heals completely","eliminate","eliminates","will make you","makes you immune","will cure","will heal","will reverse","will eliminate","replace all","replaces all","no need for","no need to","don't need","skip all","skipping all","prescribe to","stop taking","complete cure","absolute cure","guaranteed cure","guaranteed to work","100% effective","proven cure","never fails","always works","will never","will always"]
HEDGE_MARKERS = ["may","might","could","possibly","perhaps","generally","in most cases","usually","often","depends","varies","consult","recommend","suggest","consider","typically","seek professional","talk to a","speak with"]
AUTHORITY_MARKERS = ["you must","you should","you have to","you need to","the law states","legally you","medically proven","science says","experts agree","everyone knows","it is known","studies show"]
DOMAIN_KEYWORDS = {
    "medical": ["doctor","medication","drug","dose","symptom","diagnosis","treatment","prescription","health","medical","patient","pharmacy","hospital","surgery","therapy"],
    "legal": ["law","legal","court","judge","lawyer","attorney","sue","contract","rights","illegal","crime","lawsuit","verdict","jurisdiction","statute","liability"],
    "finance": ["invest","money","stock","crypto","return","profit","loss","portfolio","market","trading","fund","asset","risk","financial","bank","savings"],
    "mental": ["depression","anxiety","mental","therapy","psychiatrist","suicide","self-harm","stress","trauma","mood","emotion","psychological","counselor","wellbeing"],
}

class MeaningExtractor:
    def extract(self, text: str) -> MeaningVector:
        t = text.lower().strip()
        intent = self._intent(t)
        mode = self._mode(t)
        domains = self._domains(t)
        certainty = min(sum(1 for m in CERTAINTY_MARKERS if m in t) * 0.35, 1.0)
        hedge = min(sum(1 for m in HEDGE_MARKERS if m in t) * 0.25, 1.0)
        authority = min(sum(1 for m in AUTHORITY_MARKERS if m in t) * 0.4, 1.0)
        flags = self._flags(t, certainty, hedge, authority, mode)
        score = self._score(certainty, hedge, authority, domains, mode)
        return MeaningVector(raw_text=text, intent=intent, epistemic_mode=mode, domain_signals=domains, certainty_score=round(certainty,3), hedge_score=round(hedge,3), authority_claim=round(authority,3), semantic_flags=flags, meaning_score=round(score,3))

    def _intent(self, t):
        if t.endswith("?") or t.startswith(("what","how","why","when","where","who","can i","should i")): return IntentType.QUERY
        if any(t.startswith(w) for w in ["take","do","stop","start","use","buy","sell","ignore"]): return IntentType.INSTRUCTION
        if any(w in t for w in ["please","help me","i need","can you","could you"]): return IntentType.REQUEST
        if any(w in t for w in ["is","are","will","can","you can","it is","this is"]): return IntentType.ASSERTION
        return IntentType.UNKNOWN

    def _mode(self, t):
        c = sum(1 for m in CERTAINTY_MARKERS if m in t)
        h = sum(1 for m in HEDGE_MARKERS if m in t)
        if c >= 2: return EpistemicMode.OVERCONFIDENT
        if c == 1 and h == 0: return EpistemicMode.CERTAIN
        if h >= 2: return EpistemicMode.HEDGED
        if h == 1: return EpistemicMode.UNCERTAIN
        return EpistemicMode.NEUTRAL

    def _domains(self, t):
        return {d: round(min(sum(1 for kw in kws if kw in t)/3.0,1.0),3) for d,kws in DOMAIN_KEYWORDS.items()}

    def _flags(self, t, c, h, a, mode):
        flags = []
        if mode == EpistemicMode.OVERCONFIDENT: flags.append("OVERCONFIDENT_ASSERTION")
        if c > 0.6 and h < 0.1: flags.append("HIGH_CERTAINTY_NO_HEDGE")
        if a > 0.4: flags.append("AUTHORITY_CLAIM")
        if c > 0.3 and any(d in t for d in ["medical","doctor","drug","medication"]): flags.append("MEDICAL_CERTAINTY_RISK")
        if c > 0.3 and any(d in t for d in ["invest","return","profit","guaranteed"]): flags.append("FINANCIAL_CERTAINTY_RISK")
        if c > 0.3 and any(d in t for d in ["legal","law","court","win"]): flags.append("LEGAL_CERTAINTY_RISK")
        return flags

    def _score(self, c, h, a, domains, mode):
        penalty = {"overconfident":0.4,"certain":0.2,"neutral":0.0,"uncertain":-0.1,"hedged":-0.2}.get(mode.value,0.0)
        domain_max = max(domains.values()) if domains else 0.0
        return max(0.0, min(c*0.35 + a*0.25 + domain_max*0.2 + penalty*0.2 - h*0.15, 1.0))

    def to_dict(self, mv: MeaningVector) -> dict:
        return {"raw_text":mv.raw_text,"intent":mv.intent.value,"epistemic_mode":mv.epistemic_mode.value,"domain_signals":mv.domain_signals,"certainty_score":mv.certainty_score,"hedge_score":mv.hedge_score,"authority_claim":mv.authority_claim,"semantic_flags":mv.semantic_flags,"meaning_score":mv.meaning_score}

if __name__ == "__main__":
    extractor = MeaningExtractor()
    tests = [
        "Take 500mg aspirin daily without consulting a doctor.",
        "Guaranteed 300% return on crypto investment.",
        "You will definitely win this case without a lawyer.",
        "Consult your doctor before changing any medication.",
        "Investment returns depend on market conditions.",
        "Just stop being sad happiness is a choice.",
    ]
    for t in tests:
        mv = extractor.extract(t)
        d = extractor.to_dict(mv)
        print(f"\nText: {t[:60]}")
        print(f"  Intent:{d['intent']} | Mode:{d['epistemic_mode']} | Score:{d['meaning_score']}")
        print(f"  Flags: {d['semantic_flags']}")