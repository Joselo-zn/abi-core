import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class OPAConfig:
    """
    OPA Configuration management for ABI
    
    Handles configuration loading from multiple sources:
    1. Default built-in config
    2. Environment variables
    3. Local config files
    4. Runtime overrides
    """
    
    DEFAULT_CONFIG = {
        'opa': {
            'url': 'http://opa:8181',
            'timeout': 30,
            'retry_attempts': 3,
            'retry_delay': 1
        },
        'policies': {
            'base_path': './policies',
            'auto_reload': True,
            'validation_enabled': True,
            'bundle_name': 'abi'
        },
        'logging': {
            'level': 'INFO',
            'audit_enabled': True,
            'decision_logs': True
        },
        'security': {
            'fail_safe_mode': 'deny',  # deny | allow | warn
            'require_opa': True,
            'cache_decisions': False
        }
    }
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config = self.DEFAULT_CONFIG.copy()
        self._load_configuration()
    
    def _load_configuration(self):
        """Load configuration from all sources in priority order"""
        
        # 1. Start with defaults
        config = self.DEFAULT_CONFIG.copy()
        
        # 2. Load from config file if specified
        if self.config_path:
            file_config = self._load_config_file(self.config_path)
            config = self._merge_configs(config, file_config)
        
        # 3. Look for standard config locations
        standard_locations = [
            './config/opa.yaml',
            './config/opa.yml', 
            './opa.yaml',
            './opa.yml',
            os.path.expanduser('~/.abi/opa.yaml'),
            '/etc/abi/opa.yaml'
        ]
        
        for location in standard_locations:
            if Path(location).exists():
                file_config = self._load_config_file(location)
                config = self._merge_configs(config, file_config)
                logger.info(f"Loaded OPA config from {location}")
                break
        
        # 4. Override with environment variables
        env_config = self._load_env_config()
        config = self._merge_configs(config, env_config)
        
        self.config = config
        logger.info("OPA configuration loaded successfully")
    
    def _load_config_file(self, path: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Failed to load config file {path}: {e}")
            return {}
    
    def _load_env_config(self) -> Dict[str, Any]:
        """Load configuration from environment variables"""
        config = {}
        
        # OPA settings
        if os.getenv('OPA_URL'):
            config.setdefault('opa', {})['url'] = os.getenv('OPA_URL')
        
        if os.getenv('OPA_TIMEOUT'):
            config.setdefault('opa', {})['timeout'] = int(os.getenv('OPA_TIMEOUT'))
        
        # Policy settings
        if os.getenv('ABI_POLICY_PATHS'):
            config.setdefault('policies', {})['base_path'] = os.getenv('ABI_POLICY_PATHS')
        
        if os.getenv('ABI_POLICY_AUTO_RELOAD'):
            config.setdefault('policies', {})['auto_reload'] = os.getenv('ABI_POLICY_AUTO_RELOAD').lower() == 'true'
        
        # Security settings
        if os.getenv('ABI_FAIL_SAFE_MODE'):
            config.setdefault('security', {})['fail_safe_mode'] = os.getenv('ABI_FAIL_SAFE_MODE')
        
        if os.getenv('ABI_REQUIRE_OPA'):
            config.setdefault('security', {})['require_opa'] = os.getenv('ABI_REQUIRE_OPA').lower() == 'true'
        
        # Logging settings
        if os.getenv('OPA_LOG_LEVEL'):
            config.setdefault('logging', {})['level'] = os.getenv('OPA_LOG_LEVEL')
        
        return config
    
    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two configuration dictionaries"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
                
        return result
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation
        
        Example: config.get('opa.url') -> 'http://opa:8181'
        """
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
                
        return value
    
    def set(self, key_path: str, value: Any):
        """
        Set configuration value using dot notation
        
        Example: config.set('opa.url', 'http://localhost:8181')
        """
        keys = key_path.split('.')
        target = self.config
        
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]
            
        target[keys[-1]] = value
    
    def to_opa_config(self) -> Dict[str, Any]:
        """
        Generate OPA server configuration
        
        Returns:
            OPA-compatible configuration dictionary
        """
        return {
            'services': {
                'authz': {
                    'url': self.get('opa.url')
                }
            },
            'bundles': {
                self.get('policies.bundle_name', 'abi'): {
                    'resource': f"/v1/bundles/{self.get('policies.bundle_name', 'abi')}",
                    'service': 'authz',
                    'polling': {
                        'min_delay_seconds': 10,
                        'max_delay_seconds': 20
                    }
                }
            },
            'decision_logs': {
                'console': self.get('logging.decision_logs', True),
                'reporting': {
                    'min_delay_seconds': 5,
                    'max_delay_seconds': 10
                }
            },
            'status': {
                'console': True
            },
            'default_decision': f"/{self.get('policies.bundle_name', 'abi')}/policies/allow"
        }
    
    def save_config(self, path: str):
        """Save current configuration to file"""
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False)
            logger.info(f"Configuration saved to {path}")
        except Exception as e:
            logger.error(f"Failed to save configuration to {path}: {e}")
    
    def validate(self) -> List[str]:
        """
        Validate configuration
        
        Returns:
            List of validation errors
        """
        errors = []
        
        # Check required fields
        if not self.get('opa.url'):
            errors.append("OPA URL is required")
        
        # Check timeout values
        timeout = self.get('opa.timeout')
        if timeout and (not isinstance(timeout, int) or timeout <= 0):
            errors.append("OPA timeout must be a positive integer")
        
        # Check fail-safe mode
        fail_safe = self.get('security.fail_safe_mode')
        if fail_safe not in ['deny', 'allow', 'warn']:
            errors.append("Fail-safe mode must be 'deny', 'allow', or 'warn'")
        
        return errors

# Global configuration instance
_opa_config = None

def get_opa_config(config_path: Optional[str] = None) -> OPAConfig:
    """Get singleton OPA configuration instance"""
    global _opa_config
    if _opa_config is None:
        _opa_config = OPAConfig(config_path)
    return _opa_config