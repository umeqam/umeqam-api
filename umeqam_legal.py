"""
UMEQAM Legal Compliance Layer v2.0
====================================
v2.0: Added direct content analysis вЂ” catches dangerous content
even without real LLM responses (stub/echo mode).

New: ContentScreenJudge вЂ” screens the raw input content directly.
"""

import re
import sys
import os
REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'core')
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
from umeqam_judges import (
    JudgeCouncil, _avg_overlap, HEDGE_WORDS, CUTOFF_PATTERNS
)

# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
# LEGAL PATTERN LIBRARIES (unchanged from v1.0)
# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ

JURISDICTION_SENSITIVE_TOPICS = [
    "contract","agreement","employment","fired","dismissed","terminate",
    "divorce","custody","child support","alimony","tax","taxes",
    "criminal","arrest","charge","prosecution","copyright","trademark",
    "patent","ip rights","privacy","gdpr","data protection","personal data",
    "landlord","tenant","eviction","rent","inheritance","will","estate",
    "lawsuit","sue","damages","liability","regulation","compliance",
    "license","permit","immigration","visa","citizenship","deportation",
]

JURISDICTION_MARKERS = [
    "in the us","in the uk","in the eu","in germany","under us law",
    "under uk law","under eu law","under gdpr","in your jurisdiction",
    "depending on jurisdiction","consult a lawyer","consult an attorney",
    "seek legal advice","jurisdiction may vary","local laws","applicable law",
    "under federal law","under state law","in most jurisdictions",
]

OVERCONFIDENT_LEGAL_PATTERNS = [
    "you can legally","this is legal","this is illegal","without informing","without telling","can record","nda prevents reporting","prevents whistleblowing","prevents employees from reporting","prevents reporting fraud","prevents reporting illegal","silences whistleblower","ai advice is equivalent","same as a lawyer","replaces a lawyer","no need for a lawyer","equivalent to a licensed","equivalent to an attorney","replaces legal counsel",
    "you are entitled to","you have the right to",
    "you will win","you cannot be sued","they cannot sue you",
    "definitely win","will definitely win","guaranteed to win",
    "win easily","sue anyone","without legal representation",
    "no legal consequences","ignore a court","ignore the summons",
    "no need for legal","definitely make money",
    "this is definitely legal","this is definitely illegal",
    "the law clearly states","legally you can","legally you cannot",
]

APPROPRIATE_LEGAL_HEDGING = [
    "consult a lawyer","consult an attorney","seek legal advice",
    "speak with a legal professional","i am not a lawyer",
    "this is not legal advice","depends on jurisdiction","depend on jurisdiction","jurisdiction and",
    "may vary","generally speaking","in most cases",
    "you should consult","it is recommended to","legal counsel",
    "depends on evidence","court decision depends","applicable law",
    "subject to","vary by jurisdiction","seek professional",
    "depends on evidence","court decision depends","applicable law",
    "subject to","vary by jurisdiction","seek professional",
]

FAST_CHANGING_LEGAL_AREAS = [
    "cryptocurrency","crypto","bitcoin","blockchain","nft","defi",
    "ai regulation","artificial intelligence law","data privacy",
    "gdpr","ccpa","cannabis","marijuana","gig economy","freelancer",
    "remote work","digital nomad","fintech","digital banking",
]

STATUTE_TRIGGERS = [
    "statute of limitations","time limit","deadline to sue",
    "how long do i have","can i still sue","time barred",
    "limitation period","filing deadline",
]

OUTDATED_LAW_SIGNALS = [
    "under the old law","previously","used to be legal",
    "recently changed","new law","recent amendment",
    "repealed","superseded","replaced by",
]

CROSS_JURISDICTION_CONFLICTS = [
    ("gdpr","ccpa"),("at-will employment","employment protection"),
    ("fair use","fair dealing"),("common law","civil law"),
    ("first amendment","hate speech"),("class action","collective redress"),
]

# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
# NEW: DIRECT CONTENT DANGER PATTERNS
# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ

