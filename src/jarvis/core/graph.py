import asyncio
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END
from langchain_core.messages import ToolMessage, AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.tools import BaseTool
from jarvis.core.state import TaskState
from jarvis.config import BaseLLM
from jarvis.utils.logger import get_logger

class TaskGraph:
    def __init__(self, llm: BaseLLM, tools: list[BaseTool]):
        self.llm = llm
        self.tools = {tool.name: tool for tool in tools} 
        self.memory = MemorySaver() 
        self.graph = self._build_graph()
        self.logger = get_logger("TaskGraph")

    def _build_graph(self):
        """Конфигурирует узлы и ребра"""
        workflow = StateGraph(TaskState)

        # Добавляем логические узлы (Nodes)
        workflow.add_node("agent", self._agent_node)
        workflow.add_node("tools", self._tools_node)
        workflow.add_node("emergency_stop", self._emergency_node)
        workflow.add_node("human_approval", self._human_approval_node)
        workflow.add_node("commit_node", self._commit_node)  
        workflow.add_node("abort_node", self._abort_node)    

        workflow.add_edge("human_approval", "agent")

        # Указываем, с какого узла граф начинает работу
        workflow.set_entry_point("agent")

        # Настраиваем условные переходы (Edges) от узла "agent"
        workflow.add_conditional_edges(
            "agent",
            self._should_continue,
            {
                "continue": "tools", 
                "end": END, 
                "emergency": "emergency_stop",
                "approval": "human_approval"
            }
        )

        workflow.add_edge("tools", "agent")
        workflow.add_edge("emergency_stop", END)
        workflow.add_edge("commit_node", END)
        workflow.add_edge("abort_node", END)

        workflow.add_conditional_edges(
            "human_approval",
            self._after_approval,
            {
                "commit": "commit_node",
                "abort": "abort_node",
                "revise": "agent"
            }
        )

        return workflow.compile(
            checkpointer=self.memory,
            interrupt_before=["human_approval"]
        )

    # УЗЛЫ (NODES) 

    async def _agent_node(self, state: TaskState) -> Dict[str, Any]:
        """Узел вызова LLM. Отвечает за генерацию следующего шага или ответа"""
        response = await self.llm.generate_stateless(state["messages"])

        self.logger.info(f"LLM Response: {response.content}")
        if response.tool_calls:
            self.logger.info(f"LLM requested tools: {[tc['name'] for tc in response.tool_calls]}")

        update_data = {
            "messages": [response], 
            "steps_count": state.get("steps_count", 0) + 1
        }
        
        if getattr(response, "tool_calls", None):
            self.logger.info(f"LLM requested tools: {[tc['name'] for tc in response.tool_calls]}")
            for tc in response.tool_calls:
                if tc["name"] == "request_user_approval_tool":
                    args = tc["args"]
                    update_data["draft_plan"] = args.get("draft_plan")
                    update_data["draft_events"] = args.get("draft_events", [])
                    update_data["draft_tasks"] = args.get("draft_tasks", [])
        
        return update_data
    
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
    
    async def _human_approval_node(self, state: TaskState) -> Dict[str, Any]:
        user_approval = state.get("user_approval")
        user_feedback = state.get("user_feedback")
        messages = list(state.get("messages", []))
        
        last_ai_msg = messages[-1]
        tool_call_id = None
        if getattr(last_ai_msg, "tool_calls", None):
            for tc in last_ai_msg.tool_calls:
                if tc["name"] == "request_user_approval_tool":
                    tool_call_id = tc["id"]
                    break

        new_messages = []
        
        if tool_call_id:
            if user_approval is True:
                content = "[СИСТЕМА]: Статус: ОДОБРЕНО. План передан на автоматическую запись."
            elif user_approval is False:
                content = "[СИСТЕМА]: Статус: ОТКЛОНЕНО. Отмени выполнение задачи и сообщи пользователю."
            elif user_feedback:
                content = f"[СИСТЕМА]: Статус: ПРАВКИ. Пользователь просит изменить черновик: '{user_feedback}'. Сделай новую версию и снова вызови апрув."
            else:
                content = "[СИСТЕМА]: Статус неизвестен."

            new_messages.append(
                ToolMessage(content=content, name="request_user_approval_tool", tool_call_id=tool_call_id)
            )

        return {"messages": new_messages}

    async def _commit_node(self, state: TaskState) -> Dict[str, Any]:
        """Выполняет реальную запись в календарь на чистом Python без LLM."""
        events = state.get("draft_events") or []
        tasks = state.get("draft_tasks") or []
        
        # Извлекаем функции из твоих инструментов
        add_event_tool = self.tools.get("calendar_add_event_tool")
        add_task_tool = self.tools.get("calendar_add_task_tool")
        
        for ev in events:
            self.logger.info(f"Авто-запись события: {ev}")
            if add_event_tool:
                await add_event_tool.ainvoke(ev)
            await asyncio.sleep(0.5)
            
        for task in tasks:
            self.logger.info(f"Авто-запись задачи: {task}")
            if add_task_tool:
                await add_task_tool.ainvoke(task)
            await asyncio.sleep(0.5)
            
        # Формируем финальный ответ от ллм
        msg = AIMessage(content="Отлично, я внес все события и задачи в твой календарь.")
        return {"messages": [msg], "is_completed": True}
    
    async def _abort_node(self, state: TaskState) -> Dict[str, Any]:
        return {
            "messages": [AIMessage(content="Пользователь отменил план. Запись не произведена.")], 
            "is_completed": True,
            "draft_events": [],
            "draft_tasks": []
        }

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

    def _should_continue(self, state: TaskState) -> Literal["continue", "end", "emergency", "approval"]:
        """Функция-маршрутизатор: определяет, куда граф пойдет дальше."""
        # ПРЕДОХРАНИТЕЛЬ
        if state.get("steps_count", 0) >= 8:
            return "emergency"
        
        last_message = state["messages"][-1]
        
        # Если агент хочет вызвать инструменты
        if getattr(last_message, "tool_calls", None):
            # Если среди вызовов есть запрос аппрува — идем в узел human_approval
            for tool_call in last_message.tool_calls:
                if tool_call["name"] == "request_user_approval_tool":
                    return "approval"
            
            return "continue" # Обычные системные инструменты
            
        return "end"
            
        # Иначе агент выдал текстовый ответ — заканчиваем работу графа
        return "end"
    
    def _after_approval(self, state: TaskState) -> Literal["commit", "revise", "abort"]:
        if state.get("user_approval") is True:
            return "commit"
        elif state.get("user_approval") is False:
            return "abort"
        return "revise"


    # ТОЧКА ВХОДА 

    async def run(self, query: str, approval_status: str = None, thread_id: str = "default_thread") -> str:
        config = {"configurable": {"thread_id": thread_id}}
        
        # Проверяем, не висит ли граф на паузе в этом потоке
        current_state = self.graph.get_state(config)
        
        if current_state and current_state.next:
            # ИСПОЛЬЗУЕМ СТАТУС ОТ ВНЕШНЕГО АГЕНТА ВМЕСТО РЕГУЛЯРОК
            if approval_status == "approved":
                update_data = {"user_approval": True, "user_feedback": None}
            elif approval_status == "rejected":
                update_data = {"user_approval": False, "user_feedback": None}
            elif approval_status == "revised":
                update_data = {"user_approval": None, "user_feedback": query}
            else:
                # Надежный фолбек, если статус не передан
                user_input = query.lower()
                if any(w in user_input for w in ["да", "согласен", "отлично", "записывай"]):
                    update_data = {"user_approval": True}
                else:
                    update_data = {"user_approval": None, "user_feedback": query}
                
            self.graph.update_state(config, update_data)
            final_state = await self.graph.ainvoke(None, config)
        else:
            initial_state = {
                "messages": [HumanMessage(content=query)],
                "task_objective": query,
                "steps_count": 0,
                "is_completed": False,
                "draft_plan": None,
                "draft_events": [],
                "draft_tasks": [],
                "user_approval": None,
                "user_feedback": None
            }
            final_state = await self.graph.ainvoke(initial_state, config)

        checkpoint = self.graph.get_state(config)
        if checkpoint.next:
            last_message = final_state["messages"][-1]
            content = last_message.content
            
            if not content and getattr(last_message, "tool_calls", None):
                approval_call = next((tc for tc in last_message.tool_calls if tc["name"] == "request_user_approval_tool"), None)
                if approval_call:
                    content = f"Я подготовил черновик:\n{approval_call['args'].get('draft_plan', '')}"
            
            return f"{content}\n\n[СИСТЕМНЫЙ СТАТУС]: Требуется подтверждение. Озвучь черновик."

        return final_state["messages"][-1].content