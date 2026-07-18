from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage

from jarvis.core.state import TaskState
from jarvis.utils.logger import get_logger
from jarvis.core.routing import route_from_supervisor, should_continue, route_from_tools, after_approval

class TaskGraph:
    def __init__(self, agent_nodes, system_nodes):
        self.agent_nodes = agent_nodes
        self.system_nodes = system_nodes
        self.memory = MemorySaver() 
        self.logger = get_logger("TaskGraph")
        self.graph = self._build_graph()

    def _build_graph(self):
        """Конфигурирует узлы и ребра мультиагентного графа"""
        workflow = StateGraph(TaskState)

        # sузлы специалистов и координатора
        workflow.add_node("supervisor", self.agent_nodes.supervisor_node)
        workflow.add_node("calendar_agent", self.agent_nodes.calendar_agent_node)
        workflow.add_node("research_agent", self.agent_nodes.research_agent_node)
        
        # системные узлы
        workflow.add_node("tools", self.system_nodes.tools_node)
        workflow.add_node("emergency_stop", self.system_nodes.emergency_node)
        workflow.add_node("human_approval", self.system_nodes.human_approval_node)
        workflow.add_node("commit_node", self.system_nodes.commit_node)  
        workflow.add_node("abort_node", self.system_nodes.abort_node)    

        workflow.add_node("prefetch_node", self.system_nodes.prefetch_node)

        # Точка входа
        workflow.set_entry_point("prefetch_node")

        workflow.add_edge("prefetch_node", "supervisor")

        # Маршрутизация от Супервизора
        workflow.add_conditional_edges(
            "supervisor",
            route_from_supervisor,
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
            should_continue,
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
            should_continue,
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
            route_from_tools,
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
            after_approval,
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