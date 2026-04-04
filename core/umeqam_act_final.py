import uuid, time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

class Verdict(Enum):
    ALLOW="ALLOW"; WARN="WARN"; BLOCK="BLOCK"
    FORCE_VERIFICATION="FORCE_VERIFICATION"; REVIEW="REVIEW"

class Domain(Enum):
    MEDICAL="medical"; LEGAL="legal"; FINANCE="finance"
    MENTAL="mental"; GENERAL="general"

class ActionType(Enum):
    HARD_BLOCK="HARD_BLOCK"; SOFT_BLOCK="SOFT_BLOCK"
    WARN="WARN"; ALLOW="ALLOW"; MINIMUM_SAFE="MINIMUM_SAFE_ACTION"
    FORCE_VERIFY="FORCE_VERIFICATION_ACTION"
    ROUTE_TO_REVIEW="ROUTE_TO_REVIEW"; PENDING_HUMAN="PENDING_HUMAN_CONFIRMATION"

class ExecutionMode(Enum):
    AUTONOMOUS="AUTONOMOUS"; SUPERVISED="SUPERVISED"; FALLBACK="FALLBACK"

class HumanStatus(Enum):
    AVAILABLE="available"; DELAYED="delayed"; UNAVAILABLE="unavailable"

class ExecutionState(Enum):
    INIT="INIT"; VALIDATED="VALIDATED"; DECISION_MADE="DECISION_MADE"
    EXECUTING="EXECUTING"; WAITING_HUMAN="WAITING_HUMAN"
    COMPLETED="COMPLETED"; FAILED="FAILED"; ROLLED_BACK="ROLLED_BACK"

@dataclass
class PolicyConfig:
    G_threshold_autonomous: float = 0.65
    memory_stale_threshold: float = 0.3
    memory_downgrade_threshold: float = 0.3
    rollback_window_ms: int = 500
    retry_max: int = 3
    timeout_ms: int = 10000
    high_risk_threshold: float = 0.8
    domain_risk: Dict = field(default_factory=lambda: {
        "medical":0.9,"legal":0.8,"finance":0.7,"mental":0.95,"general":0.3})
    domain_escalation: Dict = field(default_factory=lambda: {
        "medical":"doctor","legal":"lawyer","finance":"regulator",
        "mental":"support_line","general":"none"})

class EventBus:
    def __init__(self): self.events = []
    def emit(self, event_type, payload):
        evt = {"event_id":f"EVT-{str(uuid.uuid4())[:8]}",
               "type":event_type,
               "timestamp":datetime.now(timezone.utc).isoformat(),
               "payload":payload}
        self.events.append(evt)
        return evt

@dataclass
class ExecutionContext:
    act_id: str
    state: ExecutionState = ExecutionState.INIT
    retries: int = 0
    max_retries: int = 3
    timeout_ms: int = 10000
    start_time: float = field(default_factory=time.time)
    result: Optional[Dict] = None

