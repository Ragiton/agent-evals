"""Safe, deterministic subprocess wrappers for the supported eval agents.

The public entry point is :func:`run_agent`::

    result = run_agent(
        {"agent": "claude-code", "model": "claude-sonnet-4-6"},
        workspace="/tmp/eval-workspace",
        prompt="Create the requested artifact.",
        output_path="/tmp/eval-workspace/stdout.txt",
        log_path="/tmp/eval-workspace/agent.log",
        timeout=1800,
    )

``agent_config`` may be an :class:`AgentConfig`, an agent name, or a mapping
with this schema::

    {
        "agent": "claude-code" | "codex" | "cursor-agent",  # required
        "model": str,                 # optional; locked default is used
        "provider": str,              # optional; must match the locked provider
        "executable": str,            # optional executable override
        "extra_args": [str, ...],     # optional additional argv elements
        "env": {str: str},             # optional environment overrides
        "timeout_seconds": number,    # optional positive timeout
        "max_budget_usd": number,     # claude-code only, optional
        "max_turns": int,             # claude-code only, optional
    }

The wrappers never invoke a shell.  They pass a list of arguments to
``subprocess.run`` and set ``cwd`` to the supplied workspace.  ``codex`` is
routed through Hermes because the installed Codex CLI does not select Hermes'
pooled ``openai-codex`` provider.  Its command is therefore ``hermes
--oneshot --model gpt-5.6-luna --provider openai-codex ...`` while the public
agent name remains ``codex``.

The return value is an :class:`InvocationResult`.  It contains the argv list,
workspace, model/provider, captured stdout/stderr, exit status, timeout/error
flags, and elapsed time.  It can be serialized with ``result.to_dict()``.
Invalid configuration raises :class:`AgentConfigError`; an unavailable
executable or failed subprocess is represented in the result so diagnostics
can still be written by the runner.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import datetime as _datetime
import json
import math
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Mapping, Sequence


SUPPORTED_AGENTS = ("claude-code", "codex", "cursor-agent")
LOCKED_MODELS = {
    "claude-code": "claude-sonnet-4-6",
    "codex": "gpt-5.6-luna",
    "cursor-agent": "composer-2.5",
}
LOCKED_PROVIDERS = {
    "claude-code": "anthropic",
    "codex": "openai-codex",
    "cursor-agent": "cursor",
}


class AgentConfigError(ValueError):
    """Raised when an agent configuration cannot be used safely."""


@dataclass(frozen=True)
class AgentConfig:
    """Normalized configuration for one supported agent invocation."""

    agent: str
    model: str | None = None
    provider: str | None = None
    executable: str | None = None
    extra_args: tuple[str, ...] = ()
    env: Mapping[str, str] = field(default_factory=dict)
    timeout_seconds: float | None = 1800.0
    max_budget_usd: float | None = None
    max_turns: int | None = None

    def normalized(self) -> "AgentConfig":
        """Return a validated config with locked defaults filled in."""

        agent = _normalize_agent_name(self.agent)
        model = self.model or LOCKED_MODELS[agent]
        provider = self.provider or LOCKED_PROVIDERS[agent]

        expected_model = LOCKED_MODELS[agent]
        if model != expected_model:
            raise AgentConfigError(
                f"{agent} requires model {expected_model!r}; got {model!r}"
            )
        expected_provider = LOCKED_PROVIDERS[agent]
        if provider != expected_provider:
            raise AgentConfigError(
                f"{agent} requires provider {expected_provider!r}; got {provider!r}"
            )

        executable = self.executable
        if executable is not None:
            if not isinstance(executable, str) or not executable.strip():
                raise AgentConfigError("executable must be a non-empty string")
            executable = executable.strip()

        extra_args = _validate_string_sequence(self.extra_args, "extra_args")
        env = _validate_env(self.env)
        timeout_seconds = _validate_timeout(self.timeout_seconds)

        if self.max_budget_usd is not None:
            if agent != "claude-code":
                raise AgentConfigError("max_budget_usd is only supported for claude-code")
            if isinstance(self.max_budget_usd, bool) or not isinstance(
                self.max_budget_usd, (int, float)
            ):
                raise AgentConfigError("max_budget_usd must be a non-negative number")
            if self.max_budget_usd < 0 or not math.isfinite(float(self.max_budget_usd)):
                raise AgentConfigError("max_budget_usd must be a finite non-negative number")
            max_budget_usd = float(self.max_budget_usd)
        else:
            max_budget_usd = None

        if self.max_turns is not None:
            if agent != "claude-code":
                raise AgentConfigError("max_turns is only supported for claude-code")
            if isinstance(self.max_turns, bool) or not isinstance(self.max_turns, int):
                raise AgentConfigError("max_turns must be a positive integer")
            if self.max_turns <= 0:
                raise AgentConfigError("max_turns must be a positive integer")

        return AgentConfig(
            agent=agent,
            model=model,
            provider=provider,
            executable=executable,
            extra_args=extra_args,
            env=env,
            timeout_seconds=timeout_seconds,
            max_budget_usd=max_budget_usd,
            max_turns=self.max_turns,
        )

    @classmethod
    def from_value(cls, value: "AgentConfig | Mapping[str, Any] | str") -> "AgentConfig":
        """Build and validate a config from the supported public forms."""

        if isinstance(value, cls):
            return value.normalized()
        if isinstance(value, str):
            return cls(agent=value).normalized()
        if not isinstance(value, Mapping):
            raise AgentConfigError(
                "agent_config must be an AgentConfig, agent name, or mapping"
            )

        allowed = {
            "agent",
            "name",
            "type",
            "model",
            "provider",
            "executable",
            "extra_args",
            "env",
            "timeout_seconds",
            "timeout",
            "max_budget_usd",
            "max_turns",
        }
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise AgentConfigError(
                f"unknown agent configuration field(s): {', '.join(map(str, unknown))}"
            )

        names = [value[key] for key in ("agent", "name", "type") if key in value]
        if not names:
            raise AgentConfigError("agent configuration requires an 'agent' field")
        if any(name != names[0] for name in names[1:]):
            raise AgentConfigError("agent, name, and type fields must agree")

        timeout_seconds = value.get("timeout_seconds", value.get("timeout", 1800.0))
        if "timeout_seconds" in value and "timeout" in value:
            if value["timeout_seconds"] != value["timeout"]:
                raise AgentConfigError("timeout and timeout_seconds fields must agree")

        extra_args = value.get("extra_args", ())
        if isinstance(extra_args, str):
            raise AgentConfigError("extra_args must be a sequence, not a shell string")

        return cls(
            agent=names[0],
            model=value.get("model"),
            provider=value.get("provider"),
            executable=value.get("executable"),
            extra_args=tuple(extra_args) if isinstance(extra_args, Sequence) else extra_args,
            env=value.get("env", {}),
            timeout_seconds=timeout_seconds,
            max_budget_usd=value.get("max_budget_usd"),
            max_turns=value.get("max_turns"),
        ).normalized()


@dataclass(frozen=True)
class InvocationResult:
    """Structured result of an agent subprocess invocation."""

    agent: str
    model: str
    provider: str
    command: tuple[str, ...]
    workspace: str
    prompt_chars: int
    stdout: str
    stderr: str
    exit_code: int | None
    timed_out: bool
    duration_seconds: float
    error: str | None = None
    output_path: str | None = None
    log_path: str | None = None
    started_at: str | None = None
    finished_at: str | None = None

    @property
    def returncode(self) -> int | None:
        """Compatibility alias for ``subprocess.CompletedProcess.returncode``."""

        return self.exit_code

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and self.error is None

    @property
    def success(self) -> bool:
        """Short alias useful to callers and JSON-oriented runners."""

        return self.succeeded

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation with stable field names."""

        result = asdict(self)
        result["command"] = list(self.command)
        result["returncode"] = self.returncode
        result["success"] = self.success
        return result

    def write_json(self, path: str | os.PathLike[str]) -> Path:
        """Write this result as indented JSON and return the destination path."""

        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return destination


