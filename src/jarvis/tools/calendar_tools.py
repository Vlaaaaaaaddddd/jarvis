import asyncio
from datetime import datetime, timedelta, time
from google.genai import types
from jarvis.config import BaseTool
from jarvis.services.calendar import GoogleCalendarService

calendar_infra = GoogleCalendarService()

def parse_relative_date(date_str: str) -> datetime:
    """Настоящее время"""
    now = datetime.now()
    if not date_str or date_str.lower() == "today":
        return now
    if date_str.lower() == "tomorrow":
        return now + timedelta(days=1)
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        return now


class CalendarAddEventTool(BaseTool):
    """Инструмент создания мероприятий"""
    
    @property
    def name(self):
        return "CalendarAddEventTool"

    def get_schema(self) -> types.Tool:
        return types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=self.name,
                    description="Создает мероприятие в Google Календаре. Умеет создавать обычные события и события на весь день, а также автоматически выбирать нужный календарь.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "summary": types.Schema(type=types.Type.STRING, description="Название события"),
                            "start_time": types.Schema(type=types.Type.STRING, description="СТРОГО ДАТА И ВРЕМЯ В ПОЛНОМ ФОРМАТЕ ISO 8601 (YYYY-MM-DDTHH:MM:SS). ВНИМАНИЕ: Сначала вызови TimeTool, чтобы узнать текущий год/месяц/день, и на их основе вычисли точный ISO-таймстемп"),
                            "is_all_day": types.Schema(type=types.Type.BOOLEAN, description="True, если событие запланировано на весь день (без конкретных часов)"),
                            "category": types.Schema(type=types.Type.STRING, description="Категория дела для выбора календаря: 'университет', 'учеба дома', 'работа, проекты', 'хорошие привычки', 'спорт', 'встречи', 'быт'"),
                            "duration_minutes": types.Schema(type=types.Type.INTEGER, description="Длительность обычного события в минутах (по умолчанию 60)"),
                            "description": types.Schema(type=types.Type.STRING, description="Описание события")
                        },
                        required=["summary"]
                    )
                )
            ]
        )

    async def execute(self, summary: str, start_time: str = "today", is_all_day: bool = False, category: str = "основной", duration_minutes: int = 60, description: str = "", **kwargs):
        def _run():
            cal_id = calendar_infra.get_calendar_id(category)
            base_dt = parse_relative_date(start_time)
            
            event = {
                'summary': summary,
                'description': description,
            }

            if is_all_day:
                # Для All-Day событий Google требует использовать поле 'date' вместо 'dateTime'
                date_str = base_dt.strftime('%Y-%m-%d')
                event['start'] = {'date': date_str}
                event['end'] = {'date': date_str}
            else:
                end_dt = base_dt + timedelta(minutes=duration_minutes)
                event['start'] = {'dateTime': base_dt.isoformat(), 'timeZone': 'Asia/Yekaterinburg'}
                event['end'] = {'dateTime': end_dt.isoformat(), 'timeZone': 'Asia/Yekaterinburg'}

            result = calendar_infra.calendar_service.events().insert(calendarId=cal_id, body=event).execute()
            return f"Мероприятие '{summary}' успешно добавлено в календарь '{category}'. Ссылка: {result.get('htmlLink')}"

        try:
            return await asyncio.to_thread(_run)
        except Exception as e:
            return f"Ошибка создания события: {str(e)}"


class CalendarAddTaskTool(BaseTool):
    """Инструмент для создания To-Do задач в Google Tasks"""
    
    @property
    def name(self):
        return "CalendarAddTaskTool"

    def get_schema(self) -> types.Tool:
        return types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=self.name,
                    description="Создает задачу (To-Do списки, напоминания без жесткой привязки к сетке часов) в Google Tasks.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "title": types.Schema(type=types.Type.STRING, description="Текст задачи"),
                            "due_date": types.Schema(type=types.Type.STRING, description="Дата дедлайна в формате ISO или 'today', 'tomorrow'"),
                            "notes": types.Schema(type=types.Type.STRING, description="Заметки или подпункты к задаче")
                        },
                        required=["title"]
                    )
                )
            ]
        )

    async def execute(self, title: str, due_date: str = None, notes: str = "", **kwargs):
        def _run():
            task = {'title': title, 'notes': notes}
            if due_date:
                dt = parse_relative_date(due_date)
                # Google Tasks требует RFC 3339 формат даты с обязательным указанием времени (ставим Z)
                task['due'] = dt.date().isoformat() + 'T00:00:00.000Z'

            # Используем список задач по умолчанию (@default)
            result = calendar_infra.tasks_service.tasks().insert(tasklist='@default', body=task).execute()
            return f"Задача To-Do '{title}' успешно добавлена в список."

        try:
            return await asyncio.to_thread(_run)
        except Exception as e:
            return f"Ошибка создания задачи: {str(e)}"


