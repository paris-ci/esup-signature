#!/usr/bin/env python3
"""
Convert nested environment variables to YAML templates.
Reads environment variables with double underscore separators and converts them
to nested YAML structure with proper data type detection.
Only includes values that override the defaults from application.yml.

To delete entire sections, use the DELETE__ prefix:
DELETE__SPRING__LDAP will remove the entire spring.ldap section
DELETE__LDAP will remove the entire ldap section
The root node will be kept intact with an empty value.
"""

import os
import yaml
import logging
import sys
from pathlib import Path
from tqdm import tqdm
from typing import Dict, Any, Union, List

# Configuration constants
DEFAULT_CONFIG_PATH = "/application.yml"
OUTPUT_FILE = "/tmp/application-docker.yml"
ENV_SEPARATOR = "__"
YAML_KEY_SEPARATOR = "-"
DELETE_PREFIX = "DELETE__"
LOG_LEVEL = logging.DEBUG

# Required database configuration
REQUIRED_DB_CONFIG = {
    "spring": {
        "datasource": {
            "driver-class-name": "org.postgresql.Driver",
            "url": "jdbc:postgresql://db:5432/esupsignature",
            "username": "esupsignature",
            "password": "esup",
            "hikari": {
                "auto-commit": False
            }
        },
        "jpa": {
            "hibernate": {
                "ddl-auto": "update"
            },
            "show-sql": False,
            "open-in-view": False
        }
    }
}

# Setup logging
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


def load_default_config() -> Dict[str, Any]:
    """
    Load default configuration from application.yml
    """
    try:
        config_path = Path(DEFAULT_CONFIG_PATH)
        if not config_path.exists():
            logger.error(f"Default configuration file not found at {DEFAULT_CONFIG_PATH}")
            sys.exit(1)
            
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load default configuration: {e}")
        sys.exit(1)


def convert_key_format(env_key: str) -> str:
    """
    Convert environment variable key format to YAML format.
    GLOBAL__ROOT_URL -> global.root-url
    """
    try:
        # Convert to lowercase and replace underscores with hyphens
        return env_key.lower().replace("_", YAML_KEY_SEPARATOR)
    except Exception as e:
        logger.error(f"Failed to convert key format for '{env_key}': {e}")
        raise


def detect_data_type(value: str) -> Union[str, int, float, bool]:
    """
    Detect and convert string values to appropriate data types.
    """
    if not isinstance(value, str):
        return value
    
    # Strip whitespace
    value = value.strip()
    
    # Boolean detection
    if value.lower() in ('true', 'yes', 'on'):
        return True
    elif value.lower() in ('false', 'no', 'off'):
        return False
    
    # Number detection
    try:
        # Try integer first
        if '.' not in value and 'e' not in value.lower():
            return int(value)
        # If there is 0 or 1 dot in the value, otherwise number only, try float
        elif value.count('.') <= 1 and value.replace('.', '').isdigit():
            return float(value)
    except ValueError:
        pass
    
    # Return as string if no conversion possible
    return value


def get_nested_value(config_dict: Dict[str, Any], keys: list) -> Any:
    """
    Get a value from a nested dictionary using a list of keys.
    """
    current = config_dict
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def clear_nested_dict(config_dict: Dict[str, Any], keys: list) -> None:
    """
    Clear a nested dictionary section while keeping the root node.
    """
    if not keys:
        return
        
    current = config_dict
    for key in keys[:-1]:
        if not isinstance(current, dict) or key not in current:
            return
        current = current[key]
    
    if isinstance(current, dict) and keys[-1] in current:
        # Instead of deleting, set to empty dict to keep the root node
        current[keys[-1]] = {}
        logger.debug(f"Cleared section: {'.'.join(keys)}")


def set_nested_dict(nested_dict: Dict[str, Any], keys: list, value: Any, default_config: Dict[str, Any]) -> None:
    """
    Set a value in a nested dictionary using a list of keys.
    Only sets the value if it differs from the default configuration.
    """
    try:
        # Get the default value
        default_value = get_nested_value(default_config, keys)
        typed_value = detect_data_type(value)
        
        # Only set if value differs from default
        if typed_value != default_value:
            current = nested_dict
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                elif not isinstance(current[key], dict):
                    logger.error(f"Conflict: '{key}' already exists as non-dict value")
                    raise ValueError(f"Key conflict at '{key}'")
                current = current[key]
            
            # Set the final value
            current[keys[-1]] = typed_value
            logger.debug(f"Setting override: {'.'.join(keys)} = {typed_value} (default was {default_value})")
        
    except Exception as e:
        logger.error(f"Failed to set nested dict for keys {keys}: {e}")
        raise


