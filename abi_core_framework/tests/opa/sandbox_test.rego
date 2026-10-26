# Tests for abi.sandbox (service_guardian/opa/policies/sandbox.rego).
# Input shape: what sandbox-service builds (abi_services/sandbox_service/app.py).
# Run: opa test <policies dir> tests/opa

package abi.sandbox_test

import rego.v1

import data.abi.sandbox

reviewer := {
	"verified": true,
	"id": "agent://reviewer-r1",
	"name": "reviewer-r1",
	"ephemeral": true,
	"allowed_actions": ["run_sandbox"],
}

ok_input := {
	"action": "run_sandbox",
	"run_id": "r1",
	"caller": reviewer,
	"run": {"plan_exists": true, "has_executable_code": true, "runs_used": 0},
	"limits": {"max_runs": 3},
}

test_reviewer_of_its_own_run_is_allowed if {
	sandbox.allow with input as ok_input
	count(sandbox.deny) == 0 with input as ok_input
}

test_non_ephemeral_caller_with_the_permission_is_allowed if {
	orchestrator := object.union(reviewer, {"name": "Abi Orchestrator Agent", "ephemeral": false})
	sandbox.allow with input as object.union(ok_input, {"caller": orchestrator})
}

test_unverified_caller_is_denied if {
	inp := object.union(ok_input, {"caller": object.union(reviewer, {"verified": false})})
	not sandbox.allow with input as inp
	"caller signature not verified" in sandbox.deny with input as inp
}

test_caller_without_verified_field_is_denied if {
	inp := json.remove(ok_input, ["caller/verified"])
	"caller signature not verified" in sandbox.deny with input as inp
}

test_caller_without_the_permission_is_denied if {
	inp := object.union(ok_input, {"caller": object.union(reviewer, {"allowed_actions": ["find_agent"]})})
	not sandbox.allow with input as inp
	"caller card lacks the run_sandbox permission" in sandbox.deny with input as inp
}

test_caller_without_allowed_actions_is_denied if {
	inp := json.remove(ok_input, ["caller/allowed_actions"])
	"caller card lacks the run_sandbox permission" in sandbox.deny with input as inp
}

test_reviewer_of_another_run_is_denied if {
	inp := object.union(ok_input, {"run_id": "r2"})
	not sandbox.allow with input as inp
	"ephemeral caller is not this run's reviewer" in sandbox.deny with input as inp
}

test_ephemeral_code_agent_of_the_run_is_denied if {
	code_agent := object.union(reviewer, {"name": "ephemeral-r1-task-1-123"})
	inp := object.union(ok_input, {"caller": code_agent})
	"ephemeral caller is not this run's reviewer" in sandbox.deny with input as inp
}

test_run_without_plan_is_denied if {
	inp := object.union(ok_input, {"run": object.union(ok_input.run, {"plan_exists": false})})
	"run has no plan" in sandbox.deny with input as inp
}

test_run_without_executable_code_is_denied if {
	inp := object.union(ok_input, {"run": object.union(ok_input.run, {"has_executable_code": false})})
	"run has no executable code (no .py entry point in its technical design)" in sandbox.deny with input as inp
}

test_last_run_within_the_limit_is_allowed if {
	sandbox.allow with input as object.union(ok_input, {"run": object.union(ok_input.run, {"runs_used": 2})})
}

test_run_limit_reached_is_denied if {
	inp := object.union(ok_input, {"run": object.union(ok_input.run, {"runs_used": 3})})
	not sandbox.allow with input as inp
	"sandbox run limit reached for this run" in sandbox.deny with input as inp
}

test_empty_input_is_denied if {
	not sandbox.allow with input as {}
}
