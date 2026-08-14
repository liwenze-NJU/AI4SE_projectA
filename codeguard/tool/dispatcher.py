from codeguard.tool import ToolResult
from codeguard.tool.registry import ToolRegistry
from codeguard.action import Action, NormalizedAction
from codeguard.secret import SecretRedactor
import uuid


class ToolDispatcher:
    """Dispatches actions to registered tool handlers with re-validation.

    Accepts both raw `Action` and `NormalizedAction` inputs; parameters are
    extracted through a single private helper so governance and execution
    always see the same parameter set.  Unknown tools and missing registries
    fail closed (KeyError), and handler exceptions are never coerced into
    success.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        workspace_root: str = "",
        secret_redactor: SecretRedactor = None,
    ):
        self._registry = registry
        self._workspace_root = workspace_root
        self._redactor = secret_redactor or SecretRedactor()

    def _extract_parameters(self, action) -> dict:
        """Single private helper for raw and normalized parameter extraction."""
        if isinstance(action, NormalizedAction):
            return dict(action.normalized_parameters or {})
        return dict(getattr(action, "parameters", None) or {})

    def dispatch(self, action: Action | NormalizedAction) -> ToolResult:
        if self._registry is None:
            raise KeyError("No tool registry configured; cannot dispatch")
        definition = self._registry.lookup(action.tool_name)
        params = self._extract_parameters(action)
        try:
            handler_result = definition.handler(
                params, workspace_root=str(self._workspace_root)
            )
            status = "SUCCESS"
            output = str(handler_result)
            error_category = None
        except PermissionError as e:
            status = "FAILURE"
            output = str(e)
            error_category = "WORKSPACE_VIOLATION"
        except FileNotFoundError as e:
            status = "FAILURE"
            output = str(e)
            error_category = "FILE_NOT_FOUND"
        except TimeoutError as e:
            status = "TIMEOUT"
            output = str(e)
            error_category = "TIMEOUT"
        except Exception as e:
            status = "ERROR"
            output = str(e)
            error_category = "UNEXPECTED"

        # Apply SecretRedactor before storing
        output = self._redactor.redact(output)

        return ToolResult(
            tool_name=action.tool_name,
            status=status,
            output_summary=output[:1000],
            diagnostics=[],
            exit_code=0 if status == "SUCCESS" else 1,
            changed_files=(
                [str(params.get("path", ""))]
                if definition.side_effect
                else []
            ),
            duration=0.0,
            truncated=len(output) > 1000,
            error_category=error_category,
            audit_id=str(uuid.uuid4()),
        )
