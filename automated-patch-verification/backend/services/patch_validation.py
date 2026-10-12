from pathlib import PurePosixPath
FORBIDDEN = {".git", ".ssh", "id_rsa", "credentials", "secrets"}
def validate_diff(diff: str, max_bytes: int = 100_000) -> dict:
    if not diff or len(diff.encode()) > max_bytes: raise ValueError("Patch is empty or exceeds the 100 KB limit.")
    if "*** Begin Patch" in diff or "\x00" in diff: raise ValueError("Patch format is invalid.")
    paths = []
    for line in diff.splitlines():
        if line.startswith(("+++ ", "--- ")):
            raw = line[4:].split("\t", 1)[0]
            if raw == "/dev/null": continue
            raw = raw.removeprefix("a/").removeprefix("b/"); path = PurePosixPath(raw)
            if path.is_absolute() or ".." in path.parts: raise ValueError("Patch contains an unsafe path.")
            normalized = str(path).lower()
            if any(part.lower() in FORBIDDEN or part.lower().startswith(".env") for part in path.parts) or normalized in {"config/production.py", "settings/production.py"}:
                raise ValueError("Patch targets a protected or secret file.")
            paths.append(raw)
    if not paths or not diff.startswith("diff --git ") or ("@@" not in diff and "new file mode" not in diff and "deleted file mode" not in diff):
        raise ValueError("Expected a valid unified git diff with at least one modified file.")
    return {"files": sorted(set(paths)), "bytes": len(diff.encode())}
