import asyncio
from datetime import datetime
from typing import Dict, Any
from langchain_core.messages import ToolMessage, AIMessage, SystemMessage
from jarvis.core.state import TaskState
from jarvis.utils.logger import get_logger
from jarvis.config import supervisor_prompt, calendar_agent_prompt, research_agent_prompt, weekdays

class AgentNodes:
    """Узлы, принимающие решения (LLM)"""
    def __init__(self, llm, tools: dict):
        self.llm = llm
        self.tools = tools
        self.logger = get_logger("AgentNodes")

    async def supervisor_node(self, state: TaskState) -> Dict[str, Any]:
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

    async def calendar_agent_node(self, state: TaskState) -> Dict[str, Any]:
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

    async def research_agent_node(self, state: TaskState) -> Dict[str, Any]:
        """Агент поисковик (пока заглушка)"""
        self.logger.info("--- [NODE] RESEARCH AGENT ---")

        allowed_names = ["search_user_memory", "internet_search_tool", "ask_user_clarification_tool"] 
        research_tools = [self.tools[name] for name in allowed_names if name in self.tools]
        
        response = await self.llm.generate_stateless(
            messages=state["messages"],
            system_prompt=research_agent_prompt,
            tools=research_tools 
        )

        return {
            "messages": [response], 
            "steps_count": state.get("steps_count", 0) + 1,
            "sender": "research_agent"
        }

class SystemNodes:
    """Узлы инфраструктуры, памяти и выполнения"""
    def __init__(self, tools: dict, repository, embedding_service):
        self.tools = tools
        self.repository = repository
        self.embedding_service = embedding_service
        self.logger = get_logger("SystemNodes")
    
    async def prefetch_node(self, state: TaskState) -> Dict[str, Any]:
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

    async def tools_node(self, state: TaskState) -> Dict[str, Any]:
        """Выполняет запрошенные инструменты"""
        self.logger.info(f"--- [NODE] TOOLS (Caller: {state.get('sender')}) ---")
        last_message = state["messages"][-1]
        tasks = []
        for tc in last_message.tool_calls:
            tool_name = tc["name"]
            if tool_name in self.tools:
                tasks.append(self.execute_tool(self.tools[tool_name], tc["args"], tc["id"]))
            else:
                tasks.append(self.fake_tool_result(tool_name, tc["id"], "Ошибка: Инструмент не найден"))
        
        results = await asyncio.gather(*tasks)
        return {"messages": results}
    
    async def human_clarification_node(self, state: TaskState) -> Dict[str, Any]:
        """Обработка уточняющих ответов пользователя"""
        user_feedback = state.get("user_feedback")
        messages = list(state.get("messages", []))
        
        last_ai_msg = messages[-1]
        tool_call_id = None

        if getattr(last_ai_msg, "tool_calls", None):
            for tc in last_ai_msg.tool_calls:
                if tc["name"] == "ask_user_clarification_tool":
                    tool_call_id = tc["id"]
                    break

        new_messages = []
        if tool_call_id:
            content = f"[ОТВЕТ ПОЛЬЗОВАТЕЛЯ]: {user_feedback}" if user_feedback else "[СИСТЕМА]: Пользователь ничего не ответил."
            
            new_messages.append(
                ToolMessage(content=content, name="ask_user_clarification_tool", tool_call_id=tool_call_id)
            )
        return {"messages": new_messages, "user_feedback": None}

    async def emergency_node(self, state: TaskState) -> Dict[str, Any]:
        msg = AIMessage(content="[СИСТЕМНОЕ СООБЩЕНИЕ] Выполнение прервано: превышен лимит шагов.")
        return {"messages": [msg], "is_completed": False}
    
    async def human_approval_node(self, state: TaskState) -> Dict[str, Any]:
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

    async def commit_node(self, state: TaskState) -> Dict[str, Any]:
        events = state.get("draft_events") or []
        tasks = state.get("draft_tasks") or []
        
        add_event_tool = self.tools.get("calendar_add_event_tool")
        add_task_tool = self.tools.get("calendar_add_task_tool")
        
        for ev in events:
            self.logger.info(f"Авто-запись события: {ev}")
            if add_event_tool:
                try:
                    res = await add_event_tool.ainvoke(ev)
                    self.logger.info(f"Результат API Google Calendar: {res}")
                except Exception as e:
                    self.logger.error(f"Ошибка при создании события в Календаре: {e}")
            await asyncio.sleep(0.5)
            
        for task in tasks:
            self.logger.info(f"Авто-запись задачи: {task}")
            if add_task_tool:
                try:
                    result = await add_task_tool.ainvoke(task)
                    self.logger.info(f"Результат API Google Tasks: {result}")
                except Exception as e:
                    self.logger.error(f"Ошибка при создании задачи: {e}")
            await asyncio.sleep(0.5)
            
        msg = AIMessage(content="Отлично, я внес все события и задачи в твой календарь.")
        return {"messages": [msg], "is_completed": True}
    
    async def abort_node(self, state: TaskState) -> Dict[str, Any]:
        return {
            "messages": [AIMessage(content="Пользователь отменил план. Запись не произведена.")], 
            "is_completed": True,
            "draft_events": [],
            "draft_tasks": []
        }
    
    async def execute_tool(self, tool, args: dict, tool_id: str) -> ToolMessage:
        self.logger.debug(f"Tool {tool.name} called with args: {args}")
        try:
            result = await tool.ainvoke(args)
            self.logger.debug(f"Tool {tool.name} result: {str(result)[:200]}")
        except Exception as e:
            self.logger.error(f"Error in {tool.name}: {str(e)}")
            result = f"Критическая ошибка выполнения {tool.name}: {str(e)}"
        return ToolMessage(content=str(result), name=tool.name, tool_call_id=tool_id)

    async def fake_tool_result(self, name: str, tool_id: str, error_msg: str) -> ToolMessage:
        return ToolMessage(content=error_msg, name=name, tool_call_id=tool_id)
