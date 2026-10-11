# Governed sandbox — may this caller run code in the sandbox for this plan run?
# Queried by sandbox-service at /v1/data/abi/sandbox. Default deny: every
# condition below must hold. sandbox-service denies on its own if OPA is
# unreachable (fail-closed): running generated code is the most privileged
# action of the code pipeline.
#
# Input (built by sandbox-service, never by the caller):
#   caller: {verified, id, name, ephemeral, allowed_actions}  — identity
#           verified by the semantic layer (HMAC), card without secrets
#   run:    {plan_exists, has_executable_code, runs_used}     — read by the
#           service from projects/<run_id>/ (plan and audit)
#   limits: {max_runs}
#
# Spec: ephemeral-reviewer-pipeline/02-ephemeral-reviewer/02.5-governed-sandbox.md

package abi.sandbox

import rego.v1

default allow := false

allow if {
	count(deny) == 0
}

deny contains "caller signature not verified" if {
	not input.caller.verified
}

# The permission is declared on the caller's card (security.allowed_actions),
# like semantic_access checks allowed_mcp_tools — but explicit: no list, no access.
deny contains "caller card lacks the run_sandbox permission" if {
	not "run_sandbox" in object.get(input.caller, "allowed_actions", [])
}

# An ephemeral agent may only use the sandbox as the reviewer of its own run.
deny contains "ephemeral caller is not this run's reviewer" if {
	input.caller.ephemeral
	input.caller.name != sprintf("reviewer-%s", [input.run_id])
}

deny contains "run has no plan" if {
	not input.run.plan_exists
}

deny contains "run has no executable code (no .py entry point in its technical design)" if {
	not input.run.has_executable_code
}

deny contains "sandbox run limit reached for this run" if {
	input.run.runs_used >= input.limits.max_runs
}
