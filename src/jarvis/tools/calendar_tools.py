import asyncio
from datetime import datetime, timedelta, time
from langchain_core.tools import tool
from jarvis.services.calendar import GoogleCalendarService

calendar_semaphore = asyncio.Semaphore(2) # максимум 1 одновременный запрос
calendar_infra = GoogleCalendarService()

def parse_relative_date(date_str: str) -> datetime:
    now = datetime.now()
    if not date_str or date_str.lower() == "today":
        return now
    if date_str.lower() == "tomorrow":
        return now + timedelta(days=1)
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        return now

@tool
async def calendar_add_event_tool(
    summary: str, 
    start_time: str = "today", 
    is_all_day: bool = False, 
    category: str = "основной", 
    duration_minutes: int = 60, 
    description: str = ""
) -> str:
    """Создает мероприятие в Google Календаре. Умеет создавать обычные события и события на весь день.
    
    Args:
        summary: Название события
        start_time: СТРОГО ДАТА И ВРЕМЯ В ПОЛНОМ ФОРМАТЕ ISO 8601 (YYYY-MM-DDTHH:MM:SS). Сначала вызови TimeTool для точного расчета.
        is_all_day: True, если событие запланировано на весь день (без конкретных часов)
        category: Категория дела: 'университет', 'учеба дома', 'работа, проекты', 'хорошие привычки', 'спорт', 'встречи', 'быт'
        duration_minutes: Длительность обычного события в минутах (по умолчанию 60)
        description: Описание события
    """
    def _run():
        cal_id = calendar_infra.get_calendar_id(category)
        base_dt = parse_relative_date(start_time)
        event = {'summary': summary, 'description': description}

        if is_all_day:
            date_str = base_dt.strftime('%Y-%m-%d')
            event['start'] = {'date': date_str}
            event['end'] = {'date': date_str}
        else:
            end_dt = base_dt + timedelta(minutes=duration_minutes)
            event['start'] = {'dateTime': base_dt.isoformat(), 'timeZone': 'Asia/Yekaterinburg'}
            event['end'] = {'dateTime': end_dt.isoformat(), 'timeZone': 'Asia/Yekaterinburg'}

        result = calendar_infra.calendar_service.events().insert(calendarId=cal_id, body=event).execute()
        return f"Мероприятие '{summary}' успешно добавлено в календарь '{category}'. Ссылка: {result.get('htmlLink')}"

    # Используем семафор, чтобы запросы шли строго друг за другом, не перегружая прокси
    async with calendar_semaphore:
        try:
            res = await asyncio.to_thread(_run)
            # Микро-пауза в 0.5 секунды между запросами для стабилизации TLS соединения
            await asyncio.sleep(0.5)
            return res
        except Exception as e:
            return f"Ошибка создания события: {str(e)}"

@tool
async def calendar_add_task_tool(title: str, due_date: str = None, notes: str = "") -> str:
    """Создает задачу (To-Do списки, напоминания без жесткой привязки к сетке часов) в Google Tasks.
    
    Args:
        title: Текст задачи
        due_date: Дата дедлайна в формате ISO или 'today', 'tomorrow'
        notes: Заметки или подпункты к задаче
    """
    def _run():
        task = {'title': title, 'notes': notes}
        if due_date:
            dt = parse_relative_date(due_date)
            task['due'] = dt.date().isoformat() + 'T00:00:00.000Z'
        
        calendar_infra.tasks_service.tasks().insert(tasklist='@default', body=task).execute()
        return f"Задача To-Do '{title}' успешно добавлена в список."

    try:
        return await asyncio.to_thread(_run)
    except Exception as e:
        return f"Ошибка создания задачи: {str(e)}"

