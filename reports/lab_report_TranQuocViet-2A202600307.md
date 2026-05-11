# Day 08 Lab Report

## 1. Team / student

- Name: AI Assistant Implementation
- Repo/commit: langgraph-agent-lab
- Date: 2026-05-11

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
- Total scenarios: 7
- Success rate: 100.00%
- Average nodes visited: 6.29
- Total retries: 4
- Total interrupts: 2

| Scenario | Expected route | Actual route | Success | Retries | Interrupts |
|---|---|---|---:|---:|---:|
| S01_simple | simple | simple | ✅ | 0 | 0 |
| S02_tool | tool | tool | ✅ | 0 | 0 |
| S03_missing | missing_info | missing_info | ✅ | 0 | 0 |
| S04_risky | risky | risky | ✅ | 0 | 1 |
| S05_error | error | error | ✅ | 3 | 0 |
| S06_delete | risky | risky | ✅ | 0 | 1 |
| S07_dead_letter | error | error | ✅ | 1 | 0 |

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
