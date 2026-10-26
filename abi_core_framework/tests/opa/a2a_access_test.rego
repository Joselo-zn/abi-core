# Tests for a2a_access (service_guardian/opa/policies/a2a_access.rego).
# Input shape: A2AAccessValidator.build_a2a_context
# (abi_core/security/a2a_access_validator.py), which queries
# a2a_access/allow and, on a denial, a2a_access/deny_reason.
# Run: opa test <policies dir> tests/opa

package a2a_access_test

import rego.v1

import data.a2a_access

a2a(source, target) := {
	"source_agent": {"name": source},
	"target_agent": {"name": target},
	"communication": {"timestamp": "2026-10-24T12:00:00", "message_length": 5},
	"validation_mode": "strict",
}

test_orchestrator_can_talk_to_any_agent if {
	a2a_access.allow with input as a2a("Abi Orchestrator Agent", "Abi Builder Agent")
	a2a_access.allow with input as a2a("Abi Orchestrator Agent", "ephemeral-r1-task-1-123")
}

test_any_agent_can_reach_the_semantic_layer if {
	a2a_access.allow with input as a2a("Abi Builder Agent", "semantic-layer")
}

test_unlisted_pair_is_denied_with_reason if {
	inp := a2a("Abi Builder Agent", "Abi Planner Agent")
	not a2a_access.allow with input as inp
	a2a_access.deny_reason == "Communication not allowed: Abi Builder Agent -> Abi Planner Agent" with input as inp
}

test_orchestrator_rule_is_not_bidirectional if {
	not a2a_access.allow with input as a2a("Abi Builder Agent", "Abi Orchestrator Agent")
}

test_unknown_agent_is_denied_with_reason if {
	inp := a2a("unknown", "Abi Builder Agent")
	not a2a_access.allow with input as inp
	a2a_access.deny_reason == "Source or target agent not properly identified" with input as inp
}

test_empty_name_is_denied if {
	not a2a_access.allow with input as a2a("Abi Orchestrator Agent", "")
}

test_disabled_mode_allows_everything if {
	inp := object.union(a2a("unknown", "unknown"), {"validation_mode": "disabled"})
	a2a_access.allow with input as inp
}

test_code_agent_and_reviewer_of_the_same_run_talk_both_ways if {
	a2a_access.allow with input as a2a("ephemeral-r1-task-1-123", "reviewer-r1")
	a2a_access.allow with input as a2a("reviewer-r1", "ephemeral-r1-task-1-123")
}

test_code_agent_and_reviewer_of_different_runs_are_denied if {
	not a2a_access.allow with input as a2a("ephemeral-r1-task-1-123", "reviewer-r2")
	not a2a_access.allow with input as a2a("reviewer-r2", "ephemeral-r1-task-1-123")
}

test_run_id_must_match_whole_not_as_prefix if {
	not a2a_access.allow with input as a2a("ephemeral-r12-task-1-123", "reviewer-r1")
}

test_two_code_agents_of_the_same_run_are_denied if {
	not a2a_access.allow with input as a2a("ephemeral-r1-task-1-123", "ephemeral-r1-task-2-456")
}

test_reviewer_with_empty_run_id_is_denied if {
	not a2a_access.allow with input as a2a("ephemeral--task-1-123", "reviewer-")
}

# ── Audit info (open-findings 6.2) ──────────────────────────────────────

test_audit_info_on_an_allowed_message if {
	info := a2a_access.audit_info with input as a2a("Abi Orchestrator Agent", "Abi Builder Agent")
	info.allowed
	info.reason == ""
}

test_audit_info_on_a_denied_message if {
	info := a2a_access.audit_info with input as a2a("Abi Builder Agent", "Abi Planner Agent")
	not info.allowed
	info.reason == "Communication not allowed: Abi Builder Agent -> Abi Planner Agent"
}

# The Python validator reads deny_reason only after a denial; it stays
# undefined when the message is allowed.
test_no_deny_reason_on_an_allowed_message if {
	not a2a_access.deny_reason with input as a2a("Abi Orchestrator Agent", "Abi Builder Agent")
}
