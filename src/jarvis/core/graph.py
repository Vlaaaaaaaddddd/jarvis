import asyncio
from datetime import datetime
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END
from langchain_core.messages import ToolMessage, AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.tools import BaseTool
from jarvis.services.embeddings import EmbeddingService
from jarvis.db.repository import PostgresRepository

from jarvis.core.state import TaskState
from jarvis.config import BaseLLM, months, weekdays, supervisor_prompt, calendar_agent_prompt, research_agent_prompt
from jarvis.utils.logger import get_logger

class TaskGraph:
    def __init__(
            self, 
            llm: BaseLLM, 
            tools: list[BaseTool], 
            repository: PostgresRepository,        
            embedding_service: EmbeddingService
            ):
        self.llm = llm
        self.tools = {tool.name: tool for tool in tools} 
        self.repository = repository
        self.embedding_service = embedding_service
        self.memory = MemorySaver() 
        self.graph = self._build_graph()
        self.logger = get_logger("TaskGraph")

    def _build_graph(self):
        """Конфигурирует узлы и ребра мультиагентного графа"""
        workflow = StateGraph(TaskState)

        # sузлы специалистов и координатора
        workflow.add_node("supervisor", self._supervisor_node)
        workflow.add_node("calendar_agent", self._calendar_agent_node)
        workflow.add_node("research_agent", self._research_agent_node)
        
        # системные узлы
        workflow.add_node("tools", self._tools_node)
        workflow.add_node("emergency_stop", self._emergency_node)
        workflow.add_node("human_approval", self._human_approval_node)
        workflow.add_node("commit_node", self._commit_node)  
        workflow.add_node("abort_node", self._abort_node)    

        workflow.add_node("prefetch_node", self._prefetch_node)

        # Точка входа
        workflow.set_entry_point("prefetch_node")

        workflow.add_edge("prefetch_node", "supervisor")

        # Маршрутизация от Супервизора
        workflow.add_conditional_edges(
            "supervisor",
            self._route_from_supervisor,
            {
                "calendar_agent": "calendar_agent",
                "research_agent": "research_agent",
                "end": END,
                "emergency": "emergency_stop"
            }
        )

        # Маршрутизация от CalendarAgent
        workflow.add_conditional_edges(
            "calendar_agent",
            self._should_continue,
            {
                "continue": "tools", 
                "supervisor": "supervisor",
                "emergency": "emergency_stop",
                "approval": "human_approval"
            }
        )

        # Маршрутизация от ResearchAgent
        workflow.add_conditional_edges(
            "research_agent",
            self._should_continue,
            {
                "continue": "tools", 
                "supervisor": "supervisor",
                "emergency": "emergency_stop",
                "approval": "human_approval"
            }
        )

        # Маршрутизация от Инструментов (возврат к тому, кто вызвал)
        workflow.add_conditional_edges(
            "tools",
            self._route_from_tools,
            {
                "calendar_agent": "calendar_agent",
                "research_agent": "research_agent"
            }
        )

        # Завершающие переходы
        workflow.add_edge("emergency_stop", END)
        workflow.add_edge("commit_node", END)
        workflow.add_edge("abort_node", END)

        # Переходы от узла согласования
        workflow.add_conditional_edges(
            "human_approval",
            self._after_approval,
            {
                "commit": "commit_node",
                "abort": "abort_node",
                "revise": "calendar_agent" # Правки возвращаются в календарный узел
            }
        )

        return workflow.compile(
            checkpointer=self.memory,
            interrupt_before=["human_approval"]
        )

    # УЗЛЫ (NODES) 

    async def _prefetch_node(self, state: TaskState) -> Dict[str, Any]:
        """вытаскивает контекст из памяти перед началом работы"""
        self.logger.info("--- [NODE] PREFETCH (RAG) ---")

        # исходный запрос пользователя
        user_query = state["messages"][-1].content
        
        if not user_query or not isinstance(user_query, str) or not user_query.strip():
            return {"sender": "prefetch"}

        try:
            # Генерируем вектор
            query_vector = await self.embedding_service.get_embedding(user_query)
            if not query_vector:
                self.logger.warning("Prefetch: Не удалось сгенерировать вектор для поиска.")
                return {"sender": "prefetch"}

            # Ищем релевантные воспоминания 
            memories = await self.repository.search_vector_memory(query_vector, limit=3)
            
            if not memories:
                self.logger.info("Prefetch: В долговременной памяти не найдено релевантных записей.")
                return {"sender": "prefetch"}

            # Форматируем результаты для системного промпта агентов
            formatted_results = ["[ВНУТРЕННЯЯ ПАМЯТЬ ДЖАРВИСА]: Найдены релевантные факты из прошлых бесед:"]
            for idx, mem in enumerate(memories, 1):
                text = mem.text if hasattr(mem, 'text') else mem.get('text', '')
                meta = mem.meta_data if hasattr(mem, 'meta_data') else mem.get('meta_data', {})
                date_str = meta.get('created_at', 'Дата не указана') if meta else 'Дата не указана'
                formatted_results.append(f"- [{date_str}] {text}")
            
            rag_context = "\n".join(formatted_results)
            rag_context += "\nИспользуй эти факты для планирования и ответов, но не цитируй их дословно без необходимости."
            
            # 4. Внедряем системное сообщение в граф
            context_msg = SystemMessage(content=rag_context)
            self.logger.info(f"Prefetch Node успешно внедрил {memories}")
            
            return {
                "messages": [context_msg],
                "sender": "prefetch"
            }

        except Exception as e:
            self.logger.error(f"Ошибка в Prefetch Node при работе с RAG: {str(e)}")
            return {"sender": "prefetch"}

    async def _supervisor_node(self, state: TaskState) -> Dict[str, Any]:
        """Главный агент, пиздит других агентов"""
        self.logger.info("--- [NODE] SUPERVISOR ---")

        current_time_str = datetime.now().strftime("%A, %Y-%m-%d")
        formatted_supervisor_prompt = supervisor_prompt.format(time_context=current_time_str)
        
        response = await self.llm.generate_stateless(
            messages=state["messages"],
            system_prompt=formatted_supervisor_prompt,
            tools=[] # У координатора нет инструментов
        )

        self.logger.info(f"Supervisor Router Output: {response.content}")
        return {
            "messages": [response], 
            "steps_count": state.get("steps_count", 0) + 1,
            "sender": "supervisor"
        }

    async def _calendar_agent_node(self, state: TaskState) -> Dict[str, Any]:
        """Специалист по календарю и расписанию"""
        self.logger.info("--- [NODE] CALENDAR AGENT ---")

        dt = datetime.now()
        time_str = (
            f"Текущая дата (ISO): {dt.strftime('%Y-%m-%d')}\n"
            f"День недели: {weekdays[dt.weekday()]}\n"
            f"Точное время: {dt.strftime('%H:%M:%S')}"
        )

        dynamic_system_prompt = calendar_agent_prompt.format(time_context=time_str)
        
        # Отдаем ему только те инструменты, которые нужны для работы
        allowed_names = ["calendar_add_event_tool", "calendar_add_task_tool", "calendar_get_schedule_tool", "request_user_approval_tool"]
        calendar_tools = [self.tools[name] for name in allowed_names if name in self.tools]
        
        response = await self.llm.generate_stateless(
            messages=state["messages"],
            system_prompt=dynamic_system_prompt,
            tools=calendar_tools
        )

        if response.tool_calls:
            self.logger.info(f"CalendarAgent requested tools: {[tc['name'] for tc in response.tool_calls]}")

        update_data = {
            "messages": [response], 
            "steps_count": state.get("steps_count", 0) + 1,
            "sender": "calendar_agent" # кто вызвал инструмент
        }
        
        # данные черновика
        if getattr(response, "tool_calls", None):
            for tc in response.tool_calls:
                if tc["name"] == "request_user_approval_tool":
                    args = tc["args"]
                    update_data["draft_plan"] = args.get("draft_plan")
                    update_data["draft_events"] = args.get("draft_events", [])
                    update_data["draft_tasks"] = args.get("draft_tasks", [])
        
        return update_data

    async def _research_agent_node(self, state: TaskState) -> Dict[str, Any]:
        """Агент поисковик (пока заглушка)"""
        self.logger.info("--- [NODE] RESEARCH AGENT ---")

        allowed_names = ["search_user_memory"] 
        research_tools = [self.tools[name] for name in allowed_names if name in self.tools]
        
        response = await self.llm.generate_stateless(
            messages=state["messages"],
            system_prompt=research_agent_prompt,
            tools=research_tools # На этапе заглушки инструменты не даем
        )

        return {
            "messages": [response], 
            "steps_count": state.get("steps_count", 0) + 1,
            "sender": "research_agent"
        }
    
    async def _tools_node(self, state: TaskState) -> Dict[str, Any]:
        """Выполняет запрошенные инструменты"""
        self.logger.info(f"--- [NODE] TOOLS (Caller: {state.get('sender')}) ---")
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
        events = state.get("draft_events") or []
        tasks = state.get("draft_tasks") or []
        
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
            
        msg = AIMessage(content="Отлично, я внес все события и задачи в твой календарь.")
        return {"messages": [msg], "is_completed": True}
    
    async def _abort_node(self, state: TaskState) -> Dict[str, Any]:
        return {
            "messages": [AIMessage(content="Пользователь отменил план. Запись не произведена.")], 
            "is_completed": True,
            "draft_events": [],
            "draft_tasks": []
        }

    # ЛОГИКА МАРШРУТИЗАЦИИ И ВСПОМОГАТЕЛЬНЫЕ 

    def _route_from_supervisor(self, state: TaskState) -> Literal["calendar_agent", "research_agent", "end", "emergency"]:
        if state.get("steps_count", 0) >= 12:
            return "emergency"

        raw_content = state["messages"][-1].content
        
        if isinstance(raw_content, list):
            text_content = " ".join([block.get("text", "") for block in raw_content if isinstance(block, dict)])
        else:
            # Если пришла обычная строка
            text_content = str(raw_content)
            
        last_msg = text_content.upper()
        
        # парсинг ответа супервизора
        if "CALENDARAGENT" in last_msg:
            return "calendar_agent"
        elif "RESEARCHAGENT" in last_msg:
            return "research_agent"
        else:
            return "end" # кончил или не распознал команду

    def _should_continue(self, state: TaskState) -> Literal["continue", "supervisor", "emergency", "approval"]:
        """Куда идти специалисту после его хода"""
        if state.get("steps_count", 0) >= 12:
            return "emergency"
        
        last_message = state["messages"][-1]
        
        # Если вызван инструмент
        if getattr(last_message, "tool_calls", None):
            for tool_call in last_message.tool_calls:
                if tool_call["name"] == "request_user_approval_tool":
                    return "approval"
            return "continue" # Идем в узел инструментов
            
        # Если агент выдал простой текстовый ответ, он возвращает управление Супервизору
        return "supervisor"

    def _route_from_tools(self, state: TaskState) -> Literal["calendar_agent", "research_agent"]:
        """Возвращает ход тому агенту, который запрашивал инструмент"""
        sender = state.get("sender", "calendar_agent") # по умолчанию фолбек
        if sender == "research_agent":
            return "research_agent"
        return "calendar_agent"

    def _after_approval(self, state: TaskState) -> Literal["commit", "revise", "abort"]:
        if state.get("user_approval") is True:
            return "commit"
        elif state.get("user_approval") is False:
            return "abort"
        return "revise"

    async def _execute_tool(self, tool: BaseTool, args: dict, tool_id: str) -> ToolMessage:
        self.logger.debug(f"Tool {tool.name} called with args: {args}")
        try:
            result = await tool.ainvoke(args)
            self.logger.debug(f"Tool {tool.name} result: {str(result)[:200]}")
        except Exception as e:
            self.logger.error(f"Error in {tool.name}: {str(e)}")
            result = f"Критическая ошибка выполнения {tool.name}: {str(e)}"
        return ToolMessage(content=str(result), name=tool.name, tool_call_id=tool_id)

    async def _fake_tool_result(self, name: str, tool_id: str, error_msg: str) -> ToolMessage:
        return ToolMessage(content=error_msg, name=name, tool_call_id=tool_id)

    # ТОЧКА ВХОДА 

    async def run(self, query: str, approval_status: str = None, thread_id: str = "default_thread") -> str:
        config = {"configurable": {"thread_id": thread_id}}
        current_state = self.graph.get_state(config)
        
        if current_state and current_state.next:
            if approval_status == "approved":
                update_data = {"user_approval": True, "user_feedback": None}
            elif approval_status == "rejected":
                update_data = {"user_approval": False, "user_feedback": None}
            elif approval_status == "revised":
                update_data = {"user_approval": None, "user_feedback": query}
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
                "sender": None, # Инициализируем пустое поле
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

        last_message = final_state["messages"][-1]
        content = last_message.content

        if isinstance(content, str) and "FINISH" in content.upper():
            if len(final_state["messages"]) > 1:
                content = final_state["messages"][-2].content