def run_agent(
    agent_config: AgentConfig | Mapping[str, Any] | str,
    workspace: str | os.PathLike[str],
    prompt: str | None = None,
    spec: str | os.PathLike[str] | Mapping[str, Any] | None = None,
    output_path: str | os.PathLike[str] | None = None,
    log_path: str | os.PathLike[str] | None = None,
    *,
    timeout: float | None = None,
) -> InvocationResult:
    """Invoke one configured agent and capture its complete result.

    ``prompt`` is the exact text sent to the agent.  If it is omitted, ``spec``
    may be a mapping containing a string ``prompt`` field, a path to a text/YAML
    spec containing a ``prompt:`` field, or a plain text file.  When both are
    supplied, the explicit ``prompt`` wins; ``spec`` is accepted for runners
    that keep the parsed spec and prompt together.

    ``output_path`` receives stdout.  ``log_path`` receives a deterministic
    combined stdout/stderr log.  Both destinations are optional and are
    created, including their parent directories, when supplied.  The return
    value is always an :class:`InvocationResult` for a valid configuration,
    including timeout and executable-not-found failures.
    """

    config = AgentConfig.from_value(agent_config)
    workspace_path = _prepare_workspace(workspace)
    prompt_text = _resolve_prompt(prompt, spec)
    effective_timeout = config.timeout_seconds if timeout is None else _validate_timeout(timeout)

    command, prompt_via_stdin = _build_command(config, workspace_path, prompt_text)
    process_env = os.environ.copy()
    process_env.update(config.env)

    started = _utc_now()
    started_monotonic = time.monotonic()
    stdout = ""
    stderr = ""
    exit_code: int | None = None
    timed_out = False
    error: str | None = None

    try:
        completed = subprocess.run(
            list(command),
            input=prompt_text if prompt_via_stdin else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(workspace_path),
            env=process_env,
            timeout=effective_timeout,
            check=False,
        )
        stdout = _as_text(completed.stdout)
        stderr = _as_text(completed.stderr)
        exit_code = completed.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = 124
        stdout = _as_text(exc.stdout)
        stderr = _as_text(exc.stderr)
        error = f"agent timed out after {effective_timeout:g} seconds"
    except FileNotFoundError as exc:
        exit_code = 127
        error = f"agent executable not found: {command[0]!r}"
        stderr = str(exc)
    except PermissionError as exc:
        exit_code = 126
        error = f"agent executable is not executable: {command[0]!r}"
        stderr = str(exc)
    except OSError as exc:
        exit_code = 126
        error = f"could not launch agent executable {command[0]!r}: {exc}"
        stderr = str(exc)

    finished = _utc_now()
    duration = round(max(0.0, time.monotonic() - started_monotonic), 6)
    written_output = _write_output(output_path, stdout)
    written_log = _write_log(log_path, stdout, stderr, error)

    return InvocationResult(
        agent=config.agent,
        model=config.model or LOCKED_MODELS[config.agent],
        provider=config.provider or LOCKED_PROVIDERS[config.agent],
        command=tuple(command),
        workspace=str(workspace_path),
        prompt_chars=len(prompt_text),
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        timed_out=timed_out,
        duration_seconds=duration,
        error=error,
        output_path=str(written_output) if written_output else None,
        log_path=str(written_log) if written_log else None,
        started_at=started,
        finished_at=finished,
    )


