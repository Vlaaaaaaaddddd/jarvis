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