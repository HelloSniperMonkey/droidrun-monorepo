"""Agent factory with smart fallback logic for Job Hunter

This module provides a unified interface for getting the appropriate agent
based on configuration and availability. It handles:

1. EXECUTION_MODE = "local" -> Use DroidRun directly
2. EXECUTION_MODE = "cloud" -> Use MobileRun, with fallback to DroidRun if:
   - MobileRun API fails
   - AND a local ADB device is connected
"""
from typing import Union, Callable, Any
from functools import wraps

from job_hunter.config import Config


class AgentError(Exception):
    """Base exception for agent-related errors"""
    pass


class CloudAgentError(AgentError):
    """Error from MobileRun Cloud agent"""
    pass


class LocalAgentError(AgentError):
    """Error from DroidRun local agent"""
    pass


def get_agent():
    """
    Get the appropriate agent based on EXECUTION_MODE config.

    Returns:
        MobileRunAgent or DroidRunAgent instance

    Raises:
        AgentError: If no agent can be initialized
    """
    mode = Config.EXECUTION_MODE

    if mode == "local":
        return _get_local_agent()
    else:  # cloud mode
        return _get_cloud_agent()


def _get_local_agent():
    """Get DroidRun local agent"""
    from job_hunter.droidrun_backup import DroidRunAgent

    agent = DroidRunAgent()
    if not agent.is_available():
        raise LocalAgentError(
            f"DroidRun agent not available: {agent.error_message}. "
            "Check that: 1) ADB device is connected, 2) droidrun is installed, "
            "3) GEMINI_API_KEY is set."
        )
    return agent


def _get_cloud_agent():
    """Get MobileRun cloud agent"""
    from job_hunter.mobilerun_agent import MobileRunAgent

    try:
        agent = MobileRunAgent()
        return agent
    except Exception as e:
        raise CloudAgentError(f"Failed to initialize MobileRun agent: {e}")


class FallbackAgent:
    """
    Wrapper agent that tries MobileRun first, then falls back to DroidRun.

    This is used when EXECUTION_MODE = "cloud" but we want automatic fallback
    if the cloud API fails and a local device is available.
    """

    def __init__(self):
        self._primary_agent = None
        self._fallback_agent = None
        self._using_fallback = False
        self._initialize_agents()

    def _initialize_agents(self):
        """Initialize primary (cloud) and fallback (local) agents"""
        # Try to initialize primary (cloud) agent
        try:
            from job_hunter.mobilerun_agent import MobileRunAgent
            self._primary_agent = MobileRunAgent()
            print("FallbackAgent: MobileRun Cloud agent initialized")
        except Exception as e:
            print(f"FallbackAgent: MobileRun Cloud failed to initialize: {e}")

        # Check if fallback is available
        if Config.should_fallback_to_local():
            try:
                from job_hunter.droidrun_backup import DroidRunAgent
                agent = DroidRunAgent()
                if agent.is_available():
                    self._fallback_agent = agent
                    print("FallbackAgent: DroidRun local fallback available")
            except Exception as e:
                print(f"FallbackAgent: DroidRun fallback failed: {e}")

        if not self._primary_agent and not self._fallback_agent:
            raise AgentError("No agent available: both MobileRun and DroidRun failed")

    def _execute_with_fallback(self, method_name: str, *args, **kwargs):
        """Execute a method with automatic fallback"""
        # Try primary agent first
        if self._primary_agent and not self._using_fallback:
            try:
                method = getattr(self._primary_agent, method_name)
                return method(*args, **kwargs)
            except Exception as e:
                print(f"FallbackAgent: Primary agent failed for {method_name}: {e}")
                # Check if we should fallback
                if self._fallback_agent:
                    print("FallbackAgent: Switching to local DroidRun fallback")
                    self._using_fallback = True
                else:
                    raise CloudAgentError(f"MobileRun failed and no fallback available: {e}")

        # Use fallback agent
        if self._fallback_agent:
            try:
                method = getattr(self._fallback_agent, method_name)
                return method(*args, **kwargs)
            except Exception as e:
                raise LocalAgentError(f"DroidRun fallback also failed: {e}")

        raise AgentError("No agent available to execute request")

    # Proxy all agent methods
    def create_task(self, *args, **kwargs):
        return self._execute_with_fallback("create_task", *args, **kwargs)

    def get_task_status(self, task_id: str):
        return self._execute_with_fallback("get_task_status", task_id)

    def search_jobs_on_portal(self, *args, **kwargs):
        return self._execute_with_fallback("search_jobs_on_portal", *args, **kwargs)

    def apply_to_job(self, *args, **kwargs):
        return self._execute_with_fallback("apply_to_job", *args, **kwargs)

    def google_search_jobs(self, *args, **kwargs):
        return self._execute_with_fallback("google_search_jobs", *args, **kwargs)

    def is_using_fallback(self) -> bool:
        """Check if currently using fallback agent"""
        return self._using_fallback

    def get_agent_type(self) -> str:
        """Get the type of agent currently being used"""
        if self._using_fallback:
            return "droidrun_local"
        return "mobilerun_cloud"


def get_agent_with_fallback():
    """
    Get an agent with automatic fallback capability.

    In cloud mode, returns a FallbackAgent that tries MobileRun first
    and falls back to DroidRun if available.

    In local mode, returns DroidRunAgent directly.

    Returns:
        FallbackAgent, MobileRunAgent, or DroidRunAgent
    """
    mode = Config.EXECUTION_MODE

    if mode == "local":
        return _get_local_agent()
    else:
        # Cloud mode with fallback
        return FallbackAgent()


# For backwards compatibility and simple usage
def create_agent(use_fallback: bool = True):
    """
    Factory function to create the appropriate agent.

    Args:
        use_fallback: If True and in cloud mode, enables automatic fallback
                      to local DroidRun if MobileRun fails.

    Returns:
        Agent instance (MobileRunAgent, DroidRunAgent, or FallbackAgent)
    """
    if use_fallback:
        return get_agent_with_fallback()
    return get_agent()
