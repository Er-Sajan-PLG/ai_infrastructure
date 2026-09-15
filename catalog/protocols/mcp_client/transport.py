"""The stdio transport: spawn a child, frame its stdout, drain its stderr.

The ``Transport`` protocol is the seam (ADR-0009 D-2). This module is the one
implementation Phase 1 ships, and it exists so that every *protocol* test can run
against an in-memory double while the process-lifecycle behaviour is tested
separately, against a real child, for exactly what it owns.

Three details here are copied from a structural reference (``mark3labs/mcp-go``)
because a naive implementation gets them wrong **silently**, on a cooperative
server, with no failing test:

1. **``stderr`` is drained continuously**, on a daemon thread, into a bounded
   drop-oldest ring. Without the drain the OS pipe fills (about 64 KiB) and the
   child blocks writing to it — deadlocking the whole channel. The bound stops a
   chatty server from exhausting memory.
2. **``stderr`` is never an error signal.** The spec says clients *"SHOULD NOT
   assume stderr output indicates error conditions."* It is kept only so a
   *process death* can be explained.
3. **Shutdown escalates through the process group.** ``start_new_session=True``
   puts the child in its own session, and the kill targets the group, so a
   wrapper script's grandchildren are reaped too. Neither the Go nor the
   TypeScript client does this, and both leak descendants.

No shell, ever. The child is spawned from an argv array with ``shell=False`` so a
``;`` in a config value is an argument rather than a command.
"""

from __future__ import annotations

import contextlib
import os
import select
import signal
import subprocess
import threading
import time
from collections import deque
from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

from .errors import MCPTransportError
from .framing import MAX_LINE_BYTES

__all__ = ["STDERR_RING_BYTES", "StdioTransport", "Transport"]

# Drop-oldest ring bound for stderr. The Go client uses 64 KiB for the same
# reason; the number is ours, and it is stated rather than implied (ADR-0009 D-10).
STDERR_RING_BYTES = 64 * 1024


def _spawn(
    command: str,
    args: Sequence[str],
    cwd: str | None,
    env: dict[str, str] | None,
) -> subprocess.Popen[bytes]:
    """Spawn the server, never through a shell.

    Written with explicit keyword arguments rather than a ``**dict`` so the
    ``Popen`` overload resolves and the return type is provably
    ``Popen[bytes]`` -- a dict typed ``object`` matches no overload, which
    silently degrades every downstream attribute access to ``Any``.

    ``shell`` is False and the argv is a list, so there is no shell to interpret
    a ``;`` and no string to interpolate into. That is the *opposite* of the
    untrusted-input case S603 warns about -- see the test asserting a ``;`` in an
    argument reaches the child literally (ADR-0009 D-2's spawn posture).
    """
    common: dict[str, Any] = {
        "stdin": subprocess.PIPE,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "shell": False,
        "cwd": cwd,
        "env": env,
        "bufsize": 0,
    }
    try:
        if os.name == "posix":
            # Own session => own process group, so a group kill reaches every
            # descendant even after the direct child exits.
            common["start_new_session"] = True
        return subprocess.Popen([command, *args], **common)  # noqa: S603
    except OSError as exc:
        raise MCPTransportError(f"could not spawn {command!r}: {exc}") from exc


@runtime_checkable
class Transport(Protocol):
    """A framed bidirectional byte channel with a process behind it."""

    def send(self, line: bytes) -> None:
        """Write one already-framed line. Must not buffer across calls."""
        ...

    def receive(self, timeout: float) -> bytes | None:
        """Return one framed line without its newline, or ``None`` on timeout."""
        ...

    def stderr_tail(self) -> str:
        """Return what the child wrote to stderr, bounded. Never an error signal."""
        ...

    def close(self, *, grace: float) -> None:
        """Shut the child down. Idempotent."""
        ...


