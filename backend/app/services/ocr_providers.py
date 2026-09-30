import base64
import json
import logging
from typing import Optional

import httpx

TIMEOUT = 120.0
KEEP_ALIVE = "10m"
MAX_TOKENS = 512

PROVIDER_TYPES = ("ollama", "anthropic", "openai")

DEFAULT_OLLAMA_URL = "http://10.10.10.10:11434"
DEFAULT_OLLAMA_MODEL = "qwen3.5:4b"


class ProviderUnreachable(Exception):
    """The provider could not be contacted. Callers may offer a different provider."""

    def __init__(self, label: str, detail: str = ""):
        self.label = label
        self.detail = detail
        super().__init__(f"{label} is unreachable")


class ProviderError(Exception):
    """The provider was reached but the request failed."""


def _strip_fences(raw: str) -> str:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return raw


def _parse_json(raw: str) -> dict:
    parsed = json.loads(_strip_fences(raw))
    if not isinstance(parsed, dict):
        raise json.JSONDecodeError("expected a JSON object", str(parsed), 0)
    return parsed


class OllamaProvider:
    """Native /api/chat. The only provider supporting schema, think and keep_alive."""

    type = "ollama"
    supports_preload = True

    def __init__(self, cfg: dict):
        self.label = cfg.get("label") or "Ollama"
        self.base_url = (cfg.get("base_url") or DEFAULT_OLLAMA_URL).rstrip("/")
        self.model = cfg.get("model") or DEFAULT_OLLAMA_MODEL

    def scan(self, image: bytes, media_type: str, prompt: str, schema: dict) -> dict:
        payload = {
            "model": self.model,
            "stream": False,
            "think": False,
            "keep_alive": KEEP_ALIVE,
            "format": schema,
            "options": {"num_predict": MAX_TOKENS},
            "messages": [{
                "role": "user",
                "content": prompt,
                "images": [base64.standard_b64encode(image).decode()],
            }],
        }
        try:
            r = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=TIMEOUT)
        except httpx.RequestError as exc:
            raise ProviderUnreachable(self.label, str(exc))
        if r.status_code >= 400:
            raise ProviderError(f"{self.label} returned {r.status_code}")
        return _parse_json(r.json().get("message", {}).get("content", ""))

    def preload(self) -> None:
        """Load the model without generating. Ollama does this for an empty prompt."""
        try:
            httpx.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "keep_alive": KEEP_ALIVE},
                timeout=TIMEOUT,
            )
        except httpx.RequestError as exc:
            raise ProviderUnreachable(self.label, str(exc))

    def test(self) -> dict:
        try:
            r = httpx.get(f"{self.base_url}/api/tags", timeout=10.0)
        except httpx.RequestError as exc:
            raise ProviderUnreachable(self.label, str(exc))
        if r.status_code >= 400:
            raise ProviderError(f"{self.label} returned {r.status_code}")
        names = [m.get("name") for m in r.json().get("models", [])]
        if self.model not in names:
            return {"success": False, "error": f"Model {self.model} is not present on this server."}
        return {"success": True, "detail": f"{self.model} available"}


class AnthropicProvider:
    """No schema parameter exists. Prompt-only, so fence stripping stays and
    the code-side validation layer carries the correctness guarantee."""

    type = "anthropic"
    supports_preload = False

    def __init__(self, cfg: dict):
        self.label = cfg.get("label") or "Anthropic"
        self.model = cfg.get("model") or "claude-sonnet-5"
        self.api_key = cfg.get("api_key") or ""

    def _client(self):
        if not self.api_key:
            raise ProviderError(f"{self.label} has no API key configured.")
        import anthropic
        return anthropic.Anthropic(api_key=self.api_key)

    def scan(self, image: bytes, media_type: str, prompt: str, schema: dict) -> dict:
        import anthropic
        client = self._client()
        try:
            msg = client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64.standard_b64encode(image).decode(),
                        }},
                        {"type": "text", "text": prompt},
                    ],
                }],
            )
        except anthropic.APIConnectionError as exc:
            raise ProviderUnreachable(self.label, str(exc))
        except anthropic.APIStatusError as exc:
            raise ProviderError(f"{self.label} returned {exc.status_code}")
        return _parse_json(msg.content[0].text)

    def preload(self) -> None:
        return None

    def test(self) -> dict:
        import anthropic
        client = self._client()
        try:
            client.messages.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
        except anthropic.APIConnectionError as exc:
            raise ProviderUnreachable(self.label, str(exc))
        except anthropic.APIStatusError:
            return {"success": False, "error": "Connection failed. Check the API key and model."}
        return {"success": True, "detail": self.model}


class OpenAICompatProvider:
    """Any /v1-compatible endpoint. response_format support varies, so a
    refusal falls back to prompt-only rather than failing the scan."""

    type = "openai"
    supports_preload = False

    def __init__(self, cfg: dict):
        self.label = cfg.get("label") or "OpenAI-compatible"
        self.base_url = (cfg.get("base_url") or "").rstrip("/")
        self.model = cfg.get("model") or ""
        self.api_key = cfg.get("api_key") or ""

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _body(self, image: bytes, media_type: str, prompt: str, schema: Optional[dict]) -> dict:
        b64 = base64.standard_b64encode(image).decode()
        body = {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }],
        }
        if schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "extraction", "schema": schema},
            }
        return body

    def scan(self, image: bytes, media_type: str, prompt: str, schema: dict) -> dict:
        url = f"{self.base_url}/chat/completions"
        try:
            r = httpx.post(url, json=self._body(image, media_type, prompt, schema),
                           headers=self._headers(), timeout=TIMEOUT)
            if r.status_code == 400:
                # Endpoint rejected the schema; retry without it and lean on validation.
                logging.info("%s refused response_format, retrying prompt-only", self.label)
                r = httpx.post(url, json=self._body(image, media_type, prompt, None),
                               headers=self._headers(), timeout=TIMEOUT)
        except httpx.RequestError as exc:
            raise ProviderUnreachable(self.label, str(exc))
        if r.status_code >= 400:
            raise ProviderError(f"{self.label} returned {r.status_code}")
        choices = r.json().get("choices") or []
        if not choices:
            raise ProviderError(f"{self.label} returned no choices")
        return _parse_json(choices[0].get("message", {}).get("content", ""))

    def preload(self) -> None:
        return None

    def test(self) -> dict:
        try:
            r = httpx.get(f"{self.base_url}/models", headers=self._headers(), timeout=10.0)
        except httpx.RequestError as exc:
            raise ProviderUnreachable(self.label, str(exc))
        if r.status_code >= 400:
            return {"success": False, "error": f"Endpoint returned {r.status_code}."}
        return {"success": True, "detail": self.model}


_BUILDERS = {
    "ollama": OllamaProvider,
    "anthropic": AnthropicProvider,
    "openai": OpenAICompatProvider,
}


def build_provider(cfg: dict):
    builder = _BUILDERS.get(cfg.get("type"))
    if builder is None:
        raise ProviderError(f"Unknown provider type: {cfg.get('type')}")
    return builder(cfg)