def run_claude_code(
    agent_config: AgentConfig | Mapping[str, Any] | str,
    workspace: str | os.PathLike[str],
    prompt: str | None = None,
    spec: str | os.PathLike[str] | Mapping[str, Any] | None = None,
    output_path: str | os.PathLike[str] | None = None,
    log_path: str | os.PathLike[str] | None = None,
    *,
    timeout: float | None = None,
) -> InvocationResult:
    """Invoke the Claude Code wrapper after requiring ``claude-code`` config."""

    return _run_named("claude-code", agent_config, workspace, prompt, spec, output_path, log_path, timeout)


def run_codex(
    agent_config: AgentConfig | Mapping[str, Any] | str,
    workspace: str | os.PathLike[str],
    prompt: str | None = None,
    spec: str | os.PathLike[str] | Mapping[str, Any] | None = None,
    output_path: str | os.PathLike[str] | None = None,
    log_path: str | os.PathLike[str] | None = None,
    *,
    timeout: float | None = None,
) -> InvocationResult:
    """Invoke Codex through Hermes' pooled ``openai-codex`` provider."""

    return _run_named("codex", agent_config, workspace, prompt, spec, output_path, log_path, timeout)


def run_cursor_agent(
    agent_config: AgentConfig | Mapping[str, Any] | str,
    workspace: str | os.PathLike[str],
    prompt: str | None = None,
    spec: str | os.PathLike[str] | Mapping[str, Any] | None = None,
    output_path: str | os.PathLike[str] | None = None,
    log_path: str | os.PathLike[str] | None = None,
    *,
    timeout: float | None = None,
) -> InvocationResult:
    """Invoke Cursor Agent using the locked ``composer-2.5`` model."""

    return _run_named("cursor-agent", agent_config, workspace, prompt, spec, output_path, log_path, timeout)