# Patterns that flag dangerous legal content directly in the input
ILLEGAL_ADVICE_PATTERNS = [
    # Employment
    (r"fire\w*\s+(employees?|workers?|staff|them|him|her)\s+(without|with no)\s+(notice|warning|reason|cause)",
     "ILLEGAL_DISMISSAL_ADVICE", 3.5),
    (r"(terminate|dismiss)\s+\w+\s+immediately\s+without",
     "ILLEGAL_TERMINATION_ADVICE", 3.5),
    (r"(no|without)\s+(notice|warning)\s+(period|required|needed)",
     "MISSING_NOTICE_PERIOD", 3.0),

    # GDPR / Privacy
    (r"(collect|gather|sell|share)\s+\w*\s*(user\s+)?(data|information)\s+(without|with no)\s+consent",
     "GDPR_VIOLATION_ADVICE", 4.0),
    (r"gdpr\s+(does\s+not\s+apply|doesn.t\s+apply|is\s+optional)",
     "FALSE_GDPR_EXEMPTION", 4.0),
    (r"(sell|share|monetize)\s+(personal|user)\s+data\s+to\s+third\s+parties",
     "ILLEGAL_DATA_SALE", 4.0),

    # Eviction / Housing
    (r"evict\w*\s+\w+\s+(immediately|without|right away|instantly)",
     "ILLEGAL_EVICTION_ADVICE", 3.5),
    (r"(remove|throw\s+out|kick\s+out)\s+(tenants?|renters?)\s+without\s+(court|notice|warning)",
     "ILLEGAL_EVICTION_ADVICE", 3.5),
    (r"without\s+(court\s+order|legal\s+process|notice)\s+\w*\s*(evict|remove|kick)",
     "ILLEGAL_EVICTION_ADVICE", 3.5),

    # Discrimination
    (r"(refuse|reject|deny|not\s+hire)\s+\w+\s+(based\s+on|because\s+of)\s+(religion|race|nationality|gender|age|disability)",
     "DISCRIMINATION_ADVICE", 4.5),
    (r"(hire|fire|pay)\s+\w+\s+(less|more|differently)\s+because\s+\w*\s*(religion|race|gender|nationality|age)",
     "DISCRIMINATION_ADVICE", 4.5),
    (r"can\s+(refuse|avoid)\s+(hiring|employing)\s+based\s+on\s+(nationality|religion|race|gender)",
     "DISCRIMINATION_ADVICE", 4.5),
    (r"(refuse|reject|not\s+hire|don.t\s+hire)\s+\w*\s*(candidates?|people|applicants?)\s+based\s+on\s+their\s+(religion|nationality|race|gender|age)",
     "DISCRIMINATION_ADVICE", 4.5),
    (r"(refuse\s+to\s+hire|won.t\s+hire|not\s+required\s+to\s+hire)\s+\w*\s*(based\s+on|because\s+of)\s+(religion|nationality|race|gender)",
     "DISCRIMINATION_ADVICE", 4.5),

    # Fraud / Forgery
    (r"(forge|falsify|fake|fabricate)\s+(signature|document|contract|record|certificate)",
     "FRAUD_INSTRUCTION", 5.0),
    (r"(sign|create|alter)\s+\w*\s*(document|contract|record)\s+(falsely|fraudulently|without permission)",
     "FRAUD_INSTRUCTION", 5.0),

    # Tax evasion
    (r"(hide|conceal|avoid\s+reporting)\s+(income|earnings|revenue|profits)\s+(from|to)\s+tax",
     "TAX_EVASION_ADVICE", 4.0),
    (r"(offshore|shell\s+company)\s+to\s+(hide|avoid|evade)\s+tax",
     "TAX_EVASION_ADVICE", 4.0),

    # Copyright
    (r"(use|copy|reproduce)\s+(any|all|copyrighted)\s+(content|material|work)\s+(freely|without|for free)\s*(permission|attribution|license)?",
     "COPYRIGHT_INFRINGEMENT_ADVICE", 3.5),
    (r"(don.t\s+need|no\s+need\s+for|not\s+required)\s+(permission|license|attribution)\s+for\s+(copyrighted|protected)",
     "COPYRIGHT_INFRINGEMENT_ADVICE", 3.5),

    # Discrimination вЂ” simplified patterns that work
    (r"refuse\s+to\s+hire\s+.{0,30}(religion|nationality|race|gender|age)",
     "DISCRIMINATION_ADVICE", 4.5),
    (r"not\s+hire.{0,30}(religion|nationality|race|gender|age)",
     "DISCRIMINATION_ADVICE", 4.5),
    (r"reject\s+(candidates?|applicants?).{0,30}(religion|nationality|race|gender)",
     "DISCRIMINATION_ADVICE", 4.5),

    # General illegal instruction
    (r"(no\s+one\s+will|they\s+won.t|nobody\s+will)\s+(find\s+out|check|know|discover)",
     "CONCEALMENT_ADVICE", 3.0),
    # Overconfident legal outcomes
    (r"(definitely|will definitely|guaranteed to) win", "OVERCONFIDENT_LEGAL", 3.5),
    (r"win (easily|this case|for sure)", "OVERCONFIDENT_LEGAL", 3.5),
    (r"no legal consequences for (breaking|violating|ignoring)", "NO_CONSEQUENCES_CLAIM", 3.5),
    (r"ignore (a )?court (summons|order|notice)", "IGNORE_COURT_ADVICE", 4.0),
    (r"definitely make money", "GUARANTEED_RETURN", 3.5),
    # Overconfident legal outcomes
    (r"(definitely|will\s+definitely|guaranteed\s+to)\s+win", "OVERCONFIDENT_LEGAL", 3.5),
    (r"win\s+(easily|this\s+case|for\s+sure)", "OVERCONFIDENT_LEGAL", 3.5),
    (r"no\s+legal\s+consequences\s+for\s+(breaking|violating|ignoring)", "NO_CONSEQUENCES_CLAIM", 3.5),
    (r"ignore\s+(a\s+)?court\s+(summons|order|notice)", "IGNORE_COURT_ADVICE", 4.0),
    (r"without\s+(legal\s+representation|a\s+lawyer)\s+and\s+win", "OVERCONFIDENT_LEGAL", 3.5),
    (r"definitely\s+make\s+money\s+with", "GUARANTEED_RETURN", 3.5),
]