class UMEQAMActEngine:
    def __init__(self, policy=None):
        self.policy = policy or PolicyConfig()
        self.outcome_log = []

    def execute(self, verdict, G_score, source_audit_id, domain,
                prerequisite_type="TYPE2", memory_weight=1.0,
                memory_history=None, is_anomaly=False,
                human_status="available", human_response_ms=5000,
                irreversible=False):
        act_id = f"ACT-{str(uuid.uuid4())[:8]}"
        bus = EventBus()
        ctx = ExecutionContext(act_id=act_id, max_retries=self.policy.retry_max)
        bus.emit("START", {"act_id":act_id})

        try:
            v = Verdict(verdict.upper())
            d = Domain(domain.lower())
            g = round(max(0.0, min(1.0, G_score)), 4)
            h = HumanStatus(human_status.lower())
            ctx.state = ExecutionState.VALIDATED
        except ValueError as e:
            ctx.state = ExecutionState.FAILED
            return {"act_audit_id":act_id,"state":"FAILED","error":str(e),
                    "final_action":ActionType.MINIMUM_SAFE.value,
                    "executed_by":"FALLBACK","events":bus.events}

        levels = self._levels(v, g, is_anomaly)
        confirmation = self._confirmation(v, d, irreversible, g, h)
        domain_action = self._domain_action(v, d)
        autonomy = self._autonomy(g, h, human_response_ms, v, d)
        memory_check = self._memory(prerequisite_type, memory_weight, is_anomaly, memory_history)
        final_action = self._resolve(v, domain_action, autonomy, memory_check, confirmation)
        rollback = self._rollback(irreversible, final_action, confirmation)

        if "PENDING" in final_action:
            ctx.state = ExecutionState.WAITING_HUMAN
            execution_result = {"status":"waiting_human_confirmation"}
        else:
            execution_result = {"status":"executed","action":final_action}
            ctx.state = ExecutionState.COMPLETED

        bus.emit("COMPLETED", {"final_action":final_action})

        return {
            "act_audit_id":act_id,
            "timestamp":datetime.now(timezone.utc).isoformat(),
            "version":"3.0-final",
            "state":ctx.state.value,
            "trigger":{"verdict":v.value,"G_score":g,
                       "source_audit_id":source_audit_id,"domain":d.value},
            "levels":levels, "confirmation":confirmation,
            "domain_action":domain_action, "autonomy":autonomy,
            "memory_check":memory_check, "rollback":rollback,
            "final_action":final_action,
            "execution_result":execution_result,
            "executed_by":autonomy["mode"],
            "events":bus.events
        }

    def _levels(self, v, G, is_anomaly):
        l1 = {Verdict.BLOCK:"STOP",Verdict.WARN:"SLOW",
              Verdict.FORCE_VERIFICATION:"FREEZE",
              Verdict.REVIEW:"SLOW",Verdict.ALLOW:"CONTINUE"}[v]
        l2_map = {Verdict.BLOCK:("FREEZE",True),
                  Verdict.FORCE_VERIFICATION:("MANDATORY_VERIFY",True),
                  Verdict.REVIEW:("ROUTE_TO_REVIEWER",True),
                  Verdict.WARN:("NOTIFY",G<0.5),
                  Verdict.ALLOW:("NOTIFY",False)}
        l2_action, l2_ex = l2_map.get(v, ("NOTIFY",False))
        l3_ex = is_anomaly or v in (Verdict.BLOCK, Verdict.FORCE_VERIFICATION)
        return {
            "L1":{"action":l1,"latency_ms":10,"executed":True},
            "L2":{"action":l2_action,"latency_ms":500,"executed":l2_ex},
            "L3":{"action":"TRANSFER_TO_HUMAN" if is_anomaly else "TRANSFER_TO_AUDIT",
                  "latency_ms":2000,"executed":l3_ex}}

    def _confirmation(self, v, d, irreversible, G, h):
        risk = self.policy.domain_risk.get(d.value, 0.3)
        high_risk = risk >= self.policy.high_risk_threshold
        required = irreversible or (high_risk and v==Verdict.BLOCK and h==HumanStatus.UNAVAILABLE)
        return {"required":required,
                "reason":"irreversible" if irreversible else
                         "high_risk_block_no_human" if required else "none",
                "high_risk_domain":high_risk,"domain_risk_score":risk}

    def _domain_action(self, v, d):
        soft = (d==Domain.MENTAL and v==Verdict.BLOCK)
        amap = {Verdict.BLOCK:ActionType.SOFT_BLOCK if soft else ActionType.HARD_BLOCK,
                Verdict.WARN:ActionType.WARN, Verdict.ALLOW:ActionType.ALLOW,
                Verdict.FORCE_VERIFICATION:ActionType.FORCE_VERIFY,
                Verdict.REVIEW:ActionType.ROUTE_TO_REVIEW}
        return {"domain":d.value,"action_type":amap[v].value,"soft_block":soft,
                "support_activated":d==Domain.MENTAL and v in (Verdict.BLOCK,Verdict.WARN),
                "escalation_contact":self.policy.domain_escalation.get(d.value,"none")}

    def _autonomy(self, G, h, response_ms, v, d):
        risk = self.policy.domain_risk.get(d.value, 0.3)
        if (v==Verdict.ALLOW and G>=self.policy.G_threshold_autonomous
                and h==HumanStatus.AVAILABLE and risk<self.policy.high_risk_threshold):
            mode = ExecutionMode.AUTONOMOUS
        elif h in (HumanStatus.AVAILABLE, HumanStatus.DELAYED):
            mode = ExecutionMode.SUPERVISED
        else:
            mode = ExecutionMode.FALLBACK
        return {"mode":mode.value,"G_score":G,"human_status":h.value,
                "response_time_ms":response_ms,"domain_risk":risk}

    def _memory(self, prereq, weight, is_anomaly, history):
        downgraded = (prereq=="TYPE1" and weight<self.policy.memory_downgrade_threshold)
        if downgraded: prereq = "TYPE2"
        failures = sum(1 for h in (history or []) if h.get("outcome")=="failure")
        boldness = "CAUTIOUS" if prereq=="TYPE3" or weight<self.policy.memory_stale_threshold or failures>2 else "CONFIDENT"
        return {"prerequisite_type":prereq,"weight_current":round(weight,4),
                "downgraded":downgraded,"action_boldness":boldness,
                "is_anomaly":is_anomaly,"prior_failures":failures,
                "memory_freshness":"fresh" if weight>0.7 else "stale" if weight<0.3 else "degraded"}

    def _resolve(self, v, domain_action, autonomy, memory_check, confirmation):
        action = domain_action["action_type"]
        mode = autonomy["mode"]
        boldness = memory_check["action_boldness"]
        if confirmation["required"]: return ActionType.PENDING_HUMAN.value
        if v==Verdict.BLOCK:
            if boldness=="CAUTIOUS" and action==ActionType.HARD_BLOCK.value and mode==ExecutionMode.SUPERVISED.value:
                return ActionType.SOFT_BLOCK.value
            return action
        if v==Verdict.FORCE_VERIFICATION: return ActionType.FORCE_VERIFY.value
        if v==Verdict.REVIEW: return ActionType.ROUTE_TO_REVIEW.value
        if mode==ExecutionMode.FALLBACK.value: return ActionType.MINIMUM_SAFE.value
        return action

    def _rollback(self, irreversible, final_action, confirmation):
        if "PENDING" in final_action:
            return {"possible":False,"reason":"action_not_yet_executed",
                    "irreversible":irreversible,"rollback_window_ms":0}
        non_rb = {ActionType.HARD_BLOCK.value, ActionType.MINIMUM_SAFE.value, ActionType.FORCE_VERIFY.value}
        possible = not irreversible and final_action not in non_rb
        return {"possible":possible,
                "reason":"rollback_available" if possible else "non_rollbackable",
                "irreversible":irreversible,
                "rollback_window_ms":self.policy.rollback_window_ms if possible else 0}

    def record_outcome(self, act_audit_id, status, lesson=""):
        evt = {"event_id":f"EVT-{str(uuid.uuid4())[:8]}",
               "act_audit_id":act_audit_id,
               "timestamp":datetime.now(timezone.utc).isoformat(),
               "status":status,"lesson":lesson}
        self.outcome_log.append(evt)
        return evt