def parse_environment_variables() -> tuple[Dict[str, Any], List[List[str]]]:
    """
    Parse environment variables and convert to nested dictionary structure.
    Returns a tuple of (config_dict, keys_to_delete)
    """
    nested_config = {}
    keys_to_delete = []
    env_vars = [(k, v) for k, v in os.environ.items() if ENV_SEPARATOR in k]
    
    if not env_vars:
        logger.warning(f"No environment variables found with separator '{ENV_SEPARATOR}'")
        return nested_config, keys_to_delete
    
    logger.info(f"Found {len(env_vars)} environment variables to process")
    
    for env_key, env_value in tqdm(env_vars, desc="Processing environment variables"):
        try:
            # Check if this is a delete command
            if env_key.startswith(DELETE_PREFIX):
                # Convert the key parts to YAML format
                key_parts = env_key[len(DELETE_PREFIX):].split(ENV_SEPARATOR)
                yaml_keys = [convert_key_format(part) for part in key_parts]
                keys_to_delete.append(yaml_keys)
                logger.debug(f"Marked for deletion: {'.'.join(yaml_keys)}")
                continue
            
            # Split by separator and convert format
            key_parts = env_key.split(ENV_SEPARATOR)
            yaml_keys = [convert_key_format(part) for part in key_parts]
            
            logger.debug(f"Converting {env_key} -> {'.'.join(yaml_keys)} = {env_value}")
            
            # Set in nested dictionary
            set_nested_dict(nested_config, yaml_keys, env_value, {})
            
        except Exception as e:
            logger.error(f"Failed to process environment variable '{env_key}': {e}")
            raise
    
    return nested_config, keys_to_delete


# Deep merge the environment configuration
def deep_merge(source, destination):
    for key, value in source.items():
        if isinstance(value, dict):
            if key not in destination:
                destination[key] = {}
            deep_merge(value, destination[key])
        else:
            destination[key] = value


def process_config(default_config: Dict[str, Any], env_config: Dict[str, Any], keys_to_delete: List[List[str]]) -> Dict[str, Any]:
    """
    Process the configuration in the correct order:
    1. Start with default config
    2. Apply deletions (keeping root nodes)
    3. Apply environment variables
    4. Ensure required database configuration
    """
    # Start with a copy of the default configuration
    final_config = default_config.copy()

    # Ensure required database configuration is present
    deep_merge(REQUIRED_DB_CONFIG, final_config)
    
    # Apply deletions first (keeping root nodes)
    for keys in keys_to_delete:
        clear_nested_dict(final_config, keys)

    # Apply environment config
    deep_merge(env_config, final_config)

    return final_config


def write_yaml_file(config_dict: Dict[str, Any], output_path: str) -> None:
    """
    Write configuration dictionary to YAML file.
    """
    try:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        yaml_config_str = yaml.dump(
            config_dict,
            default_flow_style=False,
            sort_keys=True,
            indent=2,
            allow_unicode=True
        )

        logger.debug(f"YAML configuration:\n{yaml_config_str}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(yaml_config_str)
        
        logger.info(f"Successfully wrote YAML configuration to {output_path}")
        
    except Exception as e:
        logger.error(f"Failed to write YAML file '{output_path}': {e}")
        raise


def main():
    """
    Main function to orchestrate the conversion process.
    """
    try:
        logger.info("Starting environment variables to YAML conversion")
        
        # Load default configuration
        default_config = load_default_config()
        logger.info("Loaded default configuration from application.yml")
        
        # Parse environment variables
        env_config, keys_to_delete = parse_environment_variables()
        
        # Process configurations in the correct order
        final_config = process_config(default_config, env_config, keys_to_delete)
        
        # Write to YAML file
        write_yaml_file(final_config, OUTPUT_FILE)
        
        logger.info(f"Conversion completed successfully. Output written to {OUTPUT_FILE}")
        
        # Print summary
        total_keys = sum(len(str(final_config).split()) for _ in [final_config])
        logger.info(f"Processed configuration with {len(final_config)} top-level sections")

        
    except Exception as e:
        logger.error(f"Conversion failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()