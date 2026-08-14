import json
import pytest
from decimal import Decimal
import httpx
from codeguard.llm.deepseek import DeepSeekAdapter
from codeguard.action import Action, ActionKind, LLMResponse


class TestDeepSeekAdapter:
    def test_adapter_success_tool_call(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "choices": [{
                    "finish_reason": "tool_calls",
                    "message": {
                        "content": '{"action": "tool_call", "tool": "read_file", "parameters": {"path": "test.py"}}'
                    }
                }],
                "model": "deepseek-v4-flash",
                "usage": {"total_tokens": 10, "prompt_tokens": 5, "completion_tokens": 5},
            })

        client = httpx.Client(transport=httpx.MockTransport(mock_handler))
        adapter = DeepSeekAdapter(api_key="sk-test-key-12345", http_client=client)
        response = adapter.generate(session_id="s1", context="test")

        assert response.finish_reason == "tool_calls"
        assert response.next_action.kind == ActionKind.TOOL_CALL
        assert response.next_action.tool_name == "read_file"
        assert response.next_action.parameters == {"path": "test.py"}
        assert response.model == "deepseek-v4-flash"
        assert response.token_used == 10
        assert isinstance(response.cost_used, Decimal)

    def test_adapter_success_complete_request(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "choices": [{
                    "finish_reason": "stop",
                    "message": {
                        "content": '{"action": "complete", "summary": "task done"}'
                    }
                }],
                "model": "deepseek-v4-flash",
                "usage": {"total_tokens": 8},
            })

        client = httpx.Client(transport=httpx.MockTransport(mock_handler))
        adapter = DeepSeekAdapter(api_key="sk-test-key", http_client=client)
        response = adapter.generate(session_id="s1", context="test")

        assert response.finish_reason == "stop"
        assert response.next_action.kind == ActionKind.COMPLETE_REQUEST
        assert response.next_action.summary == "task done"
        assert response.model == "deepseek-v4-flash"

    def test_adapter_success_assistant_message(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "choices": [{
                    "finish_reason": "stop",
                    "message": {
                        "content": '{"action": "assistant_message", "message": "hello user"}'
                    }
                }],
                "model": "deepseek-v4-flash",
                "usage": {"total_tokens": 6},
            })

        client = httpx.Client(transport=httpx.MockTransport(mock_handler))
        adapter = DeepSeekAdapter(api_key="sk-test-key", http_client=client)
        response = adapter.generate(session_id="s1", context="test")

        assert response.next_action.kind == ActionKind.ASSISTANT_MESSAGE
        assert response.next_action.message == "hello user"

    def test_adapter_success_request_user_input(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "choices": [{
                    "finish_reason": "stop",
                    "message": {
                        "content": '{"action": "request_user_input", "question": "which file should I read?"}'
                    }
                }],
                "model": "deepseek-v4-flash",
                "usage": {"total_tokens": 7},
            })

        client = httpx.Client(transport=httpx.MockTransport(mock_handler))
        adapter = DeepSeekAdapter(api_key="sk-test-key", http_client=client)
        response = adapter.generate(session_id="s1", context="test")

        assert response.next_action.kind == ActionKind.REQUEST_USER_INPUT
        assert response.next_action.question == "which file should I read?"

    def test_adapter_api_error_400(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={
                "error": {"message": "Invalid API key"}
            })

        client = httpx.Client(transport=httpx.MockTransport(mock_handler))
        adapter = DeepSeekAdapter(api_key="sk-bad-key", http_client=client)
        with pytest.raises(ValueError, match="API error"):
            adapter.generate(session_id="s1", context="test")

    def test_adapter_api_error_500(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="Internal Server Error")

        client = httpx.Client(transport=httpx.MockTransport(mock_handler))
        adapter = DeepSeekAdapter(api_key="sk-test-key", http_client=client)
        with pytest.raises(ValueError, match="API error"):
            adapter.generate(session_id="s1", context="test")

    def test_adapter_timeout(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("Request timed out")

        client = httpx.Client(transport=httpx.MockTransport(mock_handler))
        adapter = DeepSeekAdapter(api_key="sk-test-key", http_client=client)
        with pytest.raises(TimeoutError, match="timed out"):
            adapter.generate(session_id="s1", context="test")

    def test_adapter_empty_choices(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "choices": [],
                "model": "deepseek-v4-flash",
                "usage": {"total_tokens": 0},
            })

        client = httpx.Client(transport=httpx.MockTransport(mock_handler))
        adapter = DeepSeekAdapter(api_key="sk-test-key", http_client=client)
        with pytest.raises(ValueError, match="Empty response"):
            adapter.generate(session_id="s1", context="test")

    def test_adapter_missing_content_field_raises(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "choices": [{"finish_reason": "stop", "message": {}}],
                "model": "deepseek-v4-flash",
                "usage": {"total_tokens": 1},
            })

        client = httpx.Client(transport=httpx.MockTransport(mock_handler))
        adapter = DeepSeekAdapter(api_key="sk-test-key", http_client=client)
        with pytest.raises(ValueError, match="action") as exc_info:
            adapter.generate(session_id="s1", context="test")
        # The chained exception must not retain the raw provider text.
        assert exc_info.value.__cause__ is None

    def test_adapter_malformed_json_content_raises(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": "not valid json {{{"}
                }],
                "model": "deepseek-v4-flash",
                "usage": {"total_tokens": 3},
            })

        client = httpx.Client(transport=httpx.MockTransport(mock_handler))
        adapter = DeepSeekAdapter(api_key="sk-test-key", http_client=client)
        with pytest.raises(ValueError, match="action") as exc_info:
            adapter.generate(session_id="s1", context="test")
        # The chained exception must not retain the raw provider text
        # in __cause__ (a traceback renderer would surface it).
        assert exc_info.value.__cause__ is None

    def test_adapter_malformed_error_message_is_redacted(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": "leaked sk-super-secret-key-9999 prose"}
                }],
                "model": "deepseek-v4-flash",
                "usage": {"total_tokens": 3},
            })

        client = httpx.Client(transport=httpx.MockTransport(mock_handler))
        adapter = DeepSeekAdapter(api_key="sk-secret-key-12345", http_client=client)
        with pytest.raises(ValueError) as exc_info:
            adapter.generate(session_id="s1", context="test")
        err = str(exc_info.value)
        assert "sk-super-secret-key-9999" not in err
        assert "sk-super-secret-key" not in err
        assert "sk-secret-key-12345" not in err

    def test_adapter_network_error(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        client = httpx.Client(transport=httpx.MockTransport(mock_handler))
        adapter = DeepSeekAdapter(api_key="sk-test-key", http_client=client)
        with pytest.raises(ValueError, match="Network error"):
            adapter.generate(session_id="s1", context="test")

    def test_adapter_llm_response_content(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": '{"action": "complete", "summary": "task finished"}'}
                }],
                "model": "deepseek-v4-flash",
                "usage": {"total_tokens": 5},
            })

        client = httpx.Client(transport=httpx.MockTransport(mock_handler))
        adapter = DeepSeekAdapter(api_key="sk-test-key", http_client=client)
        response = adapter.generate(session_id="s1", context="test")
        assert response.content == '{"action": "complete", "summary": "task finished"}'
        assert response.token_used == 5

    def test_adapter_request_has_system_protocol_message(self):
        captured_payload = {}

        def mock_handler(request: httpx.Request) -> httpx.Response:
            captured_payload.update(json.loads(request.content))
            return httpx.Response(200, json={
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": '{"action": "complete", "summary": "task done"}'}
                }],
                "model": "deepseek-v4-flash",
                "usage": {"total_tokens": 2},
            })

        client = httpx.Client(transport=httpx.MockTransport(mock_handler))
        adapter = DeepSeekAdapter(api_key="sk-test-key", http_client=client)
        adapter.generate(session_id="s1", context="user says hello")

        messages = captured_payload["messages"]
        assert messages[0]["role"] == "system"
        assert messages[1] == {"role": "user", "content": "user says hello"}
        for expected in ["tool_call", "assistant_message",
                         "request_user_input", "complete"]:
            assert expected in messages[0]["content"]
        # T8-FIX5: the prompt must declare assistant_message TERMINAL —
        # final validation follows immediately and no further LLM call is
        # made, so intermediate progress must use tool events instead.
        content = messages[0]["content"]
        assert "TERMINAL" in content
        assert "final validation" in content.lower()
        assert "never use it for intermediate" in content.lower()

    def test_adapter_api_key_not_in_repr(self):
        adapter = DeepSeekAdapter(api_key="sk-secret-key-12345")
        r = repr(adapter)
        assert "sk-secret-key-12345" not in r

    def test_adapter_api_key_not_in_exception(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={
                "error": {"message": "Authentication failed"}
            })

        client = httpx.Client(transport=httpx.MockTransport(mock_handler))
        adapter = DeepSeekAdapter(api_key="sk-secret-key-12345", http_client=client)
        with pytest.raises(ValueError) as exc_info:
            adapter.generate(session_id="s1", context="test")
        assert "sk-secret-key-12345" not in str(exc_info.value)

    def test_adapter_default_client_created(self):
        adapter = DeepSeekAdapter(api_key="sk-test-key")
        assert adapter._client is not None
        assert isinstance(adapter._client, httpx.Client)

    def test_adapter_uses_correct_endpoint(self):
        captured_url = []

        def mock_handler(request: httpx.Request) -> httpx.Response:
            captured_url.append(str(request.url))
            return httpx.Response(200, json={
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": '{"action": "complete", "summary": "ok"}'}
                }],
                "model": "deepseek-v4-flash",
                "usage": {"total_tokens": 1},
            })

        client = httpx.Client(transport=httpx.MockTransport(mock_handler))
        adapter = DeepSeekAdapter(api_key="sk-test-key", http_client=client)
        adapter.generate(session_id="s1", context="test")
        assert "/chat/completions" in captured_url[0]

    def test_adapter_auth_header_set(self):
        captured_headers = []

        def mock_handler(request: httpx.Request) -> httpx.Response:
            captured_headers.append(dict(request.headers))
            return httpx.Response(200, json={
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": '{"action": "complete", "summary": "ok"}'}
                }],
                "model": "deepseek-v4-flash",
                "usage": {"total_tokens": 1},
            })

        client = httpx.Client(transport=httpx.MockTransport(mock_handler))
        adapter = DeepSeekAdapter(api_key="sk-test-key", http_client=client)
        adapter.generate(session_id="s1", context="test")
        assert "authorization" in captured_headers[0]
        assert captured_headers[0]["authorization"] == "Bearer sk-test-key"