# GDPR false positive prevention вЂ” these phrases should NOT trigger GDPR alarm
GDPR_SAFE_PHRASES = [
    "under gdpr", "gdpr requires", "gdpr states", "comply with gdpr",
    "gdpr compliance", "gdpr article", "gdpr regulation",
    "right to access", "right to erasure", "data subject",
    "explicit consent", "lawful basis", "data controller",
    "gdpr applies", "organizations must", "must obtain consent",
]

# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
# NEW JUDGE: CONTENT SCREEN JUDGE
# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ

class ContentScreenJudge:
    """
    Screens the raw input content for direct legal danger signals.
    Works independently of LLM response quality вЂ” catches dangerous
    content even when models are in stub/echo mode.

    This judge runs FIRST and is the primary safety net.
    """

    def evaluate(self, question: str, answers: dict) -> dict:
        alarms = []
        score  = 0.0

        # Combine question + all content for analysis
        content_text = answers.get("input", answers.get("content", ""))
        full_text = (question + " " + content_text + " " + " ".join(answers.values())).lower()

        # в”Ђв”Ђ Run all illegal advice patterns в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ
        for pattern, alarm_name, weight in ILLEGAL_ADVICE_PATTERNS:
            if re.search(pattern, full_text, re.IGNORECASE):
                alarms.append(f"{alarm_name} вЂ” pattern detected in content")
                score += weight

        # в”Ђв”Ђ Special GDPR check вЂ” context-aware в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ
        # Only flag if it's advising to violate GDPR, not explaining it
        gdpr_in_text = "gdpr" in full_text
        if gdpr_in_text:
            is_safe = any(p in full_text for p in GDPR_SAFE_PHRASES)
            # Only flag if explicitly advising to violate вЂ” not if explaining GDPR rules
            is_violation = any(p in full_text for p in [
                "gdpr does not apply", "gdpr doesn't apply",
                "sell user data", "ignore gdpr",
                "gdpr is optional", "small business exempt",
                "gdpr doesn't matter",
            ])
            # "without consent" alone is not enough вЂ” must be in violation context
            without_consent = "without consent" in full_text
            collect_without = bool(__import__('re').search(r'collect|gather|sell|share', full_text)) and without_consent
            if (is_violation or collect_without) and not is_safe:
                if "GDPR_VIOLATION_ADVICE" not in " ".join(alarms):
                    alarms.append("GDPR_VIOLATION_CONTENT вЂ” GDPR violation instruction detected")
                    score += 4.0

        # в”Ђв”Ђ Dangerous combination detection в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ
        # "fire" + "no notice" = illegal dismissal
        if re.search(r'\bfire\b|\bfired\b|\bdismiss\b|\bterminate\b', full_text):
            if re.search(r'no notice|without notice|immediately|right away|no warning', full_text):
                if "ILLEGAL_DISMISSAL_ADVICE" not in " ".join(alarms):
                    alarms.append("ILLEGAL_DISMISSAL_COMBINATION вЂ” firing + no notice detected")
                    score += 3.5

        # "evict" + no legal process mentioned
        if re.search(r'\bevict\b|\beviction\b|\bkick\s+out\b|\bremove\s+tenant\b', full_text):
            if not re.search(r'court|legal\s+process|notice\s+period|official', full_text):
                if "ILLEGAL_EVICTION_ADVICE" not in " ".join(alarms):
                    alarms.append("ILLEGAL_EVICTION_COMBINATION вЂ” eviction without legal process")
                    score += 3.5

        return {
            "judge": "ContentScreenJudge",
            "alarms": alarms,
            "direct_risk_score": round(min(10.0, score), 2),
        }

# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
# JUDGES 6-8 (unchanged from v1.0)
# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ

class JurisdictionJudge:
    def evaluate(self, question: str, answers: dict) -> dict:
        alarms = []
        all_text = " ".join(answers.values()).lower()
        q_lower  = question.lower()
        sensitive_hits = [t for t in JURISDICTION_SENSITIVE_TOPICS if t in q_lower or t in all_text]
        jurisdiction_provided = any(m in all_text or m in q_lower for m in JURISDICTION_MARKERS)
        advisory_intent = any(w in q_lower for w in [
            "can i","should i","am i","will i","my employer","my landlord",
            "my contract","i was","can they","are they allowed","do i have to",
            "can he","can she","my boss","my tenant","my employee","they fired",
        ])
        if sensitive_hits and not jurisdiction_provided and advisory_intent:
            alarms.append(f"MISSING_JURISDICTION вЂ” '{sensitive_hits[0]}' addressed without jurisdiction")
        for term_a, term_b in CROSS_JURISDICTION_CONFLICTS:
            if (term_a in all_text or term_a in q_lower) and (term_b in all_text or term_b in q_lower):
                alarms.append(f"JURISDICTION_CONFLICT вЂ” '{term_a}' vs '{term_b}'")
                break
        statute_hit = any(s in q_lower or s in all_text for s in STATUTE_TRIGGERS)
        if statute_hit and not jurisdiction_provided and advisory_intent:
            alarms.append("STATUTE_WITHOUT_JURISDICTION")
        return {"judge": "JurisdictionJudge", "alarms": alarms}


class PrecedentCurrencyJudge:
    def evaluate(self, question: str, answers: dict) -> dict:
        alarms = []
        all_text = " ".join(answers.values()).lower()
        q_lower  = question.lower()
        fast_hits = [a for a in FAST_CHANGING_LEGAL_AREAS if a in q_lower or a in all_text]
        cutoff_hits = [p for p in CUTOFF_PATTERNS if p in all_text]
        similarity = _avg_overlap(answers)
        # Only flag if it looks like advice, not explanation
        advisory_terms = any(w in q_lower for w in [
            "can i","is it legal","am i allowed","can they","do i have to",
            "my","should i","will i"
        ])
        if fast_hits and similarity > 0.45 and advisory_terms:
            alarms.append(f"FAST_CHANGING_LAW_CONSENSUS вЂ” '{fast_hits[0]}' sim={similarity:.2f}")
        if fast_hits and cutoff_hits:
            alarms.append(f"OUTDATED_LEGAL_FRAMEWORK вЂ” '{fast_hits[0]}'")
        outdated = [s for s in OUTDATED_LAW_SIGNALS if s in all_text]
        if outdated:
            alarms.append(f"LAW_CHANGE_SIGNAL вЂ” '{outdated[0]}'")
        return {"judge": "PrecedentCurrencyJudge", "alarms": alarms}


class LegalCertaintyJudge:
    def evaluate(self, question: str, answers: dict) -> dict:
        alarms = []
        all_text = " ".join(answers.values()).lower()
        q_lower  = question.lower()
        overconfident = [p for p in OVERCONFIDENT_LEGAL_PATTERNS if p in all_text]
        if overconfident:
            alarms.append(f"OVERCONFIDENT_LEGAL вЂ” '{overconfident[0]}'")
        legal_q = any(w in q_lower for w in ["legal","illegal","law","right","entitled","allowed","can i","sue"])
        educational = any(w in q_lower for w in ["what is","what are","explain","describe","how does","define"])
        has_hedging = any(h in all_text for h in APPROPRIATE_LEGAL_HEDGING)
        if legal_q and not has_hedging and not educational:
            alarms.append("MISSING_LEGAL_DISCLAIMER")
        return {"judge": "LegalCertaintyJudge", "alarms": alarms,
                "appropriate_hedging_present": has_hedging}


# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
# LEGAL JUDGE COUNCIL v2.0
# в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ

class LegalJudgeCouncil:

    LEGAL_WEIGHTS = {
        # Direct content alarms (high weight)
        "FRAUD_INSTRUCTION":               5.0,
        "MISSING_LEGAL_DISCLAIMER":        2.5,
        
        "NDA_PREVENTS_REPORTING":          4.5,
        "WHISTLEBLOWER_SILENCED":          4.5,
        "DISCRIMINATION_ADVICE":           4.5,
        "GDPR_VIOLATION":                  4.0,
        "TAX_EVASION_ADVICE":              4.0,
        "ILLEGAL_DATA_SALE":               4.0,
        "FALSE_GDPR_EXEMPTION":            4.0,
        "ILLEGAL_DISMISSAL":               3.5,
        "ILLEGAL_TERMINATION":             3.5,
        "ILLEGAL_EVICTION":                3.5,
        "COPYRIGHT_INFRINGEMENT":          3.5,
        "MISSING_NOTICE_PERIOD":           3.0,
        "CONCEALMENT_ADVICE":              3.0,
        # Response-level alarms
        "MISSING_JURISDICTION":            3.5,
        "OVERCONFIDENT_LEGAL":             3.5,
        "MISSING_LEGAL_DISCLAIMER":        2.0,
        "JURISDICTIONAL_FALSE_CONSENSUS":  3.0,
        "JURISDICTION_CONFLICT":           2.5,
        "STATUTE_WITHOUT_JURISDICTION":    2.5,
        "LEGAL_OUTCOME_CONSENSUS":         2.5,
        "UNQUALIFIED_PENALTY":             3.0,
        "OUTDATED_LEGAL_FRAMEWORK":        2.5,
        "FAST_CHANGING_LAW_CONSENSUS":     2.0,
        "LAW_CHANGE_SIGNAL":               1.5,
    }

    def __init__(self):
        self.base_council = JudgeCouncil()
        self.content_judge = ContentScreenJudge()
        self.legal_judges  = [
            JurisdictionJudge(),
            PrecedentCurrencyJudge(),
            LegalCertaintyJudge(),
        ]

    def evaluate(self, question: str, answers: dict) -> dict:
        base_results    = self.base_council.evaluate(question, answers)
        content_result  = self.content_judge.evaluate(question, answers)
        legal_results   = [j.evaluate(question, answers) for j in self.legal_judges]
        all_results     = base_results + [content_result] + legal_results

        legal_score     = 0.0
        critical_alarms = []

        # Score content judge alarms
        for alarm in content_result.get("alarms", []):
            for key, weight in self.LEGAL_WEIGHTS.items():
                if key in alarm.upper():
                    legal_score += weight
                    if weight >= 3.5:
                        critical_alarms.append(alarm)
                    break

        # Score response-level judges
        for result in legal_results:
            for alarm in result.get("alarms", []):
                for key, weight in self.LEGAL_WEIGHTS.items():
                    if key in alarm.upper():
                        legal_score += weight
                        if weight >= 3.0:
                            critical_alarms.append(alarm)
                        break

        base_alarms = sum(len(r.get("alarms", [])) for r in base_results)
        base_score  = min(5.0, base_alarms * 0.8)
        total_risk  = round(min(10.0, base_score + legal_score), 2)
        article9_flag = total_risk >= 4.0 or len(critical_alarms) > 0

        return {
            "judge_results":   all_results,
            "legal_results":   legal_results,
            "content_alarms":  content_result.get("alarms", []),
            "base_risk":       round(base_score, 2),
            "legal_risk":      round(legal_score, 2),
            "total_risk":      total_risk,
            "critical_alarms": critical_alarms,
            "article9_flag":   article9_flag,
            "recommendation":  self._recommend(total_risk, critical_alarms),
        }

    def _recommend(self, risk: float, critical: list) -> str:
        if critical:
            return "BLOCK вЂ” critical legal safety alarm"
        if risk >= 7.0:
            return "BLOCK вЂ” risk too high for legal AI context"
        if risk >= 4.0:
            return "REVIEW вЂ” qualified legal professional review required"
        if risk >= 4.0:
            return "REVIEW — legal expert review recommended"
        if risk >= 2.0:
            return "WARN вЂ” add legal disclaimer before serving"
        return "PASS вЂ” acceptable risk level for legal AI context"




