#!/usr/bin/env python3
"""
Convert nested environment variables to YAML templates.
Reads environment variables with double underscore separators and converts them
to nested YAML structure with proper data type detection.
"""

import os
import yaml
import logging
import sys
from pathlib import Path
from tqdm import tqdm
from typing import Dict, Any, Union

# Configuration constants
OUTPUT_FILE = "/tmp/application-docker.yml"
ENV_SEPARATOR = "__"
YAML_KEY_SEPARATOR = "-"
LOG_LEVEL = logging.INFO

# Setup logging
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


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
    if value.lower() in ('true', 'yes', '1', 'on'):
        return True
    elif value.lower() in ('false', 'no', '0', 'off'):
        return False
    
    # Number detection
    try:
        # Try integer first
        if '.' not in value and 'e' not in value.lower():
            return int(value)
        else:
            # Try float
            return float(value)
    except ValueError:
        pass
    
    # Return as string if no conversion possible
    return value


def set_nested_dict(nested_dict: Dict[str, Any], keys: list, value: Any) -> None:
    """
    Set a value in a nested dictionary using a list of keys.
    """
    try:
        current = nested_dict
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            elif not isinstance(current[key], dict):
                logger.error(f"Conflict: '{key}' already exists as non-dict value")
                raise ValueError(f"Key conflict at '{key}'")
            current = current[key]
        
        # Set the final value with type detection
        final_key = keys[-1]
        typed_value = detect_data_type(value)
        current[final_key] = typed_value
        
    except Exception as e:
        logger.error(f"Failed to set nested dict for keys {keys}: {e}")
        raise


def parse_environment_variables() -> Dict[str, Any]:
    """
    Parse environment variables and convert to nested dictionary structure.
    """
    nested_config = {}
    env_vars = [(k, v) for k, v in os.environ.items() if ENV_SEPARATOR in k]
    
    if not env_vars:
        logger.warning(f"No environment variables found with separator '{ENV_SEPARATOR}'")
        return nested_config
    
    logger.info(f"Found {len(env_vars)} environment variables to process")
    
    for env_key, env_value in tqdm(env_vars, desc="Processing environment variables"):
        try:
            # Split by separator and convert format
            key_parts = env_key.split(ENV_SEPARATOR)
            yaml_keys = [convert_key_format(part) for part in key_parts]
            
            logger.debug(f"Converting {env_key} -> {'.'.join(yaml_keys)} = {env_value}")
            
            # Set in nested dictionary
            set_nested_dict(nested_config, yaml_keys, env_value)
            
        except Exception as e:
            logger.error(f"Failed to process environment variable '{env_key}': {e}")
            raise
    
    return nested_config


def write_yaml_file(config_dict: Dict[str, Any], output_path: str) -> None:
    """
    Write configuration dictionary to YAML file.
    """
    try:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(
                config_dict,
                f,
                default_flow_style=False,
                sort_keys=True,
                indent=2,
                allow_unicode=True
            )
        
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
        
        # Parse environment variables
        config_dict = parse_environment_variables()
        
        if not config_dict:
            logger.warning("No configuration generated - no matching environment variables found")
            return
        
        # Write to YAML file
        write_yaml_file(config_dict, OUTPUT_FILE)
        
        logger.info(f"Conversion completed successfully. Output written to {OUTPUT_FILE}")
        
        # Print summary
        total_keys = sum(len(str(config_dict).split()) for _ in [config_dict])
        logger.info(f"Processed configuration with {len(config_dict)} top-level sections")
        
    except Exception as e:
        logger.error(f"Conversion failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()