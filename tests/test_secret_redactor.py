from codeguard.secret import SecretRedactor


def test_redact_api_key():
    redactor = SecretRedactor()
    result = redactor.redact("api_key = sk-1234567890abcdef")
    assert "sk-1234567890abcdef" not in result
    assert "sk-" in result  # prefix preserved, key redacted
    assert "api_key" in result


def test_redact_credential_pattern():
    redactor = SecretRedactor()
    result = redactor.redact("password = super-secret-123")
    assert "super-secret-123" not in result


def test_redact_path_to_relative():
    redactor = SecretRedactor(workspace_root="/home/user/project")
    result = redactor.redact("File at /home/user/project/src/main.py")
    assert "/home/user/project" not in result
    assert "src/main.py" in result


def test_redact_length_limit():
    redactor = SecretRedactor(max_length=50)
    result = redactor.redact("a" * 100)
    assert len(result) <= 50


def test_redact_preserves_normal_content():
    redactor = SecretRedactor()
    result = redactor.redact("This is normal code: print('hello')")
    assert result == "This is normal code: print('hello')"


def test_redact_multiple_api_keys():
    redactor = SecretRedactor()
    result = redactor.redact("key1=sk-abc key2=sk-xyz")
    assert "sk-abc" not in result
    assert "sk-xyz" not in result


def test_redact_hyphenated_api_key_fully():
    """Hyphenated credential tokens (DeepSeek-style keys) are redacted as
    one token; no tail segment may leak."""
    redactor = SecretRedactor()
    result = redactor.redact("key=sk-abcdef1234567890-secret-tail")
    assert "sk-abcdef1234567890-secret-tail" not in result
    assert "secret-tail" not in result
    assert "sk-***" in result


def test_redact_preserves_false_positives():
    """sk- embedded in words (flask, disk, risk) must not be redacted."""
    redactor = SecretRedactor()
    result = redactor.redact("flask-app disk-usage risk-assessment task-force")
    assert "flask-app" in result
    assert "disk-usage" in result
    assert "risk-assessment" in result


def test_redact_idempotent():
    """Applying redact twice produces the same result as once."""
    redactor = SecretRedactor()
    text = "api_key = sk-1234567890abcdef password = mypass"
    once = redactor.redact(text)
    twice = redactor.redact(once)
    assert once == twice