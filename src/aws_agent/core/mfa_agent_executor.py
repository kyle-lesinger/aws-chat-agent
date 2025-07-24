"""Custom Agent Executor that propagates MFA exceptions."""

from typing import Any, Dict, List, Optional, Sequence, Union
from langchain.agents import AgentExecutor
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.callbacks import CallbackManagerForChainRun, AsyncCallbackManagerForChainRun
from langchain_core.tools import BaseTool

from ..credentials.providers import MFARequiredException


class MFAAgentExecutor(AgentExecutor):
    """Custom AgentExecutor that propagates MFARequiredException."""
    
    def _take_next_step(
        self,
        name_to_tool_map: Dict[str, BaseTool],
        color_mapping: Dict[str, str],
        inputs: Dict[str, str],
        intermediate_steps: List[tuple[AgentAction, str]],
        run_manager: Optional[CallbackManagerForChainRun] = None,
    ) -> Union[AgentFinish, List[tuple[AgentAction, str]]]:
        """Override to propagate MFA exceptions."""
        try:
            return super()._take_next_step(
                name_to_tool_map,
                color_mapping,
                inputs,
                intermediate_steps,
                run_manager,
            )
        except MFARequiredException:
            # Re-raise MFA exception without catching it
            raise
        except Exception:
            # Let parent class handle other exceptions
            raise
    
    def _call(
        self,
        inputs: Dict[str, str],
        run_manager: Optional[CallbackManagerForChainRun] = None,
    ) -> Dict[str, Any]:
        """Override to propagate MFA exceptions."""
        try:
            return super()._call(inputs, run_manager)
        except MFARequiredException:
            # Re-raise MFA exception without catching it
            raise
        except Exception:
            # Let parent class handle other exceptions
            raise
    
    async def _atake_next_step(
        self,
        name_to_tool_map: Dict[str, BaseTool],
        color_mapping: Dict[str, str],
        inputs: Dict[str, str],
        intermediate_steps: List[tuple[AgentAction, str]],
        run_manager: Optional[AsyncCallbackManagerForChainRun] = None,
    ) -> Union[AgentFinish, List[tuple[AgentAction, str]]]:
        """Async override to propagate MFA exceptions."""
        try:
            return await super()._atake_next_step(
                name_to_tool_map,
                color_mapping,
                inputs,
                intermediate_steps,
                run_manager,
            )
        except MFARequiredException:
            # Re-raise MFA exception without catching it
            raise
        except Exception:
            # Let parent class handle other exceptions
            raise
    
    async def _acall(
        self,
        inputs: Dict[str, str],
        run_manager: Optional[AsyncCallbackManagerForChainRun] = None,
    ) -> Dict[str, Any]:
        """Async override to propagate MFA exceptions."""
        try:
            return await super()._acall(inputs, run_manager)
        except MFARequiredException:
            # Re-raise MFA exception without catching it
            raise
        except Exception:
            # Let parent class handle other exceptions
            raise