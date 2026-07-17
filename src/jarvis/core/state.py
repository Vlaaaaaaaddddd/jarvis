from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class TaskState(TypedDict):
    """
    Эфемерное состояние для решения одной делегированной задачи.
    """
    messages: Annotated[Sequence[BaseMessage], add_messages] # Список сообщений
    task_objective: str # Исходная формулировка задачи от пользователя
    steps_count: int
    is_completed: bool
    sender: str | None  
    draft_plan: str | None # черновик расписания
    user_approval: bool | None # True - одобрено, False - откат, None - ожидание    

    # Структурированные списки для автоматического коммита на Python
    draft_events: list[dict] | None
    draft_tasks: list[dict] | None

    # Текстовые правки от пользователя
    user_feedback: str | None        