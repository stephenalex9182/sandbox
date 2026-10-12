from typing import TypedDict
from langgraph.graph import StateGraph, START, END
class FlowState(TypedDict, total=False):
    log: str
    analysis: dict
    source_files: dict[str, str]
    patch: dict
    validation: dict
    result: dict
    failure_output: str
    exit_code: int | None
def receive_log(s): return {"analysis": {"status": "received", "log_bytes": len(s["log"].encode())}}
def analyze(s):
    from backend.agents.analyzers import analyze_log
    result = analyze_log(s["log"])
    if s.get("failure_output"): result["previous_failure"] = s["failure_output"][:200_000]
    return {"analysis": result}
def identify_code(s): return {"source_files": s.get("source_files", {})}
def root_cause(s):
    from backend.agents.analyzers import analyze_root_cause
    analysis = dict(s["analysis"]); analysis["root_cause"] = analyze_root_cause(analysis, s["source_files"])
    return {"analysis": analysis}
def validate(s):
    from backend.services.patch_validation import validate_diff
    return {"validation": validate_diff(s["patch"]["diff"])}
def failure_analysis(s):
    if not s.get("failure_output"): return {}
    from backend.agents.analyzers import analyze_failure
    result = analyze_failure(s.get("patch", {}).get("diff", ""), s["failure_output"], s.get("exit_code"))
    analysis = dict(s.get("analysis", {})); analysis["failure_analysis"] = result
    return {"analysis": analysis}
def sandbox(s):
    from backend.sandbox.runner import run_patch
    return {"result": run_patch(s["source_files"], s["patch"]["diff"])}
def build_draft_workflow():
    from backend.agents.analyzers import generate_patch
    graph = StateGraph(FlowState)
    graph.add_node("receive_log", receive_log); graph.add_node("analyze_log", analyze)
    graph.add_node("identify_code", identify_code); graph.add_node("analyze_root_cause", root_cause)
    graph.add_node("failure_analysis", failure_analysis)
    graph.add_node("generate_patch", lambda s: {"patch": generate_patch(s["analysis"], s["source_files"])})
    graph.add_node("validate_patch", validate); graph.add_node("verify_e2b", sandbox)
    graph.add_edge(START, "receive_log"); graph.add_edge("receive_log", "analyze_log")
    graph.add_edge("analyze_log", "identify_code"); graph.add_edge("identify_code", "analyze_root_cause"); graph.add_edge("analyze_root_cause", "failure_analysis"); graph.add_edge("failure_analysis", "generate_patch")
    graph.add_edge("generate_patch", "validate_patch"); graph.add_edge("validate_patch", END)
    return graph.compile()

def build_verification_workflow():
    graph = StateGraph(FlowState); graph.add_node("verify_e2b", sandbox)
    graph.add_edge(START, "verify_e2b"); graph.add_edge("verify_e2b", END)
    return graph.compile()
