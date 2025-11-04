import os
import logging
from pathlib import Path
from typing import List, Dict, Any
import importlib.util

logger = logging.getLogger(__name__)

class PolicyLoader:
    """
    Loads OPA policies from multiple sources:
    1. Built-in policies from guardial.opa.policies
    2. User-defined policies from ./policies/ directory
    3. Package-installed policies from other modules
    """
    
    def __init__(self, base_policy_path: str = None):
        self.base_policy_path = base_policy_path or "./opa"
        self.loaded_policies = {}
        
    def discover_policy_sources(self) -> List[Dict[str, Any]]:
        """
        Discover all available policy sources
        
        Returns:
            List of policy source configurations
        """
        sources = []
        
        # 1. Built-in ABI policies (from guardial package)
        try:
            import guardial.opa.policies
            builtin_path = Path(guardial.opa.policies.__file__).parent
            sources.append({
                'name': 'abi-builtin',
                'type': 'package',
                'path': str(builtin_path),
                'priority': 100,  # Highest priority
                'description': 'Built-in ABI policies'
            })
        except ImportError:
            logger.warning("Built-in ABI policies not found")
        
        # 2. Local policies directory
        local_policies = Path(self.base_policy_path)
        if local_policies.exists():
            sources.append({
                'name': 'local',
                'type': 'directory',
                'path': str(local_policies),
                'priority': 50,
                'description': 'Local project policies'
            })
        
        # 3. Environment-specified policy paths
        env_policies = os.getenv('ABI_POLICY_PATHS', '')
        if env_policies:
            for path in env_policies.split(':'):
                if Path(path).exists():
                    sources.append({
                        'name': f'env-{Path(path).name}',
                        'type': 'directory', 
                        'path': path,
                        'priority': 75,
                        'description': f'Environment policy: {path}'
                    })
        
        # 4. Discover installed policy packages
        installed_sources = self._discover_installed_policies()
        sources.extend(installed_sources)
        
        # Sort by priority (highest first)
        sources.sort(key=lambda x: x['priority'], reverse=True)
        
        logger.info(f"Discovered {len(sources)} policy sources")
        for source in sources:
            logger.info(f"  - {source['name']}: {source['description']}")
            
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
                                'description': f'Installed policy package: {dist.project_name}'
                            })
                    except Exception as e:
                        logger.warning(f"Failed to load policy package {dist.project_name}: {e}")
                        
        except ImportError:
            logger.debug("pkg_resources not available for policy discovery")
            
        return sources
    
    def load_all_policies(self) -> Dict[str, str]:
        """
        Load all .rego policy files from discovered sources
        
        Returns:
            Dictionary mapping policy names to policy content
        """
        policies = {}
        sources = self.discover_policy_sources()
        
        for source in sources:
            source_policies = self._load_policies_from_source(source)
            
            # Handle conflicts (higher priority wins)
            for policy_name, policy_content in source_policies.items():
                if policy_name in policies:
                    logger.info(f"Policy '{policy_name}' overridden by {source['name']}")
                policies[policy_name] = policy_content
                
        logger.info(f"Loaded {len(policies)} total policies")
        self.loaded_policies = policies
        return policies
    
    def _load_policies_from_source(self, source: Dict[str, Any]) -> Dict[str, str]:
        """Load .rego files from a specific source"""
        policies = {}
        source_path = Path(source['path'])
        
        if not source_path.exists():
            logger.warning(f"Policy source path does not exist: {source_path}")
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
                logger.debug(f"Loaded policy '{policy_name}' from {source['name']}")
                
            except Exception as e:
                logger.error(f"Failed to load policy {rego_file}: {e}")
                
        logger.info(f"Loaded {len(policies)} policies from {source['name']}")
        return policies
    
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
            'sources': sources,
            'policies': {}
        }
        
        for policy_name, content in self.loaded_policies.items():
            # Extract package name from policy content
            package_line = next((line for line in content.split('\n') 
                               if line.strip().startswith('package ')), '')
            package_name = package_line.replace('package ', '').strip() if package_line else 'unknown'
            
            manifest['policies'][policy_name] = {
                'package': package_name,
                'size_bytes': len(content.encode('utf-8')),
                'lines': len(content.split('\n'))
            }
            
        return manifest
    
    def validate_policies(self) -> List[Dict[str, Any]]:
        """
        Validate loaded policies for common issues
        
        Returns:
            List of validation issues
        """
        issues = []
        
        for policy_name, content in self.loaded_policies.items():
            # Check for package declaration
            if 'package ' not in content:
                issues.append({
                    'policy': policy_name,
                    'type': 'missing_package',
                    'message': 'Policy missing package declaration'
                })
            
            # Check for basic syntax issues
            if content.count('{') != content.count('}'):
                issues.append({
                    'policy': policy_name,
                    'type': 'syntax_error',
                    'message': 'Mismatched braces in policy'
                })
            
            # Check for default rules
            if 'default ' not in content:
                issues.append({
                    'policy': policy_name,
                    'type': 'missing_default',
                    'message': 'Policy missing default rules'
                })
                
        return issues