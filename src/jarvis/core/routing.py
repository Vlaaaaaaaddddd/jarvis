from typing import Literal
from jarvis.core.state import TaskState

def route_from_supervisor(state: TaskState) -> Literal["calendar_agent", "research_agent", "end", "emergency"]:
    if state.get("steps_count", 0) >= 12:
        return "emergency"

    raw_content = state["messages"][-1].content
    
    if isinstance(raw_content, list):
        text_content = " ".join([block.get("text", "") for block in raw_content if isinstance(block, dict)])
    else:
        # Если пришла обычная строка
        text_content = str(raw_content)
        
    last_msg = text_content.upper()
    
    if "НАПРАВЛЕНИЕ: CALENDARAGENT" in last_msg:
        return "calendar_agent"
    elif "НАПРАВЛЕНИЕ: RESEARCHAGENT" in last_msg:
        return "research_agent"
    else:
        return "end" # кончил или не распознал команду

def should_continue(state: TaskState) -> Literal["continue", "supervisor", "emergency", "approval", "clarification"]:
    """Куда идти специалисту после его хода"""
    if state.get("steps_count", 0) >= 12:
        return "emergency"
    
    last_message = state["messages"][-1]
    
    if getattr(last_message, "tool_calls", None):
        for tool_call in last_message.tool_calls:
            if tool_call["name"] == "request_user_approval_tool":
                return "approval"
            if tool_call["name"] == "ask_user_clarification_tool":
                return "clarification"
        return "continue"
        
    return "supervisor"

def route_from_tools(state: TaskState) -> Literal["calendar_agent", "research_agent"]:
    """Возвращает ход тому агенту, который запрашивал инструмент"""
    sender = state.get("sender", "calendar_agent") # по умолчанию фолбек
    if sender == "research_agent":
        return "research_agent"
    return "calendar_agent"

def after_approval(state: TaskState) -> Literal["commit", "revise", "abort"]:
    if state.get("user_approval") is True:
        return "commit"
    elif state.get("user_approval") is False:
        return "abort"
    return "revise"