@tool
async def calendar_get_schedule_tool(start_time: str = "today", end_time: str = "today", target: str = "all") -> str:
    """Главный инструмент просмотра планов из календаря и задач To-Do.
    
    Args:
        start_time: Начало периода в формате YYYY-MM-DD. Всегда вызывай TimeTool перед этим.
        end_time: Конец периода в формате YYYY-MM-DD.
        target: 'all' (календари + задачи), 'задачи' (только задачи), или точное название календаря ('спорт', 'работа, проекты' и т.д.)
    """
    base_start = parse_relative_date(start_time)
    base_end = parse_relative_date(end_time)
    
    if start_time == end_time:
        time_min = datetime.combine(base_start.date(), time.min).isoformat() + 'Z'
        time_max = datetime.combine(base_end.date(), time.max).isoformat() + 'Z'
    else:
        time_min = base_start.isoformat() + 'Z'
        time_max = base_end.isoformat() + 'Z'

    def _fetch_calendar(name, cal_id):
        try:
            res = calendar_infra.calendar_service.events().list(
                calendarId=cal_id, timeMin=time_min, timeMax=time_max,
                singleEvents=True, orderBy='startTime'
            ).execute()
            return {"type": "calendar", "name": name, "items": res.get('items', [])}
        except Exception as e:
            return {"type": "calendar", "name": name, "error": str(e), "items": []}

    def _fetch_tasks():
        try:
            res = calendar_infra.tasks_service.tasks().list(
                tasklist='@default', dueMin=time_min, dueMax=time_max, showCompleted=False
            ).execute()
            return {"type": "tasks", "items": res.get('items', [])}
        except Exception as e:
            return {"type": "tasks", "error": str(e), "items": []}

    async_tasks = []
    target = target.lower()

    if target == "all":
        for name, cal_id in calendar_infra.CALENDAR_MAP.items():
            async_tasks.append(asyncio.to_thread(_fetch_calendar, name, cal_id))
        async_tasks.append(asyncio.to_thread(_fetch_tasks))
    elif target == "задачи":
        async_tasks.append(asyncio.to_thread(_fetch_tasks))
    else:
        cal_id = calendar_infra.get_calendar_id(target)
        async_tasks.append(asyncio.to_thread(_fetch_calendar, target, cal_id))

    fetched_results = await asyncio.gather(*async_tasks)

    all_events = []
    todo_tasks = []

    for res in fetched_results:
        if res["type"] == "calendar":
            for item in res["items"]:
                start_data = item['start'].get('dateTime', item['start'].get('date'))
                all_events.append({
                    "calendar": res["name"],
                    "summary": item['summary'],
                    "start": start_data,
                    "is_all_day": 'date' in item['start']
                })
        elif res["type"] == "tasks":
            todo_tasks = res["items"]

    all_events.sort(key=lambda x: x['start'])

    report = f"СВОДКА ПЛАНОВ ({start_time.upper()} - {end_time.upper()}) | ФИЛЬТР: {target.upper()}\n\n"
    
    if not all_events and target != "задачи":
        report += "Событий в календаре на этот период нет.\n"
    else:
        current_date = None
        for ev in all_events:
            dt_str = ev['start']
            if ev['is_all_day']:
                date_part = datetime.strptime(dt_str, '%Y-%m-%d').strftime('%d.%m (%A)')
                time_part = "[Весь день]"
            else:
                dt_obj = datetime.fromisoformat(dt_str.split('+')[0].split('Z')[0])
                date_part = dt_obj.strftime('%d.%m (%A)')
                time_part = dt_obj.strftime('%H:%M')

            if date_part != current_date:
                current_date = date_part
                report += f"\n{current_date}:\n"

            report += f" - {time_part} | [{ev['calendar'].upper()}] — {ev['summary']}\n"

    if target in ["all", "задачи"]:
        if todo_tasks:
            report += "\nЗАДАЧИ TO-DO НА ЭТОТ ПЕРИОД:\n"
            for t in todo_tasks:
                due = t.get('due')
                due_str = f" (до {datetime.fromisoformat(due.replace('Z', '+00:00')).strftime('%d.%m')})" if due else ""
                report += f"{t['title']}{due_str}\n"
                if t.get('notes'):
                    report += f"     └── {t['notes']}\n"
        elif target == "задачи":
             report += "Задач на указанный период не найдено.\n"

    return report