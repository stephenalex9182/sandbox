import io, tarfile, time
import re
from pathlib import PurePosixPath
from backend.config import get_settings
DENY = {".env", ".git", ".ssh", "node_modules", "__pycache__", ".venv", "venv", "secrets"}
def _safe_files(files: dict[str, str]) -> list[tuple[str, bytes]]:
    s = get_settings(); total = 0; result = []
    if not files: raise ValueError("Upload a Python project before verification.")
    for name, content in files.items():
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or any(p.lower() in DENY or p.lower().startswith(".env") for p in path.parts): raise ValueError(f"Project contains a prohibited path: {name}")
        encoded = content.encode("utf-8")
        if len(encoded) > s.max_project_file_bytes: raise ValueError(f"File exceeds size limit: {name}")
        total += len(encoded); result.append((str(path), encoded))
    if total > s.max_project_total_bytes: raise ValueError("Project exceeds total upload size limit.")
    return result
def run_patch(files: dict[str, str], diff: str) -> dict:
    s = get_settings()
    if not s.e2b_api_key: raise RuntimeError("E2B is not configured. Verification is disabled; generated code will not run locally.")
    safe_files = _safe_files(files)
    from e2b import Sandbox
    sb = None; start = time.monotonic(); stdout = ""; stderr = ""; exit_code = None
    try:
        # Disable all outbound networking for untrusted patch and test code.
        # This prevents sandbox code from reaching services or exfiltrating source.
        sb = Sandbox.create(api_key=s.e2b_api_key, timeout=s.sandbox_timeout_seconds, allow_internet_access=False)
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w:gz") as tar:
            for path, data in safe_files:
                info = tarfile.TarInfo(path); info.size = len(data); info.mode = 0o600
                tar.addfile(info, io.BytesIO(data))
        sb.files.write("/tmp/project.tar.gz", archive.getvalue())
        sb.files.write("/tmp/patch.diff", diff)
        cmd = sb.commands.run("set -e; mkdir -p /tmp/project; tar -xzf /tmp/project.tar.gz -C /tmp/project; cd /tmp/project; git apply --check /tmp/patch.diff; git apply /tmp/patch.diff", timeout=s.sandbox_timeout_seconds)
        if cmd.exit_code == 0:
            test = sb.commands.run(r"set -e; cd /tmp/project; python -m compileall -q .; if [ -f requirements.txt ]; then python -m pip install --disable-pip-version-check -r requirements.txt; fi; if find . -maxdepth 3 \( -name 'test_*.py' -o -name '*_test.py' \) | grep -q .; then python -m pytest -q; else echo 'NO_TEST_SUITE_DETECTED'; fi", timeout=s.sandbox_timeout_seconds)
            stdout = (getattr(test, "stdout", "") or "")[:s.max_output_bytes]; stderr = (getattr(test, "stderr", "") or "")[:s.max_output_bytes]; exit_code = test.exit_code
            no_tests = "NO_TEST_SUITE_DETECTED" in stdout or "no tests ran" in stdout.lower()
            summary = stdout.splitlines()[-1] if stdout else ""
            test_counts = {name: int((re.search(rf"(\d+)\s+{name}", summary) or [None, 0])[1]) for name in ("passed", "failed", "skipped")}
            status = "partially_verified" if exit_code == 0 and no_tests else ("verified" if exit_code == 0 else "failed")
            report = "Full verification unavailable because no test suite was detected." if no_tests else "Python syntax validation, dependency installation, and pytest completed in E2B."
        else:
            stderr = (getattr(cmd, "stderr", "") or "Patch could not be applied cleanly.")[:s.max_output_bytes]; exit_code = cmd.exit_code; status = "failed"; report = "Patch application failed inside E2B."
        return {"status": status, "stdout": stdout, "stderr": stderr, "exit_code": exit_code, "duration_ms": int((time.monotonic()-start)*1000), "report": report, "tests": test_counts if cmd.exit_code == 0 else {"passed": 0, "failed": 0, "skipped": 0}, "sandbox_id": sb.sandbox_id}
    finally:
        if sb is not None: sb.kill()
