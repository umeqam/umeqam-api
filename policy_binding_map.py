POLICY_BINDING_MAP = {
    "medical": {
        "HIPAA": {"regulation":"HIPAA","primary_article":"45 CFR §164.502","violation_type":"Unauthorized disclosure of PHI","max_penalty_usd":1900000,"jurisdiction":"US","enforcer":"HHS Office for Civil Rights"},
        "FDA": {"regulation":"FDA 21 CFR Part 11","primary_article":"21 CFR §11.10","violation_type":"Non-compliant AI-generated medical content","max_penalty_usd":15000,"jurisdiction":"US","enforcer":"FDA"},
        "EU_AI_Act": {"regulation":"EU AI Act","primary_article":"Art.9","violation_type":"High-risk AI system without risk management","max_penalty_eur":30000000,"jurisdiction":"EU","enforcer":"National Market Surveillance Authority"},
        "GDPR": {"regulation":"GDPR","primary_article":"Art.9","violation_type":"Processing health data without lawful basis","max_penalty_eur":20000000,"jurisdiction":"EU","enforcer":"DPA"},
    },
    "legal": {
        "GDPR": {"regulation":"GDPR","primary_article":"Art.5(1)(a)","violation_type":"Unlawful automated processing in legal context","max_penalty_eur":20000000,"jurisdiction":"EU","enforcer":"DPA"},
        "EU_AI_Act": {"regulation":"EU AI Act","primary_article":"Art.13","violation_type":"Lack of transparency in AI-assisted legal decisions","max_penalty_eur":15000000,"jurisdiction":"EU","enforcer":"National Market Surveillance Authority"},
        "FCA": {"regulation":"FCA PRIN","primary_article":"PRIN 2.1.1(6)","violation_type":"Failure to treat customers fairly","jurisdiction":"UK","enforcer":"FCA"},
    },
    "finance": {
        "MiFID_II": {"regulation":"MiFID II","primary_article":"Art.24","violation_type":"Non-compliant investment advice / suitability failure","max_penalty_eur":5000000,"jurisdiction":"EU","enforcer":"ESMA"},
        "SEC": {"regulation":"SEC Rules","primary_article":"Rule 10b-5","violation_type":"Material misrepresentation in financial AI output","max_penalty_usd":1000000,"jurisdiction":"US","enforcer":"SEC"},
        "FINRA": {"regulation":"FINRA Rules","primary_article":"Rule 2010","violation_type":"Standards of commercial honor violation","max_penalty_usd":310000,"jurisdiction":"US","enforcer":"FINRA"},
        "FCA": {"regulation":"FCA COBS","primary_article":"COBS 4.2.1","violation_type":"Misleading financial communication","jurisdiction":"UK","enforcer":"FCA"},
        "BaFin": {"regulation":"BaFin/WpHG","primary_article":"§63 WpHG","violation_type":"Breach of conduct obligations for investment services","max_penalty_eur":5000000,"jurisdiction":"DE","enforcer":"BaFin"},
        "AMF": {"regulation":"AMF RG","primary_article":"Art.314-4","violation_type":"Failure to act in client best interest","max_penalty_eur":100000000,"jurisdiction":"FR","enforcer":"AMF"},
        "GDPR": {"regulation":"GDPR","primary_article":"Art.22","violation_type":"Automated financial decision without human oversight","max_penalty_eur":20000000,"jurisdiction":"EU","enforcer":"DPA"},
    },
    "mental": {
        "HIPAA": {"regulation":"HIPAA","primary_article":"45 CFR §164.502(a)","violation_type":"Unauthorized use of mental health PHI","max_penalty_usd":1900000,"jurisdiction":"US","enforcer":"HHS"},
        "GDPR": {"regulation":"GDPR","primary_article":"Art.9(1)","violation_type":"Processing mental health data without explicit consent","max_penalty_eur":20000000,"jurisdiction":"EU","enforcer":"DPA"},
        "EU_AI_Act": {"regulation":"EU AI Act","primary_article":"Art.5(1)(b)","violation_type":"AI exploiting psychological vulnerabilities","max_penalty_eur":35000000,"jurisdiction":"EU","enforcer":"National Market Surveillance Authority"},
    },
}

def get_policy_bindings(domain, regulators, risk_score):
    domain_map = POLICY_BINDING_MAP.get(domain, {})
    bindings = []
    for reg in regulators:
        if reg in domain_map:
            b = dict(domain_map[reg])
            b["regulator"] = reg
            if risk_score >= 75: b["triggered"] = True; b["severity"] = "HIGH"
            elif risk_score >= 50: b["triggered"] = True; b["severity"] = "MEDIUM"
            elif risk_score >= 25: b["triggered"] = False; b["severity"] = "LOW"
            else: b["triggered"] = False; b["severity"] = "NONE"
            bindings.append(b)
    return bindings

def get_top_binding(domain, regulators, risk_score):
    bindings = get_policy_bindings(domain, regulators, risk_score)
    triggered = [b for b in bindings if b.get("triggered")]
    return triggered[0] if triggered else (bindings[0] if bindings else {})
