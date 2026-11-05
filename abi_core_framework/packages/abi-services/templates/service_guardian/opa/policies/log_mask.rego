package system.log

# OPA decision logs (decision_logs.console=true) print each decision's full
# input. Two fields of it carry what the user wrote: the preview of an
# agent-to-agent message, and an ephemeral card's skill description (the
# first 200 characters of its task prompt). They are erased from the log;
# the policies still see them, and the event lists them under "erased".
# Spec: abi-core .abi/specs/not-implemented/logs-without-user-content.md
mask contains "/input/communication/message_preview"

mask contains path if {
	some i
	input.input.agent_card.skills[i].description
	path := sprintf("/input/agent_card/skills/%d/description", [i])
}
