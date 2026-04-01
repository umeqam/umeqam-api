from typing import Any, Dict, List, Optional, Union
from .client import UMEQAMClient

class UMEQAMGuard:
    """
    UMEQAM guard for LangChain pipelines.
    
    Usage:
        from umeqam.langchain import UMEQAMGuard
        guard = UMEQAMGuard(api_key="your-key", domain="medical")
        safe_text = guard.check("some LLM output")
    """

    def __init__(self, api_key: str, domain: str, block_on_fail: bool = True):
        self.client = UMEQAMClient(api_key)
        self.domain = domain
        self.block_on_fail = block_on_fail

    def check(self, text: str) -> str:
        result = self.client.analyze(text, self.domain)
        verdict = result.get("overall_verdict", "REVIEW")
        if verdict == "FAIL" and self.block_on_fail:
            raise ValueError(
                "UMEQAM blocked: %s | flags: %s" % (
                    result.get("recommendation", "unsafe content"),
                    result.get("flags", [])
                )
            )
        return text

    def is_safe(self, text: str) -> bool:
        try:
            self.check(text)
            return True
        except ValueError:
            return False


try:
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.outputs import LLMResult

    class UMEQAMLangChainGuard(BaseCallbackHandler):
        """
        LangChain callback handler that intercepts LLM output
        and checks it with UMEQAM before returning to user.
        
        Usage:
            from umeqam.langchain import UMEQAMLangChainGuard
            guard = UMEQAMLangChainGuard(api_key="your-key", domain="medical")
            llm = ChatOpenAI(callbacks=[guard])
        """

        def __init__(self, api_key: str, domain: str, block_on_fail: bool = True):
            self.guard = UMEQAMGuard(api_key, domain, block_on_fail)

        def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
            for generations in response.generations:
                for gen in generations:
                    text = gen.text if hasattr(gen, "text") else str(gen)
                    self.guard.check(text)

except ImportError:
    pass