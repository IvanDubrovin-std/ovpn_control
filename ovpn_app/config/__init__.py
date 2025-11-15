"""
Configuration module for OpenVPN management
Centralized configuration following Clean Code principles
"""

from .constants import *
from .agent_config import AgentConfig

__all__ = ['AgentConfig', 'DEFAULT_SUBNET', 'DEFAULT_NETMASK', 'OVPN_CONFIG_PATH']