class StdioTransport:
    """Spawns an MCP server and speaks newline-delimited JSON-RPC to its pipes.

    Attributes:
        command: The executable, as argv[0].
        args: Remaining argv entries, passed literally.
    """

    __slots__ = (
        "_closed",
        "_force_kill_seconds",
        "_process",
        "_stderr_lock",
        "_stderr_ring",
        "_stderr_thread",
        "_stdout_buf",
    )

    def __init__(
        self,
        command: str,
        args: Sequence[str] = (),
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        force_kill_seconds: float = 3.0,
    ) -> None:
        if not command:
            raise ValueError("command must not be empty")

        self._process: subprocess.Popen[bytes] = _spawn(command, args, cwd, env)

        self._stdout_buf = bytearray()
        self._stderr_ring: deque[bytes] = deque()
        self._stderr_lock = threading.Lock()
        self._closed = False
        self._force_kill_seconds = force_kill_seconds

        self._stderr_thread = threading.Thread(
            target=self._drain_stderr, name="mcp-stderr", daemon=True
        )
        self._stderr_thread.start()

    # -- Transport protocol -------------------------------------------------- #

    def send(self, line: bytes) -> None:
        """Write one framed line to the child's stdin."""
        stdin = self._process.stdin
        if stdin is None:
            raise MCPTransportError("child stdin is closed")
        try:
            stdin.write(line)
            stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise MCPTransportError(f"could not write to child stdin: {exc}") from exc

    def receive(self, timeout: float) -> bytes | None:
        """Read one framed line from the child's stdout, or ``None`` on timeout.

        A ``None`` return is *timeout*, not EOF. EOF is a return code: the caller
        checks :meth:`died` to tell the two apart, which is what lets a timeout
        raise ``MCPTimeoutError`` while a death raises ``MCPServerDiedError``.
        """
        deadline = time.monotonic() + timeout
        stdout = self._process.stdout
        if stdout is None:
            raise MCPTransportError("child stdout is closed")

        while True:
            newline = self._stdout_buf.find(b"\n")
            if newline != -1:
                line = bytes(self._stdout_buf[:newline])
                del self._stdout_buf[: newline + 1]
                return line.rstrip(b"\r")

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None

            ready, _, _ = select.select([stdout], [], [], min(remaining, 0.5))
            if not ready:
                if self.died():
                    return None
                continue

            chunk = (
                stdout.read1(65536) if hasattr(stdout, "read1") else stdout.read(65536)
            )
            if not chunk:
                return None
            self._stdout_buf.extend(chunk)

            if len(self._stdout_buf) > MAX_LINE_BYTES:
                raise MCPTransportError(
                    f"no newline within {MAX_LINE_BYTES} bytes; the child is not "
                    f"framing its output"
                )

    def stderr_tail(self) -> str:
        """Return the bounded stderr ring as text, oldest first."""
        with self._stderr_lock:
            data = b"".join(self._stderr_ring)
        return data.decode("utf-8", errors="replace")

    def close(self, *, grace: float = 2.0) -> None:
        """Shut the child down: close stdin, wait, then signal the group.

        The sequence is the specification's: close the input stream, wait for the
        server to exit, and only then terminate forcibly. The grace period is the
        client's own number (ADR-0009 D-7).
        """
        if self._closed:
            return
        self._closed = True

        stdin = self._process.stdin
        if stdin is not None:
            with contextlib.suppress(OSError):
                # Already closed, or the child is gone. Either way there is
                # nothing to report: the escalation below is what matters.
                stdin.close()

        try:
            self._process.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            self._terminate_group()

        self._join_stderr()
        self._close_pipes()

    # -- introspection ------------------------------------------------------- #

    @property
    def pid(self) -> int:
        """The child's process id."""
        return self._process.pid

    def died(self) -> bool:
        """True when the child has exited."""
        return self._process.poll() is not None

    @property
    def returncode(self) -> int | None:
        """The child's exit status, or ``None`` while it is running."""
        return self._process.poll()

    # -- internals ----------------------------------------------------------- #

    def _terminate_group(self) -> None:
        """Escalate from SIGTERM to SIGKILL, targeting the process *group*.

        Every signal call is suppressed on failure, and that is deliberate
        rather than sloppy: the process may already be gone (``ProcessLookupError``),
        we may not own it (``PermissionError``), or the group id may have been
        reaped between the lookup and the signal. In all three cases the correct
        next step is the same — wait, then escalate — so there is nothing to
        handle and nothing useful to report.
        """
        if os.name == "posix":
            with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
                os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
        else:  # pragma: no cover - Windows path
            with contextlib.suppress(OSError):
                self._process.terminate()

        try:
            self._process.wait(timeout=self._force_kill_seconds)
            return
        except subprocess.TimeoutExpired:
            pass

        if os.name == "posix":
            with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
                os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
        else:  # pragma: no cover - Windows path
            with contextlib.suppress(OSError):
                self._process.kill()

        # Last wait. If the process is still alive after SIGKILL there is
        # nothing further this client can do, and blocking forever would be
        # worse than abandoning it.
        with contextlib.suppress(subprocess.TimeoutExpired):
            self._process.wait(timeout=self._force_kill_seconds)

    def _drain_stderr(self) -> None:
        """Read stderr until EOF, keeping only the most recent ``STDERR_RING_BYTES``.

        This thread exists to prevent the OS pipe from filling. It is a daemon so
        a hung server cannot keep the interpreter alive.
        """
        stderr = self._process.stderr
        if stderr is None:  # pragma: no cover - stderr is always a pipe here
            return
        total = 0
        while True:
            try:
                chunk = stderr.read(4096)
            except (OSError, ValueError):
                break
            if not chunk:
                break
            with self._stderr_lock:
                self._stderr_ring.append(chunk)
                total += len(chunk)
                while total > STDERR_RING_BYTES and self._stderr_ring:
                    total -= len(self._stderr_ring.popleft())

    def _join_stderr(self) -> None:
        """Wait briefly for the drain thread so the tail is complete."""
        self._stderr_thread.join(timeout=1.0)

    def _close_pipes(self) -> None:
        """Close every pipe this transport opened.

        ``Popen`` keeps the parent-side file objects alive until they are closed
        explicitly, and the test suite runs with ``filterwarnings = ["error"]``,
        so an unclosed pipe is not a tidiness issue -- it turns a passing test
        into a teardown failure. Closing here rather than relying on the
        garbage collector also means a long-lived process that opens and closes
        many servers does not accumulate file descriptors.
        """
        for stream in (
            self._process.stdin,
            self._process.stdout,
            self._process.stderr,
        ):
            if stream is None:
                continue
            # ValueError as well as OSError: a stream closed by the child's
            # exit raises the former, not the latter. Either way there is
            # nothing left to release.
            with contextlib.suppress(OSError, ValueError):
                stream.close()
