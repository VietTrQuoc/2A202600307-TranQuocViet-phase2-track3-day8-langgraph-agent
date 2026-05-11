"""Report generation helper."""

from __future__ import annotations

from pathlib import Path

from .metrics import MetricsReport


def render_report_stub(metrics: MetricsReport) -> str:
    """Return a minimal report stub.

    TODO(student): replace with a richer report using the template in reports/.
    """
    # Generate scenario table
    scenario_rows = []
    for m in metrics.scenario_metrics:
        scenario_rows.append(f"| {m.scenario_id} | {m.expected_route} | {m.actual_route or 'N/A'} | {'✅' if m.success else '❌'} | {m.retry_count} | {m.interrupt_count} |")
    
    scenario_table = "\n".join(scenario_rows)
    
    return f"""# Day 08 Lab Report

## 1. Team / student

- Name: AI Assistant Implementation
- Repo/commit: langgraph-agent-lab
- Date: {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}

## 2. Architecture

The graph implements a support-ticket agent workflow with the following nodes and edges:

**Nodes:**
- `intake`: Normalize query, PII checks, metadata extraction
- `classify`: Route classification based on keywords and logic (simple/tool/missing_info/risky/error)
- `answer`: Generate final response grounded in tool results and approval
- `tool`: Execute mock tools with structured results and transient failure simulation
- `evaluate`: Structured validation of tool results for retry loop control
- `clarify`: Generate specific clarification questions based on query context
- `risky_action`: Prepare proposed actions with evidence and risk justification
- `approval`: Human-in-the-loop approval with mock/reject/edit support
- `retry`: Record retry attempts with exponential backoff
- `dead_letter`: Escalate unresolvable failures to manual review
- `finalize`: Emit final audit event

**Edges:**
- START -> intake -> classify -> [answer/tool/clarify/risky/retry]
- tool -> evaluate -> [answer/retry/dead_letter]
- retry -> [tool/dead_letter]
- clarify -> finalize
- risky -> approval -> [tool/answer]
- [answer/dead_letter] -> finalize -> END

**Key features:**
- Bounded retry loops with exponential backoff
- Conditional routing based on state logic
- Human-in-the-loop approval for risky actions
- Structured error handling with dead-letter escalation

## 3. State schema

| Field | Reducer | Why |
|---|---|---|
| thread_id | overwrite | unique identifier per conversation thread |
| scenario_id | overwrite | scenario identifier for metrics |
| query | overwrite | normalized user query |
| route | overwrite | current classification route |
| risk_level | overwrite | risk assessment (low/medium/high) |
| attempt | overwrite | current retry attempt counter |
| max_attempts | overwrite | maximum allowed retry attempts |
| final_answer | overwrite | final response to user |
| pending_question | overwrite | clarification question if needed |
| proposed_action | overwrite | risky action proposal details |
| approval | overwrite | approval decision and metadata |
| evaluation_result | overwrite | tool result evaluation outcome |
| backoff_seconds | overwrite | exponential backoff delay |
| messages | append | conversation history |
| tool_results | append | tool execution results |
| errors | append | error messages and retry history |
| events | append | audit events for debugging/metrics |

## 4. Scenario results

Key metrics summary:
- Total scenarios: {metrics.total_scenarios}
- Success rate: {metrics.success_rate:.2%}
- Average nodes visited: {metrics.avg_nodes_visited:.2f}
- Total retries: {metrics.total_retries}
- Total interrupts: {metrics.total_interrupts}

| Scenario | Expected route | Actual route | Success | Retries | Interrupts |
|---|---|---|---:|---:|---:|
{scenario_table}

## 5. Failure analysis

1. **Retry/tool failure**: When tool execution fails (simulated transient errors), the evaluate node detects error indicators in results and routes to retry. After max_attempts (3), routes to dead_letter for manual escalation. Backoff prevents overwhelming external systems.

2. **Risky action without approval**: Risky routes require approval before tool execution. If rejected, routes directly to answer with rejection message. This prevents unauthorized high-risk operations while maintaining user feedback.

3. **Missing information**: Vague queries (<5 words with pronouns) route to clarification, preventing hallucinated responses and ensuring accurate support.

## 6. Persistence / recovery evidence

- **Checkpointer**: Uses memory checkpointer for state persistence across graph invocations
- **Thread ID**: Each scenario uses unique thread_id for isolation
- **State history**: Events array provides audit trail of node visits and decisions
- **Crash recovery**: State can be resumed from any checkpoint using thread_id

## 7. Extension work

Completed extensions:
- Exponential backoff in retry logic (1s, 2s, 4s, 8s delays)
- Structured tool results with status/data fields
- Enhanced approval node with reject/edit options
- PII detection in intake node
- Context-aware clarification questions

## 8. Improvement plan

If given one more day, I would productionize:
1. **Real LLM integration**: Replace keyword heuristics with LLM-based classification and evaluation
2. **Database persistence**: Switch to SQLite/Postgres for production state management
3. **Real HITL UI**: Build Streamlit dashboard for approval workflows
4. **Advanced retry strategies**: Circuit breaker pattern and intelligent backoff
5. **Metrics dashboard**: Real-time monitoring and alerting for failure rates
"""


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report_stub(metrics), encoding="utf-8")
