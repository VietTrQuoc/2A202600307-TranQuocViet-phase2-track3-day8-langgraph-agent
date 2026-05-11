"""Node skeletons for the LangGraph workflow.

Each function should be small, testable, and return a partial state update. Avoid mutating the
input state in place.
"""

from __future__ import annotations

from .state import AgentState, ApprovalDecision, Route, make_event


def intake_node(state: AgentState) -> dict:
    """Normalize raw query into state fields.

    TODO(student): add normalization, PII checks, and metadata extraction.
    """
    import re

    query = state.get("query", "").strip()
    # Basic normalization: lowercase, remove extra spaces
    normalized_query = re.sub(r'\s+', ' ', query.lower())
    
    # PII checks
    has_email = bool(re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', query))
    has_phone = bool(re.search(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', query))
    has_pii = has_email or has_phone
    
    # Metadata
    word_count = len(normalized_query.split())
    has_keywords = any(kw in normalized_query for kw in ['refund', 'order', 'status', 'reset', 'delete', 'timeout', 'fail'])
    
    return {
        "query": normalized_query,
        "messages": [f"intake:{normalized_query[:40]}"],
        "events": [make_event("intake", "completed", "query normalized", 
                            word_count=word_count, has_pii=has_pii, has_keywords=has_keywords)],
    }


def classify_node(state: AgentState) -> dict:
    """Classify the query into a route.

    TODO(student): replace keyword heuristics with a clear routing policy.
    Required routes: simple, tool, missing_info, risky, error.
    """
    query = state.get("query", "").lower()
    words = query.split()
    clean_words = [w.strip("?!.,;:") for w in words]
    
    route = Route.SIMPLE
    risk_level = "low"
    
    if any(kw in query for kw in ['refund', 'delete', 'cancel', 'remove', 'terminate', 'send confirmation', 'external action']):
        route = Route.RISKY
        risk_level = "high"
    elif any(kw in query for kw in ['status', 'order', 'lookup', 'check', 'find', 'search', 'retrieve']):
        route = Route.TOOL
        risk_level = "medium"
    elif any(kw in query for kw in ['timeout', 'fail', 'failure', 'error', 'cannot', 'unable', 'system down']):
        route = Route.ERROR
        risk_level = "high"
    elif len(clean_words) < 5 and any(w in clean_words for w in ['it', 'this', 'that']):
        route = Route.MISSING_INFO
        risk_level = "low"
    
    return {
        "route": route.value,
        "risk_level": risk_level,
        "events": [make_event("classify", "completed", f"route={route.value}, risk={risk_level}")],
    }


def ask_clarification_node(state: AgentState) -> dict:
    """Ask for missing information instead of hallucinating.

    TODO(student): generate a specific clarification question from state.
    """
    query = state.get("query", "").lower()
    
    if 'order' in query:
        question = "Could you please provide the order number or customer ID to look up the details?"
    elif 'account' in query or 'user' in query:
        question = "Please provide the account email or user ID for verification."
    elif 'refund' in query or 'return' in query:
        question = "What is the order number and reason for the refund request?"
    elif 'status' in query:
        question = "Which service or order status are you inquiring about? Please provide details."
    else:
        question = "I need more specific information to help you. Could you provide additional context or details?"
    
    return {
        "pending_question": question,
        "final_answer": question,
        "events": [make_event("clarify", "completed", "clarification question generated")],
    }


def tool_node(state: AgentState) -> dict:
    """Call a mock tool.

    Simulates transient failures for error-route scenarios to demonstrate retry loops.
    TODO(student): implement idempotent tool execution and structured tool results.
    """
    attempt = int(state.get("attempt", 0))
    scenario_id = state.get("scenario_id", "unknown")
    
    # Simulate transient failures for error scenarios
    if state.get("route") == Route.ERROR.value and attempt < 2:
        result: dict[str, str | None] = {
            "status": "error",
            "message": f"Transient failure on attempt {attempt} for scenario {scenario_id}",
            "data": None
        }
    else:
        # Mock successful tool result
        result = {
            "status": "success",
            "message": f"Tool executed successfully for scenario {scenario_id}",
            "data": {
                "order_status": "shipped",
                "customer_info": {"name": "John Doe", "email": "john@example.com"}
            }
        }
    
    return {
        "tool_results": [str(result)],  # Keep as string for compatibility
        "events": [make_event("tool", "completed", f"tool executed attempt={attempt}, status={result['status']}")],
    }


def risky_action_node(state: AgentState) -> dict:
    """Prepare a risky action for approval.

    TODO(student): create a proposed action with evidence and risk justification.
    """
    query = state.get("query", "")
    
    if 'refund' in query:
        proposed_action = {
            "action": "process_refund",
            "details": "Initiate refund for customer order",
            "evidence": "Customer requested refund in support ticket",
            "risks": "Potential financial loss if fraudulent, requires verification",
            "justification": "Customer satisfaction and policy compliance"
        }
    elif 'delete' in query:
        proposed_action = {
            "action": "delete_account",
            "details": "Permanently delete customer account",
            "evidence": "Customer requested account deletion",
            "risks": "Irreversible action, potential legal issues if not verified",
            "justification": "GDPR compliance and customer right to be forgotten"
        }
    elif 'send' in query:
        proposed_action = {
            "action": "send_notification",
            "details": "Send confirmation email to customer",
            "evidence": "Action completion requires customer notification",
            "risks": "Email delivery issues, potential spam concerns",
            "justification": "Transparency and customer communication"
        }
    else:
        proposed_action = {
            "action": "external_action",
            "details": "Execute external system operation",
            "evidence": "Query indicates need for external system interaction",
            "risks": "System integration risks, potential data inconsistencies",
            "justification": "Required to fulfill customer request"
        }
    
    return {
        "proposed_action": str(proposed_action),  # Keep as string for state compatibility
        "events": [make_event("risky_action", "pending_approval", f"action={proposed_action['action']}")],
    }


def approval_node(state: AgentState) -> dict:
    """Human approval step with optional LangGraph interrupt().

    Set LANGGRAPH_INTERRUPT=true to use real interrupt() for HITL demos.
    Default uses mock decision so tests and CI run offline.

    TODO(student): implement reject/edit decisions and timeout escalation.
    """
    import os
    import time

    proposed_action = state.get("proposed_action", "")
    
    if os.getenv("LANGGRAPH_INTERRUPT", "").lower() == "true":
        from langgraph.types import interrupt

        value = interrupt({
            "proposed_action": proposed_action,
            "risk_level": state.get("risk_level"),
            "query": state.get("query"),
            "options": ["approve", "reject", "edit"]
        })
        
        if isinstance(value, dict):
            decision = ApprovalDecision(**value)
        elif isinstance(value, str):
            if value == "approve":
                decision = ApprovalDecision(approved=True, comment="Approved via interrupt")
            elif value == "reject":
                decision = ApprovalDecision(approved=False, comment="Rejected via interrupt")
            else:
                decision = ApprovalDecision(approved=False, comment=f"Edited: {value}")
        else:
            decision = ApprovalDecision(approved=bool(value))
    else:
        # Mock approval logic: approve if risk is low, reject if high
        risk_level = state.get("risk_level", "unknown")
        if risk_level == "low":
            decision = ApprovalDecision(approved=True, comment="Mock approval for low-risk action")
        elif risk_level == "medium":
            decision = ApprovalDecision(approved=True, comment="Mock approval for medium-risk action")
        else:
            # For high-risk, sometimes reject for demo
            proposed_action_str = proposed_action.lower() if proposed_action else ""
            approved = "refund" not in proposed_action_str  # Reject refunds in mock
            decision = ApprovalDecision(
                approved=approved, 
                comment="Mock rejection for high-risk action" if not approved else "Mock approval after review"
            )
    
    return {
        "approval": decision.model_dump(),
        "events": [make_event("approval", "completed", f"approved={decision.approved}, comment={decision.comment[:50]}")],
    }


def retry_or_fallback_node(state: AgentState) -> dict:
    """Record a retry attempt or fallback decision.

    TODO(student): implement bounded retry, exponential backoff metadata, and fallback route.
    """
    attempt = int(state.get("attempt", 0)) + 1
    max_attempts = int(state.get("max_attempts", 3))
    
    # Exponential backoff: 1, 2, 4, 8 seconds
    backoff_seconds = 2 ** (attempt - 1)
    
    errors = [f"Transient failure on attempt {attempt}, will retry after {backoff_seconds}s"]
    
    return {
        "attempt": attempt,
        "backoff_seconds": backoff_seconds,
        "errors": errors,
        "events": [make_event("retry", "completed", f"retry attempt {attempt}/{max_attempts}, backoff={backoff_seconds}s")],
    }


def answer_node(state: AgentState) -> dict:
    """Produce a final response.

    TODO(student): ground the answer in tool_results and approval where relevant.
    """
    tool_results = state.get("tool_results", [])
    approval = state.get("approval")
    query = state.get("query", "")
    
    if tool_results:
        latest_result = tool_results[-1]
        if "success" in latest_result:
            answer = f"Based on our records: {latest_result}. Your request has been processed successfully."
        else:
            answer = f"I encountered an issue: {latest_result}. Please try again or contact support."
    elif approval and not approval.get("approved"):
        answer = f"Your request requires approval but was not approved. Reason: {approval.get('comment', 'Not specified')}."
    elif approval and approval.get("approved"):
        answer = f"Your request has been approved and processed. Confirmation: {approval.get('comment', 'Approved')}."
    elif "reset password" in query:
        answer = "I've initiated the password reset process. Please check your email for instructions."
    elif state.get("pending_question"):
        answer = state.get("pending_question", "Could you provide more details?")
    else:
        answer = "Thank you for your inquiry. Your request has been noted and will be handled by our support team."
    
    return {
        "final_answer": answer,
        "events": [make_event("answer", "completed", "final answer generated")],
    }


def evaluate_node(state: AgentState) -> dict:
    """Evaluate tool results — the 'done?' check that enables retry loops.

    TODO(student): replace heuristic with LLM-as-judge or structured validation.
    """
    tool_results = state.get("tool_results", [])
    attempt = int(state.get("attempt", 0))
    max_attempts = int(state.get("max_attempts", 3))
    
    if not tool_results:
        return {
            "evaluation_result": "needs_retry",
            "events": [make_event("evaluate", "completed", "no tool results, needs retry")],
        }
    
    latest_result = tool_results[-1]
    
    # Structured validation: check for error indicators
    error_indicators = ["error", "failure", "timeout", "unable", "cannot", "failed"]
    has_error = any(indicator in latest_result.lower() for indicator in error_indicators)
    
    if has_error and attempt < max_attempts:
        evaluation_result = "needs_retry"
    elif has_error and attempt >= max_attempts:
        evaluation_result = "max_retries_exceeded"
    else:
        evaluation_result = "success"
    
    return {
        "evaluation_result": evaluation_result,
        "events": [make_event("evaluate", "completed", f"evaluation={evaluation_result}, attempt={attempt}")],
    }


def dead_letter_node(state: AgentState) -> dict:
    """Log unresolvable failures for manual review.

    Third layer of error strategy: retry -> fallback -> dead letter.
    TODO(student): persist to dead-letter queue, alert on-call, or create support ticket.
    """
    scenario_id = state.get("scenario_id", "unknown")
    attempt = state.get("attempt", 0)
    errors = state.get("errors", [])
    
    # Mock dead-letter persistence
    dead_letter_entry = {
        "scenario_id": scenario_id,
        "query": state.get("query"),
        "final_attempt": attempt,
        "errors": errors,
        "timestamp": "2024-01-01T00:00:00Z",  # Mock timestamp
        "status": "escalated_to_manual_review"
    }
    
    return {
        "final_answer": f"Request could not be completed after {attempt} attempts. Logged for manual review (Ticket #{scenario_id}). Our team will contact you within 24 hours.",
        "events": [make_event("dead_letter", "completed", f"escalated scenario {scenario_id}, attempt={attempt}")],
    }


def finalize_node(state: AgentState) -> dict:
    """Finalize the run and emit a final audit event."""
    return {"events": [make_event("finalize", "completed", "workflow finished")]}
