import re
FRAME = re.compile(r'File "([^\"]+)", line (\d+)(?:, in ([^\n]+))?')
JAVA_FRAME = re.compile(r'\bat\s+([\w.$]+)\(([^():]+):(\d+)\)')
def parse_log(text: str) -> dict:
    if not text.strip(): raise ValueError("The log is empty.")
    if len(text) > 200_000: raise ValueError("Log exceeds the 200 KB limit.")
    lines = text.splitlines()
    match = FRAME.search(text); java = JAVA_FRAME.search(text)
    exception = next((line.strip() for line in lines if re.search(r'\b[\w.$]*(?:Exception|Error)\b', line) and not re.search(r'\b(ERROR|FATAL)\b', line)), lines[0][:500])
    timestamp = re.search(r'\b\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d[^ ]*', text)
    frame = {"file": None, "line": None, "function": None}
    if match: frame = {"file": match.group(1), "line": int(match.group(2)), "function": match.group(3)}
    elif java: frame = {"file": java.group(2), "line": int(java.group(3)), "function": java.group(1)}
    severity = "high" if re.search(r'critical|fatal|exception|error', text, re.I) else "medium"
    error_name = re.search(r'([\w.$]*(?:Exception|Error))', exception)
    error_type = error_name.group(1).split(".")[-1] if error_name else exception.split(":", 1)[0][:120]
    return {"error_type": error_type, "message": exception[:500], "stack_trace": text[:200_000], **frame, "severity": severity, "timestamp": timestamp.group(0) if timestamp else None}
