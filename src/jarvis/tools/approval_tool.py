
from langchain_core.tools import tool

@tool
def request_user_approval_tool(
    draft_plan: str, 
    draft_events: list[dict] = None, 
    draft_tasks: list[dict] = None
) -> str:
    """
    Вызови этот инструмент, когда ты составил черновик расписания, планов или задач 
    и тебе требуется подтверждение пользователя перед тем, как реально записать их в календарь.
    Вызывай его только если черновик действительно сложный и требует подтверджения.
    
    ВАЖНО: Для простых точечных действий (например, добавить одну конкретную задачу или одно событие на свободное время, 
    если пользователь прямо об этом попросил: 'запиши встречу на 15:00') этот инструмент вызывать НЕ НУЖНО — 
    сразу используй инструменты записи (CalendarAddEventTool / CalendarAddTaskTool).
    
    Args:
        draft_plan: Текстовый черновик предлагаемого расписания (для озвучки).
        draft_events: Список событий. Каждый словарь должен содержать ключи для calendar_add_event_tool (summary, start_time, category, duration_minutes).
        draft_tasks: Список задач. Каждый словарь должен содержать ключи для calendar_add_task_tool (title, due_date, notes).
    """
    ev_count = len(draft_events) if draft_events else 0
    t_count = len(draft_tasks) if draft_tasks else 0
    return f"Черновик отправлен на согласование. Событий в буфере: {ev_count}, Задач: {t_count}."