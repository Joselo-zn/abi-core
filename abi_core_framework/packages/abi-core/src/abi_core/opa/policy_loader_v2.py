import os
from pathlib import Path
from typing import List, Dict, Any
import importlib.util
from abi_core.common.utils import abi_logging

from .core_policies import get_core_policy_generator


class PolicyLoaderV2:
    """
    Enhanced Policy Loader with mandatory core policies
    
    Features:
    1. MANDATORY core policies - system won't start without them
    2. Auto-generation of core policies at runtime
    3. Extensible policy loading from multiple sources
    4. Policy validation and conflict resolution
    """
    
    def __init__(self, base_policy_path: str = None):
        self.base_policy_path = base_policy_path or "./opa"
        self.loaded_policies = {}
        self.core_generator = get_core_policy_generator()
        
    def ensure_system_security(self) -> bool:
        """
        CRITICAL: Ensure system has required security policies
        
        Returns:
            True if system is secure and can start
            False if system MUST NOT start due to missing security policies
        """
        abi_logging(" Validating system security policies...")
        
        # Ensure core policies directory exists
        core_policy_dir = Path(self.base_policy_path)
        core_policy_dir.mkdir(parents=True, exist_ok=True)
        
        # Ensure core policies exist and are valid
        if not self.core_generator.ensure_core_policies(str(core_policy_dir)):
            abi_logging("[!] CRITICAL SECURITY FAILURE: Core policies unavailable", level="error")
            abi_logging("[!] SYSTEM STARTUP BLOCKED FOR SECURITY", level="error")
            return False
        
        abi_logging("[Y] System security validation passed")
        return True
        
    def discover_policy_sources(self) -> List[Dict[str, Any]]:
        """
        Discover all available policy sources
        
        Returns:
            List of policy source configurations
        """
        sources = []
        
        # 0. MANDATORY: Core policies (HIGHEST PRIORITY)
        core_policy_path = Path(self.base_policy_path)
        if core_policy_path.exists():
            sources.append({
                'name': 'abi-core-mandatory',
                'type': 'core',
                'path': str(core_policy_path),
                'priority': 1000,  # HIGHEST PRIORITY - CANNOT BE OVERRIDDEN
                'description': 'MANDATORY ABI core security policies',
                'required': True
            })
        
        # 1. Built-in ABI policies (from guardial package)
        try:
            import guardial.opa.policies
            builtin_path = Path(guardial.opa.policies.__file__).parent
            sources.append({
                'name': 'abi-builtin',
                'type': 'package',
                'path': str(builtin_path),
                'priority': 100,
                'description': 'Built-in ABI policies',
                'required': False
            })
        except ImportError:
            abi_logging("Built-in ABI V2 policies not found", level="warning")
        
        # 2. Environment-specified policy paths
        env_policies = os.getenv('ABI_POLICY_PATHS', '')
        if env_policies:
            for path in env_policies.split(':'):
                if Path(path).exists():
                    sources.append({
                        'name': f'env-{Path(path).name}',
                        'type': 'directory', 
                        'path': path,
                        'priority': 75,
                        'description': f'Environment policy: {path}',
                        'required': False
                    })
        
        # 3. Local policies directory (if different from core)
        local_policies = Path(self.base_policy_path)
        if local_policies.exists() and str(local_policies) not in [s['path'] for s in sources]:
            sources.append({
                'name': 'local',
                'type': 'directory',
                'path': str(local_policies),
                'priority': 50,
                'description': 'Local project policies',
                'required': False
            })
        
        # 4. Discover installed policy packages
        installed_sources = self._discover_installed_policies()
        sources.extend(installed_sources)
        
        # Sort by priority (highest first)
        sources.sort(key=lambda x: x['priority'], reverse=True)
        
        abi_logging(f"Discovered {len(sources)} policy sources")
        for source in sources:
            required_marker = " [REQUIRED]" if source.get('required') else ""
            abi_logging(f"  - {source['name']}: {source['description']}{required_marker}")
            
        return sources
    
    def _discover_installed_policies(self) -> List[Dict[str, Any]]:
        """
        Discover policy packages installed via pip
        
        Looks for packages with naming pattern: *_abi_policies
        """
        sources = []
        
        try:
            import pkg_resources
            
            for dist in pkg_resources.working_set:
                if dist.project_name.endswith('_abi_policies'):
                    try:
                        # Try to import the package
                        spec = importlib.util.find_spec(dist.project_name)
                        if spec and spec.origin:
                            package_path = Path(spec.origin).parent
                            sources.append({
                                'name': dist.project_name,
                                'type': 'package',
                                'path': str(package_path),
                                'priority': 25,
                                'description': f'Installed policy package: {dist.project_name}',
                                'required': False
                            })
                    except Exception as e:
                        abi_logging(f"Failed to load policy package {dist.project_name}: {e}", level="warning")
                        
        except ImportError:
            abi_logging("pkg_resources not available for policy discovery", level="debug")
            
        return sources
    
    def load_all_policies(self) -> Dict[str, str]:
        """
        Load all .rego policy files from discovered sources
        
        CRITICAL: Will fail if core security policies are missing
        
        Returns:
            Dictionary mapping policy names to policy content
        """
        # CRITICAL: Ensure system security first
        if not self.ensure_system_security():
            raise RuntimeError("CRITICAL: System security validation failed - cannot load policies")
        
        policies = {}
        sources = self.discover_policy_sources()
        
        # Track if we loaded core policies
        core_policies_loaded = False
        
        for source in sources:
            source_policies = self._load_policies_from_source(source)
            
            # Special handling for core policies
            if source.get('required') and source['type'] == 'core':
                if not source_policies:
                    raise RuntimeError(f"CRITICAL: Required core policies not found in {source['path']}")
                core_policies_loaded = True
                abi_logging(f"[Y] Loaded MANDATORY core policies from {source['name']}")
            
            # Handle conflicts (higher priority wins, but core policies cannot be overridden)
            for policy_name, policy_content in source_policies.items():
                if policy_name in policies:
                    # Check if trying to override core policies
                    if 'abi_policies' in policy_name and source['priority'] < 1000:
                        abi_logging(f"[X] BLOCKED: Attempt to override core policy '{policy_name}' by {source['name']}", level="warning")
                        continue
                    else:
                        abi_logging(f"Policy '{policy_name}' overridden by {source['name']}")
                
                policies[policy_name] = policy_content
        
        # CRITICAL: Verify core policies were loaded
        if not core_policies_loaded:
            raise RuntimeError("CRITICAL: Core security policies not loaded - system cannot operate safely")
                
        abi_logging(f"[Y] Loaded {len(policies)} total policies (including mandatory core policies)")
        self.loaded_policies = policies
        return policies
    
    def _load_policies_from_source(self, source: Dict[str, Any]) -> Dict[str, str]:
        """Load .rego files from a specific source"""
        policies = {}
        source_path = Path(source['path'])
        
        if not source_path.exists():
            if source.get('required'):
                abi_logging(f"CRITICAL: Required policy source path does not exist: {source_path}", level="error")
                raise RuntimeError(f"Required policy source missing: {source_path}")
            else:
                abi_logging(f"Policy source path does not exist: {source_path}", level="warning")
                return policies
            
        # Find all .rego files recursively
        rego_files = list(source_path.rglob("*.rego"))
        
        for rego_file in rego_files:
            try:
                with open(rego_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Use relative path as policy name
                relative_path = rego_file.relative_to(source_path)
                policy_name = str(relative_path).replace('/', '_').replace('.rego', '')
                
                policies[policy_name] = content
                abi_logging(f"Loaded policy '{policy_name}' from {source['name']}", level="debug")
                
            except Exception as e:
                error_msg = f"Failed to load policy {rego_file}: {e}"
                if source.get('required'):
                    abi_logging(f"CRITICAL: {error_msg}", level="error")
                    raise RuntimeError(error_msg)
                else:
                    abi_logging(error_msg, level="error")
                
        abi_logging(f"Loaded {len(policies)} policies from {source['name']}")
        return policies
    
    def validate_policies(self) -> List[Dict[str, Any]]:
        """
        Validate loaded policies for common issues
        
        Returns:
            List of validation issues
        """
        issues = []
        
        # CRITICAL: Check for core policies
        core_policy_found = False
        for policy_name, content in self.loaded_policies.items():
            if 'abi_policies' in policy_name and 'package abi.core' in content:
                core_policy_found = True
                break
        
        if not core_policy_found:
            issues.append({
                'policy': 'SYSTEM',
                'type': 'CRITICAL_MISSING_CORE',
                'message': 'CRITICAL: Core security policies not found - system unsafe',
                'severity': 'CRITICAL'
            })
        
        for policy_name, content in self.loaded_policies.items():
            # Check for package declaration
            if 'package ' not in content:
                issues.append({
                    'policy': policy_name,
                    'type': 'missing_package',
                    'message': 'Policy missing package declaration',
                    'severity': 'ERROR'
                })
            
            # Check for basic syntax issues
            if content.count('{') != content.count('}'):
                issues.append({
                    'policy': policy_name,
                    'type': 'syntax_error',
                    'message': 'Mismatched braces in policy',
                    'severity': 'ERROR'
                })
            
            # Check for default rules (recommended)
            if 'default ' not in content:
                issues.append({
                    'policy': policy_name,
                    'type': 'missing_default',
                    'message': 'Policy missing default rules',
                    'severity': 'WARNING'
                })
        
        # Log critical issues
        critical_issues = [i for i in issues if i.get('severity') == 'CRITICAL']
        if critical_issues:
            abi_logging(f"[!] CRITICAL POLICY ISSUES FOUND: {len(critical_issues, level="error")}")
            for issue in critical_issues:
                abi_logging(f"[!] {issue['message']}", level="error")
                
        return issues
    
    def get_policy_manifest(self) -> Dict[str, Any]:
        """
        Generate a manifest of all loaded policies
        
        Returns:
            Manifest with policy metadata
        """
        sources = self.discover_policy_sources()
        
        manifest = {
            'version': '1.0.0',
            'generated_at': None,  # Will be set by caller
            'security_validated': True,
            'core_policies_loaded': any('abi_policies' in name for name in self.loaded_policies.keys()),
            'sources': sources,
            'policies': {}
        }
        
        for policy_name, content in self.loaded_policies.items():
            # Extract package name from policy content
            package_line = next((line for line in content.split('\n') 
                               if line.strip().startswith('package ')), '')
            package_name = package_line.replace('package ', '').strip() if package_line else 'unknown'
            
            # Determine if this is a core policy
            is_core = 'abi_policies' in policy_name and 'abi.core' in package_name
            
            manifest['policies'][policy_name] = {
                'package': package_name,
                'size_bytes': len(content.encode('utf-8')),
                'lines': len(content.split('\n')),
                'is_core_policy': is_core,
                'required': is_core
            }
            
        return manifest

# Singleton instance
_policy_loader = None

def get_policy_loader(base_policy_path: str = None) -> PolicyLoaderV2:
    """Get singleton policy loader instance"""
    global _policy_loader
    if _policy_loader is None:
        _policy_loader = PolicyLoaderV2(base_policy_path)
    return _policy_loader