class CalendarGetScheduleTool(BaseTool):
    """Парсер расписания"""
    def __init__(self):
        super().__init__()
    
    @property
    def name(self):
        return "CalendarGetScheduleTool"

    def get_schema(self) -> types.Tool:
        return types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=self.name,
                    description="Главный инструмент просмотра планов. Умеет показывать расписание из конкретного календаря, только задачи To-Do, или сводку по ВСЕМ делам сразу за указанный период.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "start_time": types.Schema(type=types.Type.STRING, description="Начало периода проверки в формате YYYY-MM-DD. ВНИМАНИЕ: Чтобы узнать, какой день недели или число соответствует запросу пользователя, сначала вызови TimeTool, а затем передай сюда вычисленную дату"),
                            "end_time": types.Schema(type=types.Type.STRING, description="Начало периода проверки в формате YYYY-MM-DD. ВНИМАНИЕ: Чтобы узнать, какой день недели или число соответствует запросу пользователя, сначала вызови TimeTool, а затем передай сюда вычисленную дату"),
                            "target": types.Schema(
                                type=types.Type.STRING, 
                                description="Что искать: 'all' (календари + задачи), 'задачи' (только задачи). "
                                            "Либо строго одно из названий конкретных календарей, если пользователь явно упомянул эту сферу: "
                                            "'университет', 'учеба дома', 'работа, проекты', 'хорошие привычки', 'спорт', 'встречи', 'быт'."
                            )
                        }
                    )
                )
            ]
        )

    async def execute(self, start_time: str = "today", end_time: str = "today", target: str = "all", **kwargs):
        # 1. Рассчитываем строгие временные границы
        base_start = parse_relative_date(start_time)
        base_end = parse_relative_date(end_time)
        
        if start_time == end_time:
            time_min = datetime.combine(base_start.date(), time.min).isoformat() + 'Z'
            time_max = datetime.combine(base_end.date(), time.max).isoformat() + 'Z'
        else:
            time_min = base_start.isoformat() + 'Z'
            time_max = base_end.isoformat() + 'Z'

        # 2. Внутренние воркеры для потоков
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
                # Фильтруем задачи строго по времени (dueMin и dueMax)
                res = calendar_infra.tasks_service.tasks().list(
                    tasklist='@default',
                    dueMin=time_min,
                    dueMax=time_max,
                    showCompleted=False # Скрываем то, что уже выполнено
                ).execute()
                return {"type": "tasks", "items": res.get('items', [])}
            except Exception as e:
                return {"type": "tasks", "error": str(e), "items": []}

        # 3. Маршрутизация: решаем, какие запросы запускать
        async_tasks = []
        target = target.lower()

        if target == "all":
            # Собираем всё: и все календари, и задачи
            for name, cal_id in calendar_infra.CALENDAR_MAP.items():
                async_tasks.append(asyncio.to_thread(_fetch_calendar, name, cal_id))
            async_tasks.append(asyncio.to_thread(_fetch_tasks))
            
        elif target == "задачи":
            # Собираем только задачи
            async_tasks.append(asyncio.to_thread(_fetch_tasks))
            
        else:
            # Ищем конкретный календарь
            cal_id = calendar_infra.get_calendar_id(target)
            async_tasks.append(asyncio.to_thread(_fetch_calendar, target, cal_id))

        # 4. Выполняем отобранные запросы параллельно
        fetched_results = await asyncio.gather(*async_tasks)

        # 5. Сборка результатов
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

        # 6. Форматирование ответа для модели
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
    
