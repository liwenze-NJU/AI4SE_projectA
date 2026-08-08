import json
from decimal import Decimal
import httpx
from codeguard.action import Action, ActionKind, LLMResponse


class DeepSeekAdapter:
    """DeepSeek API adapter using OpenAI-compatible HTTP interface.

    Implements the LLMClient protocol. HTTP client is injectable for testing.
    """

    def __init__(self, api_key: str, model: str = "deepseek-v4-flash",
                 base_url: str = "https://api.deepseek.com/v1",
                 timeout: int = 60,
                 http_client: httpx.Client | None = None):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = http_client or httpx.Client(timeout=timeout)

    def __repr__(self) -> str:
        return f"DeepSeekAdapter(model={self._model!r}, base_url={self._base_url!r})"

    def generate(self, session_id: str, context: str) -> LLMResponse:
        try:
            response = self._client.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": context}],
                    "max_tokens": 4096,
                },
            )
        except httpx.TimeoutException:
            raise TimeoutError(
                f"DeepSeek API request timed out after {self._timeout}s"
            )
        except (httpx.ConnectError, httpx.NetworkError) as e:
            raise ValueError(f"Network error contacting DeepSeek API: {e}") from e

        if response.status_code != 200:
            error_msg = "Unknown error"
            try:
                error_body = response.json()
                error_msg = error_body.get("error", {}).get("message", error_msg)
            except Exception:
                error_msg = response.text[:200]
            raise ValueError(
                f"API error ({response.status_code}) from DeepSeek: {error_msg}"
            )

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise ValueError("Empty response from DeepSeek API")

        choice = choices[0]
        content = choice.get("message", {}).get("content", "")
        finish_reason = choice.get("finish_reason", "stop")
        model = data.get("model", self._model)
        usage = data.get("usage", {})
        token_used = usage.get("total_tokens", 0)

        action = self._parse_action(content)
        cost = self._estimate_cost(token_used)

        return LLMResponse(
            content=content,
            next_action=action,
            finish_reason=finish_reason,
            model=model,
            token_used=token_used,
            cost_used=cost,
            raw_response=response.text,
        )

    def _parse_action(self, content: str) -> Action:
        try:
            action_data = json.loads(content) if content else {}
        except json.JSONDecodeError:
            action_data = {"action": "complete", "summary": content[:100]}

        action_type = action_data.get("action", "complete")
        if action_type == "tool_call":
            return Action(
                kind=ActionKind.TOOL_CALL,
                tool_name=action_data.get("tool", ""),
                parameters=action_data.get("parameters", {}),
                raw=content,
            )
        return Action(
            kind=ActionKind.COMPLETE_REQUEST,
            summary=action_data.get("summary", ""),
            raw=content,
        )

    def _estimate_cost(self, token_used: int) -> Decimal:
        return Decimal(token_used * 2) / Decimal("1000000")