import re


class SecretRedactor:
    """Redacts sensitive information from output strings.

    Applied before storing in logs, traces, ToolResult, Feedback, Memory.
    Implemented early so all output components use it from first version.

    Redaction rules (applied in order):
    1. sk- API keys: preserve "sk-" prefix, redact the key body.
       Matches the full credential-like token after "sk-": one or more
       alphanumeric segments joined by hyphens (DeepSeek-style keys such
       as sk-abcdef1234567890-secret-tail are redacted as one token, so
       a short first segment no longer leaks the tail). False positives
       inside words (flask, disk, risk, task) are unaffected by the
       word boundary.
    2. Generic credential patterns (api_key=, password=, secret=, token=):
       if the value starts with "sk-", output "sk-***" (preserving the
       already-redacted prefix from step 1); otherwise output "***".
    3. Workspace root path: replaced with "." for portability.
    4. Length limit: if result exceeds max_length, truncate and append
       "...[truncated]". The suffix is counted within max_length so the
       final output never exceeds max_length.
    """

    def __init__(self, workspace_root: str = "", max_length: int = 10000):
        self._workspace_root = workspace_root
        self._max_length = max_length

    def _redact_sk_key(self, match):
        return match.group(1) + "***"

    def _redact_generic_value(self, match):
        value = match.group(2)
        if value.startswith("sk-"):
            return match.group(1) + "sk-***"
        return match.group(1) + "***"

    def redact(self, text: str) -> str:
        if not text:
            return text
        # Step 1: sk- API keys (prefix preserved, key body redacted).
        # The whole credential-like token — including hyphenated tails —
        # is matched as one unit so no tail segment leaks.
        text = re.sub(
            r'\b(sk-)[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*',
            self._redact_sk_key,
            text,
        )
        # Step 2: Generic credential patterns
        for field in ['api_key', 'password', 'secret', 'token']:
            text = re.sub(
                rf'({field}\s*[=:]\s*)(\S+)',
                self._redact_generic_value,
                text,
            )
        # Step 3: Workspace root normalization
        if self._workspace_root:
            text = text.replace(self._workspace_root, ".")
        # Step 4: Length limit (suffix counted within max_length)
        if len(text) > self._max_length:
            suffix = "...[truncated]"
            text = text[:self._max_length - len(suffix)] + suffix
        return text