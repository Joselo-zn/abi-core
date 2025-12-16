# OPA Migration Guide

## Overview

The OPA (Open Policy Agent) related files have been reorganized for better structure and maintainability. This guide explains the changes and how to update your code.

## Changes Made

### File Relocations

| Old Location | New Location |
|--------------|--------------|
| `abi-core/agents/abi-llm-base/common/opa/` | `abi-core/agents/abi-llm-base/opa/` |
| `config/opa.yaml` | `abi-core/agents/abi-llm-base/opa/opa.yaml` |
| `policies/custom_policies.rego` | `abi-core/agents/abi-llm-base/opa/custom_policies.rego` |

### Import Changes

Update your import statements:

```python
# OLD
from common.opa.config import get_opa_config
from common.opa.policy_loader import PolicyLoader
from common.opa.policy_loader_v2 import PolicyLoaderV2
from common.opa.core_policies import CorePolicyGenerator

# NEW
from abi_llm_base.opa.config import get_opa_config
from abi_llm_base.opa.policy_loader import PolicyLoader
from abi_llm_base.opa.policy_loader_v2 import PolicyLoaderV2
from abi_llm_base.opa.core_policies import CorePolicyGenerator
```

### Configuration Changes

The configuration system now looks for `opa.yaml` in the following order:

1. `./opa/opa.yaml` (new primary location)
2. `./config/opa.yaml` (legacy support)
3. `./opa.yaml`
4. `~/.abi/opa.yaml`
5. `/etc/abi/opa.yaml`

### Policy Path Changes

Default policy paths have been updated:

- **Old default**: `./policies`
- **New default**: `./opa`

## Migration Steps

### 1. Update Import Statements

Search and replace in your codebase:

```bash
# Find files with old imports
grep -r "from common.opa" .

# Replace imports (example with sed)
sed -i 's/from common\.opa\./from abi_llm_base.opa./g' your_file.py
```

### 2. Update Configuration References

If you have hardcoded paths to `config/opa.yaml`, update them to use the new location or rely on the automatic discovery.

### 3. Move Custom Policies

If you have custom policies in the old `policies/` directory, move them to the new `opa/` directory:

```bash
mv policies/*.rego abi-core/agents/abi-llm-base/opa/
```

### 4. Update Environment Variables

If you're using environment variables, update them:

```bash
# OLD
export ABI_POLICY_PATHS="./policies"

# NEW  
export ABI_POLICY_PATHS="./opa"
```

### 5. Verify Migration

Run the verification script:

```bash
cd abi-core/agents/abi-llm-base
python opa/verify_migration.py
```

## Benefits of the New Structure

1. **Centralized OPA Files**: All OPA-related files are now in one location
2. **Better Organization**: Clearer separation between common utilities and OPA-specific code
3. **Simplified Imports**: More intuitive import paths
4. **Backward Compatibility**: Legacy paths are still supported during transition

## Troubleshooting

### Import Errors

If you get import errors:

1. Check that you've updated all import statements
2. Ensure the `abi_llm_base` package is in your Python path
3. Verify that `__init__.py` files exist in the package hierarchy

### Configuration Not Found

If configuration files aren't found:

1. Check that `opa.yaml` exists in the new location
2. Verify file permissions
3. Check environment variables

### Policy Loading Issues

If policies aren't loading:

1. Verify policy files are in the correct directory
2. Check file extensions (should be `.rego`)
3. Validate policy syntax

## Support

If you encounter issues during migration:

1. Check the verification script output
2. Review the logs for specific error messages
3. Ensure all dependencies are properly updated

## Rollback Plan

If you need to rollback:

1. Restore the old directory structure
2. Revert import statements
3. Move configuration files back to original locations

However, the new structure is recommended for better maintainability.