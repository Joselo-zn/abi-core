# Tests for abi.basic (service_guardian/opa/policies/basic.rego).
# Run: opa test <policies dir> tests/opa

package abi.basic_test

import rego.v1

import data.abi.basic

test_health_check_is_allowed if {
	basic.allow with input as {"action": "health_check"}
}

test_read_of_a_public_resource_is_allowed if {
	basic.allow with input as {"action": "read", "resource_type": "log", "content": "service started"}
}

test_read_with_sensitive_content_is_denied if {
	not basic.allow with input as {"action": "read", "resource_type": "log", "content": "the API Token is x"}
}

test_read_of_a_non_public_resource_is_denied if {
	not basic.allow with input as {"action": "read", "resource_type": "database", "content": "x"}
}

test_write_is_denied if {
	not basic.allow with input as {"action": "write", "resource_type": "log", "content": "x"}
}

test_risk_score_by_action if {
	basic.risk_score == 0.0 with input as {"action": "health_check"}
	basic.risk_score == 0.9 with input as {"action": "execute"}
}

test_unknown_action_has_maximum_risk if {
	basic.risk_score == 1.0 with input as {"action": "format_disk"}
}
