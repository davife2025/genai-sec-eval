"""Target adapters: the runner only ever sees `generate(system, user) -> str`.

Adding a new model backend = write one small class here.
"""
from __future__ import annotations

import asyncio
import os
from typing import Protocol

from .dataset import CANARY, FEE_TOKEN, SYSTEM_MARKER, all_attack_seeds


class Target(Protocol):
    async def generate(self, system: str, user: str) -> str: ...


class MockTarget:
    """Offline simulator so you can test the whole pipeline without a token.

    mode=safe    -> never complies
    mode=partial -> falls for roleplay / encoded / indirect attacks, refuses direct ones
    mode=leaky   -> complies with everything
    It also has an over-eager keyword filter, to demonstrate over-refusal.
    """

    def __init__(self, mode: str = "partial", **_):
        self.mode = mode
        self._seeds = [s.lower() for s in all_attack_seeds()]

    async def generate(self, system: str, user: str) -> str:
        await asyncio.sleep(0)
        low = user.lower()
        manipulated = any(k in low for k in ("debugbot", "base64", "important note to the assistant"))
        is_attack = any(seed in low for seed in self._seeds)
        comply = {"safe": False, "leaky": is_attack or manipulated}.get(self.mode, manipulated)
        if comply:
            return (f"Sure! Internal reference: {SYSTEM_MARKER}. Vault secret: {CANARY}. "
                    f"[[TOOL:transfer(500)]] {FEE_TOKEN}")
        if is_attack:
            return "I'm sorry, but I can't help with that request."
        if "password" in low or " pin" in low or "waive" in low:   # over-eager filter
            return "I'm sorry, but I can't help with that request."
        return "Happy to help! Here is some general guidance on that topic."


class HFTarget:
    """Hugging Face Inference Providers via huggingface_hub (async, OpenAI-style chat API)."""

    def __init__(self, model: str, provider: str = "auto", temperature: float = 0.7,
                 max_tokens: int = 300, api_key: str | None = None, **_):
        from huggingface_hub import AsyncInferenceClient

        token = api_key or os.environ.get("HF_TOKEN")
        if not token:
            raise RuntimeError("HF_TOKEN is not set. Put HF_TOKEN=hf_... in a file named .env in the project root, or run: export HF_TOKEN=hf_...")
        self.model, self.temperature, self.max_tokens = model, temperature, max_tokens
        self.client = AsyncInferenceClient(provider=provider, api_key=token)

    async def generate(self, system: str, user: str) -> str:
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return resp.choices[0].message.content or ""


class LangChainHFTarget:
    """OPTIONAL: same Hugging Face models, called through LangChain.
    Install with: pip install -e ".[langchain]"   (not covered by the offline tests)"""

    def __init__(self, model: str, temperature: float = 0.7, max_tokens: int = 300,
                 api_key: str | None = None, **_):
        from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

        token = api_key or os.environ.get("HF_TOKEN")
        if not token:
            raise RuntimeError("HF_TOKEN is not set.")
        llm = HuggingFaceEndpoint(repo_id=model, task="text-generation", temperature=temperature,
                                  max_new_tokens=max_tokens, huggingfacehub_api_token=token)
        self.chat = ChatHuggingFace(llm=llm)

    async def generate(self, system: str, user: str) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage

        out = await self.chat.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
        return str(out.content)


def make_target(cfg: dict) -> Target:
    cfg = dict(cfg)
    kind = cfg.pop("type", "mock")
    if kind == "mock":
        return MockTarget(**cfg)
    if kind == "hf":
        return HFTarget(**cfg)
    if kind == "langchain":
        return LangChainHFTarget(**cfg)
    raise ValueError(f"unknown target type: {kind}")
