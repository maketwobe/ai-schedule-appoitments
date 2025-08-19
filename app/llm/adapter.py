from __future__ import annotations
import json
from typing import Type, TypeVar, Any, Dict
from pydantic import BaseModel, TypeAdapter
from app.config import settings

# Carrega .env se existir (garante OPENAI_API_KEY)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

T = TypeVar("T", bound=BaseModel)

def _json_to_python(payload: str | dict) -> Any:
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except Exception:
            return {"text": payload}
    return payload

def _validate_with_schema(schema: Type[T], payload: str | dict) -> T:
    adapter = TypeAdapter(schema)
    data = _json_to_python(payload)
    return adapter.validate_python(data)

class LLMAdapter:
    """
    Abstrai Pydantic AI; se não der certo, usa OpenAI JSON-mode.
    Compatível com versões recentes onde Agent.run NÃO aceita 'response_model'.
    """
    def __init__(self):
        self.model = settings.openai_model
        self._mode = "pydantic_ai"
        self._pai = None
        self._openai = None

        # tenta pydantic_ai
        try:
            import pydantic_ai  # type: ignore
            self._pai = pydantic_ai
        except Exception:
            self._mode = "openai"

        # prepara OpenAI client (para fallback ou uso direto)
        try:
            from openai import AsyncOpenAI  # type: ignore
            self._openai = AsyncOpenAI()
        except Exception:
            if self._mode == "openai":
                raise RuntimeError(
                    "Nenhuma engine LLM disponível. Instale 'pydantic-ai' ou 'openai' e defina OPENAI_API_KEY."
                )

    async def ask_dict(self, system: str, user: str) -> Dict[str, Any]:
        """
        Pede JSON e retorna um dict Python (sem validar schema).
        """
        # 1) tenta pydantic_ai
        if self._mode == "pydantic_ai" and self._pai is not None:
            try:
                from pydantic_ai import Agent  # type: ignore
                sys_prompt = system + "\nResponda ESTRITAMENTE em JSON válido, sem texto extra."
                agent = Agent(self.model, system_prompt=sys_prompt)
                result = await agent.run(user)
                text = getattr(result, "output_text", None) or str(result)
                return _json_to_python(text) or {}
            except Exception:
                pass

        # 2) Fallback OpenAI JSON-mode
        if self._openai is None:
            return {}
        r = await self._openai.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user + "\n\nResponda apenas com um JSON válido."},
            ],
        )
        content = r.choices[0].message.content or "{}"
        return _json_to_python(content) or {}

    async def ask_json(self, system: str, user: str, schema: Type[T]) -> T:
        """
        Mantido para compatibilidade: pede JSON e valida com schema Pydantic.
        """
        # Tenta pydantic_ai
        if self._mode == "pydantic_ai" and self._pai is not None:
            try:
                from pydantic_ai import Agent  # type: ignore
                sys_prompt = system + "\nResponda ESTRITAMENTE em JSON válido, sem texto extra."
                agent = Agent(self.model, system_prompt=sys_prompt)
                result = await agent.run(user)
                text = getattr(result, "output_text", None) or str(result)
                return _validate_with_schema(schema, text)
            except Exception:
                pass

        # Fallback: OpenAI JSON-mode
        if self._openai is None:
            raise RuntimeError("OpenAI client não inicializado e pydantic_ai falhou.")
        r = await self._openai.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user + "\n\nResponda apenas com um JSON válido."},
            ],
        )
        content = r.choices[0].message.content or "{}"
        return _validate_with_schema(schema, content)
