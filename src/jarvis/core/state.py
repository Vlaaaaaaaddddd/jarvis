from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class TaskState(TypedDict):
    """
    Эфемерное состояние для решения одной делегированной задачи.
    """
    # Список сообщений (шагов рассуждения)
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # Исходная формулировка задачи от пользователя
    task_objective: str
    
    # Счетчик шагов для жесткого лимита
    steps_count: int
    
    # Флаг успешности выполнения
    is_completed: bool

    # Текстовое описание черновика расписания
    draft_plan: str | None       

    # True - одобрено, False - откат, None - ожидание    
    user_approval: bool | None

    # Структурированные списки для автоматического коммита на Python
    draft_events: list[dict] | None
    draft_tasks: list[dict] | None

    # Текстовые правки от пользователя
    user_feedback: str | None        