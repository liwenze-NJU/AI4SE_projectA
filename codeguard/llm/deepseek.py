import json
from decimal import Decimal
import httpx
from codeguard.action import Action, ActionKind, ActionParser, LLMResponse
from codeguard.secret import SecretRedactor

# ---------------------------------------------------------------------------
# Strict action protocol (system prompt)
# ---------------------------------------------------------------------------
# Exactly four action kinds are permitted. The provider MUST reply with one
# single JSON object and nothing else; prose outside the JSON is forbidden.
# Every response is re-parsed by ActionParser and `complete` still undergoes
# the final validation loop, so it must carry a real summary.

ACTION_PROTOCOL_PROMPT = (
    "You are CodeGuard, a governed coding agent. You must respond with "
    "EXACTLY ONE JSON object and nothing else — no prose outside the JSON, "
    "no markdown fences, no commentary before or after it. The JSON object "
    'must have an "action" field with exactly one of these four values:\n'
    '1. "tool_call" — invoke a registered tool. Required fields: '
    '"tool" (string, the tool name) and "parameters" (object).\n'
    '2. "assistant_message" — reply to the user. Required field: '
    '"message" (non-empty string).\n'
    '3. "request_user_input" — ask the user a question. Required field: '
    '"question" (non-empty string).\n'
    '4. "complete" — declare the task done. Required field: "summary" '
    "(non-empty string describing the outcome). A complete response still "
    "undergoes final validation; if validation fails the task continues, "
    "so do not declare completion prematurely.\n"
    "Respond with one of these four JSON objects only."
)


class DeepSeekAdapter:
    """DeepSeek API adapter using OpenAI-compatible HTTP interface.

    Implements the LLMClient protocol. HTTP client is injectable for testing.
    """

    def __init__(self, api_key: str, model: str = "deepseek-v4-flash",
                 base_url: str = "https://api.deepseek.com/v1",
                 timeout: int = 60,
                 http_client: httpx.Client | None = None,
                 secret_redactor: SecretRedactor | None = None):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = http_client or httpx.Client(timeout=timeout)
        self._redactor = secret_redactor if secret_redactor is not None \
            else SecretRedactor()

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
                    "messages": [
                        {"role": "system", "content": ACTION_PROTOCOL_PROMPT},
                        {"role": "user", "content": context},
                    ],
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
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Empty message from DeepSeek API (no action JSON)")
        try:
            return ActionParser().parse(content)
        except ValueError as e:
            # Never echo raw provider text into the error: it may carry
            # secrets. The message is redacted and the raise is NOT
            # chained (no `from e`) so the pre-redaction parser error —
            # which embeds raw provider content — cannot leak via
            # __cause__ in a traceback renderer.
            detail = self._redactor.redact(str(e))
            raise ValueError(f"Invalid action response from DeepSeek: {detail}")

    def _estimate_cost(self, token_used: int) -> Decimal:
        return Decimal(token_used * 2) / Decimal("1000000")
