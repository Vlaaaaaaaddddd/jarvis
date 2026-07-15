import asyncio
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END
from langchain_core.messages import ToolMessage, AIMessage, HumanMessage
from langchain_core.tools import BaseTool
from jarvis.core.state import TaskState
from jarvis.config import BaseLLM
from jarvis.utils.logger import get_logger

class TaskGraph:
    def __init__(self, llm: BaseLLM, tools: list[BaseTool]):
        self.llm = llm
        self.tools = {tool.name: tool for tool in tools} 
        self.graph = self._build_graph()
        self.logger = get_logger("TaskGraph")

    def _build_graph(self):
        """Конфигурирует узлы и ребра"""
        workflow = StateGraph(TaskState)

        # Добавляем логические узлы (Nodes)
        workflow.add_node("agent", self._agent_node)
        workflow.add_node("tools", self._tools_node)
        workflow.add_node("emergency_stop", self._emergency_node)

        # Указываем, с какого узла граф начинает работу
        workflow.set_entry_point("agent")

        # Настраиваем условные переходы (Edges) от узла "agent"
        workflow.add_conditional_edges(
            "agent", self._should_continue,
            {"continue": "tools", "end": END, "emergency": "emergency_stop"}
        )

        # Настраиваем безусловные переходы
        workflow.add_edge("tools", "agent")          # После инструментов всегда возвращаемся к LLM
        workflow.add_edge("emergency_stop", END)     # После ошибки всегда завершаем работу

        # Компилируем граф в исполняемый объект
        return workflow.compile()

    # УЗЛЫ (NODES) 

    async def _agent_node(self, state: TaskState) -> Dict[str, Any]:
        """Узел вызова LLM. Отвечает за генерацию следующего шага или ответа"""
        response = await self.llm.generate_stateless(state["messages"])

        self.logger.info(f"LLM Response: {response.content}")
        if response.tool_calls:
            self.logger.info(f"LLM requested tools: {[tc['name'] for tc in response.tool_calls]}")
        
        # Возвращаем новые данные для State. LangGraph сам приклеит response к списку messages
        return {"messages": [response], "steps_count": state.get("steps_count", 0) + 1}

    async def _tools_node(self, state: TaskState) -> Dict[str, Any]:
        last_message = state["messages"][-1]
        tasks = []
        for tc in last_message.tool_calls:
            tool_name = tc["name"]
            if tool_name in self.tools:
                tasks.append(self._execute_tool(self.tools[tool_name], tc["args"], tc["id"]))
            else:
                tasks.append(self._fake_tool_result(tool_name, tc["id"], "Ошибка: Инструмент не найден"))
        
        results = await asyncio.gather(*tasks)
        return {"messages": results}

    async def _emergency_node(self, state: TaskState) -> Dict[str, Any]:
        """Узел, который отрабатывает, если мы застряли в цикле"""
        msg = AIMessage(content="[СИСТЕМНОЕ СООБЩЕНИЕ] Выполнение прервано: превышен лимит шагов.")
        return {"messages": [msg], "is_completed": False}

    # ВСПОМОГАТЕЛЬНАЯ ЛОГИКА 

    async def _execute_tool(self, tool: BaseTool, args: dict, tool_id: str) -> ToolMessage:
        """Безопасная обертка для выполнения одного инструмента."""
        self.logger.debug(f"Tool {tool.name} called with args: {args}")
        try:
            # LangChain ainvoke сам валидирует аргументы!
            result = await tool.ainvoke(args)
            self.logger.debug(f"Tool {tool.name} result: {str(result)[:200]}")
        except Exception as e:
            self.logger.error(f"Error in {tool.name}: {str(e)}")
            result = f"Критическая ошибка выполнения {tool.name}: {str(e)}"
        
        return ToolMessage(content=str(result), name=tool.name, tool_call_id=tool_id)

    async def _fake_tool_result(self, name: str, tool_id: str, error_msg: str) -> ToolMessage:
        return ToolMessage(content=error_msg, name=name, tool_call_id=tool_id)

    def _should_continue(self, state: TaskState) -> Literal["continue", "end", "emergency"]:
        """Функция-маршрутизатор: определяет, куда граф пойдет дальше."""
        # ПРЕДОХРАНИТЕЛЬ (максимум 8 итераций)
        if state.get("steps_count", 0) >= 8:
            return "emergency"
        
        # Смотрим на последнее сообщение от агента
        last_message = state["messages"][-1]
        
        # Если агент хочет вызвать инструменты — направляем в узел tools
        if getattr(last_message, "tool_calls", None):
            return "continue"
            
        # Иначе агент выдал текстовый ответ — заканчиваем работу графа
        return "end"

    # ТОЧКА ВХОДА ИЗВНЕ 

    async def run(self, query: str) -> str:
        initial_state = {
            "messages": [HumanMessage(content=query)],
            "task_objective": query,
            "steps_count": 0,
            "is_completed": True
        }
        final_state = await self.graph.ainvoke(initial_state)
        return final_state["messages"][-1].content