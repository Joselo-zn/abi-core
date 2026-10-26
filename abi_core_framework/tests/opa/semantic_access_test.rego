# Tests for abi.semantic_access (service_guardian/opa/policies/semantic_access.rego).
# Input shape: SemanticAccessValidator._prepare_opa_input
# (abi_core/semantic/semantic_access_validator.py). The validator queries the
# whole package and grants access only if `allow` is true AND `deny` is empty
# (_process_policy_result), so `permitted` below mirrors that.
# Run: opa test <policies dir> tests/opa

package abi.semantic_access_test

import rego.v1

import data.abi.semantic_access

noon := 1792843200000000000 # 2026-10-24T12:00:00Z

three_am := 1792810800000000000 # 2026-10-24T03:00:00Z

mock_now_ns := noon

card := {
	"id": "agent://planner_agent",
	"name": "Abi Planner Agent",
	"metadata": {"version": "1.0.0"},
}

req(tool) := {
	"action": "semantic_layer_access",
	"resource_type": "mcp_server",
	"source_agent": "agent://planner_agent",
	"agent_card": card,
	"request_metadata": {"source_ip": "172.18.0.5", "mcp_tool": tool},
	"context": {"service": "semantic_layer", "validation_mode": "strict", "require_user_validation": false},
}

# Risk factors add up as decimals (0.35000000000000000002), so compare with a tolerance.
risk_is(inp, now, expected) if {
	score := semantic_access.risk_score with input as inp with time.now_ns as now
	abs(score - expected) < 0.000001
}

with_card(inp, fields) := object.union(inp, {"agent_card": object.union(inp.agent_card, fields)})

permitted(inp) if {
	semantic_access.allow with input as inp with time.now_ns as mock_now_ns
	count(semantic_access.deny) == 0 with input as inp with time.now_ns as mock_now_ns
}

denied_with(inp, reason) if {
	not permitted(inp)
	reason in semantic_access.deny with input as inp with time.now_ns as mock_now_ns
}

# ── Identity ────────────────────────────────────────────────────────────

test_registered_agent_with_matching_id_is_permitted if {
	permitted(req("find_agent"))
}

test_id_matches_without_the_agent_prefix if {
	permitted(object.union(req("find_agent"), {"source_agent": "planner_agent"}))
}

test_id_matches_by_card_name if {
	permitted(object.union(req("find_agent"), {"source_agent": "abi planner agent"}))
}

test_service_card_id_matches if {
	inp := object.union(req("find_agent"), {
		"source_agent": "service://sandbox",
		"agent_card": {"id": "service://sandbox", "name": "sandbox"},
	})
	permitted(inp)
}

test_card_of_another_agent_is_not_permitted if {
	inp := object.union(req("find_agent"), {"source_agent": "agent://builder"})
	not permitted(inp)
	"Register agent in the system" in semantic_access.remediation_suggestions with input as inp
}

test_request_without_card_is_not_permitted if {
	not permitted(object.remove(req("find_agent"), ["agent_card"]))
}

# ── Deny rules ──────────────────────────────────────────────────────────

test_agent_in_the_blacklist_data_is_denied if {
	inp := req("find_agent")
	not semantic_access.allow with input as inp with data.blacklisted_agents as ["agent://planner_agent"]
	"Agent is blacklisted" in semantic_access.deny with input as inp with data.blacklisted_agents as ["agent://planner_agent"]
}

test_card_marked_blacklisted_is_denied if {
	denied_with(with_card(req("find_agent"), {"metadata": {"status": "blacklisted"}}), "Agent is blacklisted")
}

test_inactive_card_is_denied if {
	denied_with(with_card(req("find_agent"), {"metadata": {"status": "inactive"}}), "Agent marked as inactive")
	denied_with(with_card(req("find_agent"), {"metadata": {"enabled": false}}), "Agent marked as inactive")
}

test_rate_limit_exceeded_is_denied if {
	inp := req("find_agent")
	counts := {"agent://planner_agent": 61}
	limits := {"requests_per_minute": 60}
	not semantic_access.allow with input as inp with data.agent_request_counts as counts with data.rate_limits as limits
	"Rate limit exceeded for agent" in semantic_access.deny with input as inp
		with data.agent_request_counts as counts
		with data.rate_limits as limits
}

test_rate_limit_not_exceeded_is_permitted if {
	inp := req("find_agent")
	semantic_access.allow with input as inp
		with data.agent_request_counts as {"agent://planner_agent": 60}
		with data.rate_limits as {"requests_per_minute": 60}
		with time.now_ns as mock_now_ns
}

test_source_ip_outside_allowed_ips_is_denied if {
	inp := with_card(req("find_agent"), {"security": {"allowed_ips": ["10.0.0.1"]}})
	denied_with(inp, "Unauthorized source IP address")
}

test_source_ip_in_allowed_ips_is_permitted if {
	permitted(with_card(req("find_agent"), {"security": {"allowed_ips": ["172.18.0.5"]}}))
}

test_access_outside_schedule_is_denied if {
	inp := with_card(req("find_agent"), {"security": {"access_schedule": {"start_hour": 8, "end_hour": 18}}})
	not semantic_access.allow with input as inp with time.now_ns as three_am
	"Access outside allowed schedule" in semantic_access.deny with input as inp with time.now_ns as three_am
}

