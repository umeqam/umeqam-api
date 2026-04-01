from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Any

class ResponseMode(Enum):
    INSUFFICIENT_EVIDENCE  = "INSUFFICIENT EVIDENCE"
    INSUFFICIENT_AUTHORITY = "INSUFFICIENT AUTHORITY TO DECIDE"
    FRAME_INVALID          = "FRAME IS INVALID"
    BLOCK                  = "BLOCK"
    ALLOW                  = "ALLOW"

@dataclass
class Signal:
    name:   str
    value:  str
    weight: float = 1.0

class SignalEngine:
    def compute_risk(self, s: Dict[str, float]) -> float:
        risk = (
            0.35 * s.get("S7", 0.0) +
            0.22 * s.get("S3", 0.0) +
            0.18 * s.get("S1", 0.0) +
            0.15 * s.get("S2", 0.0) +
            0.10 * s.get("S5", 0.0)
        )
        return min(max(risk, 0.0), 1.0)

    def escalation(self, s: Dict[str, float], high_stakes: bool = False) -> Dict[str, Any]:
        flags = []
        bonus = 0.0
        if s.get("S8", 0) > 0.55: flags.append("S8_Conflict"); bonus += 0.35
        if s.get("S4", 0) > 0.60: flags.append("S4_Pressure"); bonus += 0.30
        if s.get("S6", 0) > 0.60: flags.append("S6_Mismatch"); bonus += 0.25
        if high_stakes: bonus += 0.18
        return {"flags": flags, "bonus": min(bonus, 0.55)}

class EpistemicGuardrail:
    def __init__(self):
        self.engine = SignalEngine()

    def analyze_signals(self, signals: List[Signal]) -> Dict[str, Any]:
        positive = sum(1 for s in signals if s.value == "+")
        negative = sum(1 for s in signals if s.value == "-")
        missing  = sum(1 for s in signals if s.value == "?")
        return {
            "positive": positive, "negative": negative, "missing": missing,
            "conflict": positive > 0 and negative > 0,
            "high_uncertainty": missing >= 2 or (positive + negative == 0),
        }

    def detect_invalid_frame(self, context: Dict[str, Any]) -> bool:
        flags = context.get("logic_flags", [])
        text  = context.get("raw_text", "").lower()
        invalid_patterns = [
            any(x in text for x in ["no evidence", "no grounds", "oснований нет"]),
            any(x in text for x in ["immediately", "or we lose", "guaranteed"]),
        ]
        explicit = any(f in flags for f in ["absence_of_evidence", "burden_shift", "pressure"])
        return explicit or any(invalid_patterns)

    def decide(self, signals: List[Signal], signal_scores: Dict[str, float], context: Dict[str, Any]) -> Dict[str, Any]:
        sig         = self.analyze_signals(signals)
        risk        = self.engine.compute_risk(signal_scores)
        esc         = self.engine.escalation(signal_scores, context.get("high_stakes", False))
        final_score = risk + esc["bonus"]

        if self.detect_invalid_frame(context):
            return self._result(ResponseMode.FRAME_INVALID, sig, final_score, esc)
        if context.get("high_stakes", False) and (sig["conflict"] or sig["high_uncertainty"]):
            return self._result(ResponseMode.INSUFFICIENT_AUTHORITY, sig, final_score, esc)
        if sig["conflict"] or sig["high_uncertainty"]:
            return self._result(ResponseMode.INSUFFICIENT_EVIDENCE, sig, final_score, esc)
        if final_score > 0.82:
            return self._result(ResponseMode.BLOCK, sig, final_score, esc)
        return self._result(ResponseMode.ALLOW, sig, final_score, esc)

    def _result(self, mode, sig, score, esc):
        explanations = {
            ResponseMode.FRAME_INVALID.value:          "Invalid logical frame detected.",
            ResponseMode.INSUFFICIENT_AUTHORITY.value: "High stakes + conflict + uncertainty.",
            ResponseMode.INSUFFICIENT_EVIDENCE.value:  "Signal conflict with missing data.",
            ResponseMode.BLOCK.value:                  "Epistemic risk too high.",
        }
        recommendations = {
            ResponseMode.FRAME_INVALID.value:          "Reformulate. Independent audit required.",
            ResponseMode.INSUFFICIENT_AUTHORITY.value: "Suspend. Requires audit and experts.",
            ResponseMode.INSUFFICIENT_EVIDENCE.value:  "Collect missing data first.",
            ResponseMode.BLOCK.value:                  "Block until deep analysis complete.",
        }
        return {
            "mode":             mode.value,
            "signals":          sig,
            "risk_score":       round(min(score, 1.0), 3),
            "escalation_flags": esc["flags"],
            "explanation":      explanations.get(mode.value, ""),
            "recommendation":   recommendations.get(mode.value, ""),
        }

def parse_signals(raw_text: str) -> List[Signal]:
    text = raw_text.lower()
    signals = []
    if any(k in text for k in ["guaranteed", "certain", "definitely", "always"]):
        signals.append(Signal("overconfidence", "-"))
    if any(k in text for k in ["no data", "unknown", "unclear", "missing"]):
        signals.append(Signal("missing_data", "?"))
    if any(k in text for k in ["evidence", "study", "research", "proven"]):
        signals.append(Signal("evidence", "+"))
    return signals or [Signal("default", "?")]