# Explicit aliases make the common interface discoverable to runners that use
# "invoke" rather than "run" naming.
invoke_agent = run_agent
invoke_claude_code = run_claude_code
invoke_codex = run_codex
invoke_cursor_agent = run_cursor_agent


def _run_named(
    expected_agent: str,
    agent_config: AgentConfig | Mapping[str, Any] | str,
    workspace: str | os.PathLike[str],
    prompt: str | None,
    spec: str | os.PathLike[str] | Mapping[str, Any] | None,
    output_path: str | os.PathLike[str] | None,
    log_path: str | os.PathLike[str] | None,
    timeout: float | None,
) -> InvocationResult:
    config = AgentConfig.from_value(agent_config)
    if config.agent != expected_agent:
        raise AgentConfigError(
            f"{expected_agent} wrapper received configuration for {config.agent}"
        )
    return run_agent(config, workspace, prompt, spec, output_path, log_path, timeout=timeout)


def _normalize_agent_name(value: Any) -> str:
    if not isinstance(value, str) or value not in SUPPORTED_AGENTS:
        supported = ", ".join(SUPPORTED_AGENTS)
        raise AgentConfigError(f"agent must be one of {supported}; got {value!r}")
    return value


def _validate_string_sequence(value: Any, field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise AgentConfigError(f"{field_name} must be a sequence of strings")
    if any(not isinstance(item, str) or not item for item in value):
        raise AgentConfigError(f"{field_name} must contain only non-empty strings")
    return tuple(value)


def _validate_env(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise AgentConfigError("env must be a mapping of string names to string values")
    if any(not isinstance(key, str) or not key for key in value):
        raise AgentConfigError("env keys must be non-empty strings")
    if any(not isinstance(item, str) for item in value.values()):
        raise AgentConfigError("env values must be strings")
    return dict(value)


def _validate_timeout(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AgentConfigError("timeout must be a positive number of seconds or null")
    if value <= 0 or not math.isfinite(float(value)):
        raise AgentConfigError("timeout must be a positive number of seconds or null")
    return float(value)


def _prepare_workspace(value: str | os.PathLike[str]) -> Path:
    if not isinstance(value, (str, os.PathLike)):
        raise AgentConfigError("workspace must be a filesystem path")
    workspace = Path(value).expanduser().resolve()
    if workspace.exists() and not workspace.is_dir():
        raise AgentConfigError(f"workspace is not a directory: {workspace}")
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def _resolve_prompt(
    prompt: str | None,
    spec: str | os.PathLike[str] | Mapping[str, Any] | None,
) -> str:
    if prompt is not None:
        if not isinstance(prompt, str):
            raise AgentConfigError("prompt must be a string")
        if prompt == "":
            raise AgentConfigError("prompt must not be empty")
        return prompt

    if spec is None:
        raise AgentConfigError("one of prompt or spec must be supplied")

    if isinstance(spec, Mapping):
        candidate = spec.get("prompt")
        if not isinstance(candidate, str) or not candidate:
            raise AgentConfigError("spec mapping must contain a non-empty string 'prompt'")
        return candidate

    if not isinstance(spec, (str, os.PathLike)):
        raise AgentConfigError("spec must be a mapping or filesystem path")
    spec_path = Path(spec).expanduser()
    if not spec_path.is_file():
        raise AgentConfigError(f"spec file not found: {spec_path}")
    text = spec_path.read_text(encoding="utf-8")
    if not text:
        raise AgentConfigError(f"spec file is empty: {spec_path}")

    # Avoid importing PyYAML at module import time.  JSON specs are handled
    # exactly, and YAML is parsed lazily when the runner asks for a spec file.
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, Mapping) and isinstance(parsed.get("prompt"), str):
        return parsed["prompt"]

    # The project specs are YAML.  Keep the dependency lazy so importing this
    # module remains possible in a minimal test environment, while still
    # extracting block/multiline prompts when PyYAML is available to the runner.
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError:
        yaml = None
    if yaml is not None:
        try:
            parsed = yaml.safe_load(text)
        except Exception:
            parsed = None
        if isinstance(parsed, Mapping) and isinstance(parsed.get("prompt"), str):
            return parsed["prompt"]

    for line in text.splitlines():
        if line.startswith("prompt:"):
            candidate = line.partition(":")[2].strip()
            if candidate and candidate not in {"|", ">"}:
                return candidate.strip("'\"")
    return text


def _build_command(
    config: AgentConfig,
    workspace: Path,
    prompt: str,
) -> tuple[tuple[str, ...], bool]:
    """Build argv and indicate whether prompt must be sent on stdin."""

    if config.agent == "claude-code":
        executable = config.executable or "claude"
        args: list[str] = [
            executable,
            "--print",
            "--permission-mode",
            "bypassPermissions",
            "--model",
            config.model or LOCKED_MODELS[config.agent],
            "--add-dir",
            str(workspace),
        ]
        if config.max_turns is not None:
            args.extend(["--max-turns", str(config.max_turns)])
        if config.max_budget_usd is not None:
            args.extend(["--max-budget-usd", str(config.max_budget_usd)])
        args.extend(config.extra_args)
        return tuple(args), True

    if config.agent == "codex":
        # Hermes is the provider router for this project.  Unlike the standalone
        # Codex CLI, it accepts --provider openai-codex and uses the pooled OAuth
        # credential without reading ~/.codex/auth.json.
        executable = config.executable or "hermes"
        args = [
            executable,
            "--oneshot",
            "--model",
            config.model or LOCKED_MODELS[config.agent],
            "--provider",
            config.provider or LOCKED_PROVIDERS[config.agent],
            "--no-restore-cwd",
            "--ignore-rules",
        ]
        args.extend(config.extra_args)
        args.append(prompt)
        return tuple(args), False

    if config.agent == "cursor-agent":
        executable = config.executable or "cursor-agent"
        args = [
            executable,
            "--print",
            "--output-format",
            "json",
            "--model",
            config.model or LOCKED_MODELS[config.agent],
            "--workspace",
            str(workspace),
            "--trust",
        ]
        args.extend(config.extra_args)
        return tuple(args), True

    # AgentConfig.normalized() makes this unreachable, but retaining the guard
    # keeps this helper safe if a new agent is added without command support.
    raise AgentConfigError(f"no command builder exists for agent {config.agent!r}")


def _write_output(path: str | os.PathLike[str] | None, stdout: str) -> Path | None:
    if path is None:
        return None
    destination = Path(path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(stdout, encoding="utf-8")
    return destination


def _write_log(
    path: str | os.PathLike[str] | None,
    stdout: str,
    stderr: str,
    error: str | None,
) -> Path | None:
    if path is None:
        return None
    destination = Path(path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    sections = ["[stdout]", stdout, "[stderr]", stderr]
    if error:
        sections.extend(["[error]", error])
    destination.write_text("\n".join(sections).rstrip() + "\n", encoding="utf-8")
    return destination


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _utc_now() -> str:
    return _datetime.datetime.now(_datetime.timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = [
    "AgentConfig",
    "AgentConfigError",
    "InvocationResult",
    "LOCKED_MODELS",
    "LOCKED_PROVIDERS",
    "SUPPORTED_AGENTS",
    "invoke_agent",
    "invoke_claude_code",
    "invoke_codex",
    "invoke_cursor_agent",
    "run_agent",
    "run_claude_code",
    "run_codex",
    "run_cursor_agent",
]