test_access_inside_schedule_is_permitted if {
	permitted(with_card(req("find_agent"), {"security": {"access_schedule": {"start_hour": 8, "end_hour": 18}}}))
}

test_tool_outside_allowed_mcp_tools_is_denied if {
	inp := with_card(req("register_tool"), {"security": {"allowed_mcp_tools": ["find_agent"]}})
	denied_with(inp, "Insufficient permissions for requested MCP tool")
}

test_tool_in_allowed_mcp_tools_is_permitted if {
	permitted(with_card(req("find_agent"), {"security": {"allowed_mcp_tools": ["find_agent"]}}))
}

test_empty_allowed_mcp_tools_does_not_restrict if {
	permitted(with_card(req("register_tool"), {"security": {"allowed_mcp_tools": []}}))
}

# ── Agent registration ──────────────────────────────────────────────────

test_register_agent_without_permission_is_denied if {
	denied_with(req("register_agent"), "Agent not authorized to register new agents")
}

test_register_agent_with_permission_is_permitted if {
	permitted(with_card(req("register_agent"), {"permissions": ["register_agents"]}))
}

# ── User validation ─────────────────────────────────────────────────────

user_req(tool, email) := object.union(req(tool), {
	"context": object.union(req(tool).context, {"require_user_validation": true}),
	"user": {"email": email},
})

test_user_validation_without_email_is_denied if {
	inp := object.union(req("find_agent"), {"context": object.union(req("find_agent").context, {"require_user_validation": true})})
	denied_with(inp, "User email required for validation")
}

test_user_without_permission_for_the_tool_is_denied if {
	denied_with(user_req("register_agent", "user@example.com"), "User does not have permission for this tool")
	denied_with(user_req("find_agent", "stranger@example.com"), "User does not have permission for this tool")
}

test_user_with_permission_for_the_tool_is_permitted if {
	permitted(user_req("find_agent", "user@example.com"))
}

# ── Ephemeral agents ────────────────────────────────────────────────────

ephemeral_req(tool) := object.union(req(tool), {
	"source_agent": "agent://ephemeral-r1-task-1-123",
	"agent_card": {"id": "agent://ephemeral-r1-task-1-123", "name": "ephemeral-r1-task-1-123", "ephemeral": true},
})

test_ephemeral_agent_can_use_lookup_tools if {
	permitted(ephemeral_req("find_agent"))
	permitted(ephemeral_req("get_tool"))
}

test_ephemeral_agent_cannot_use_admin_tools if {
	every tool in ["register_agent", "unregister_agent", "register_tool", "update_tool", "delete_tool"] {
		denied_with(ephemeral_req(tool), "Ephemeral agent cannot use admin tools")
	}
}

test_blacklisted_ephemeral_agent_is_denied if {
	inp := with_card(ephemeral_req("find_agent"), {"metadata": {"status": "blacklisted"}})
	denied_with(inp, "Agent is blacklisted")
}

# ── Risk score and the whole document ───────────────────────────────────

test_risk_score_of_a_plain_lookup if {
	# semantic_layer_access 0.2 + internal ip 0 + daytime 0 + find_agent 0 + untrusted agent 0.05
	risk_is(req("find_agent"), noon, 0.25)
}

test_risk_score_rises_at_night_from_outside if {
	inp := object.union(req("register_agent"), {"request_metadata": {"source_ip": "8.8.8.8", "mcp_tool": "register_agent"}})

	# 0.2 + external ip 0.1 + night 0.1 + register_agent 0.3 + 0.05
	risk_is(inp, three_am, 0.75)
}

test_risk_score_of_an_ephemeral_agent if {
	# 0.2 + 0 + 0 + 0 + ephemeral 0.15
	risk_is(ephemeral_req("find_agent"), noon, 0.35)
}

# The validator reads the whole package: a rule that fails to evaluate
# (a conflict) would turn every request into "OPA service error".
test_whole_package_evaluates if {
	doc := data.abi.semantic_access with input as req("find_agent") with time.now_ns as noon
	doc.allow
	doc.deny == set()
	doc.risk_score
}

# ── Audit log (open-findings 6.1) ───────────────────────────────────────

test_audit_log_on_an_allowed_request if {
	log := semantic_access.audit_log with input as req("find_agent") with time.now_ns as noon
	log.decision.allow
	log.policy == "semantic_access"
}

test_audit_log_on_a_denied_request if {
	inp := with_card(req("find_agent"), {"metadata": {"status": "inactive"}})
	log := semantic_access.audit_log with input as inp with time.now_ns as noon
	not log.decision.allow
	log.evaluation.agent_inactive
}

# Agent-to-agent calls carry no `user` (the validator only sends it when there
# is a user email; req() has none): the log must still exist, with user_email null.
test_audit_log_without_user if {
	log := semantic_access.audit_log with input as req("find_agent") with time.now_ns as noon
	log.input_summary.user_email == null
}

test_audit_log_with_user if {
	log := semantic_access.audit_log with input as user_req("find_agent", "user@example.com") with time.now_ns as noon
	log.input_summary.user_email == "user@example.com"
}
