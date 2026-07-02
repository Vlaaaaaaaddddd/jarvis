import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from jarvis.config import CALENDAR_TOKEN_FILE, CALENDAR_CREDENTIALS_FILE

class GoogleCalendarService:
    """Инфраструктурный сервис для работы с Google Calendar и Google Tasks"""
    SCOPES = [
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/tasks' # Добавляем права на To-Do задачи
    ]
    TOKEN_FILE = CALENDAR_TOKEN_FILE
    CREDENTIALS_FILE = CALENDAR_CREDENTIALS_FILE

    CALENDAR_MAP = {
    'университет': "575d046f6dd941c525ad7539355bb7ac0bdefc2d51980f3a30c26fe028f311c8@group.calendar.google.com",
    'учеба дома': "8b786d9637b13e48792a4711b083b1e4ac668a8104be115b345a75a372ee5ae8@group.calendar.google.com",
    'работа, проекты': "c2ed439907297813a9f5d46e874a5734fcff5bb56ef79def612de6cf4b2cc74e@group.calendar.google.com",
    'хорошие привычки': "843df977b1eb54d067ed8cbc03b9cb85d5f8ba177c0f28bd326f07b7daebeb8c@group.calendar.google.com",
    'спорт': '5a5efee2ae07b0a208fa7646a5636829d2f13bb6d55e9ba681e963d123f1597c@group.calendar.google.com',
    'встречи': 'c69a890fa800546f15108af92a1e094ef6a7d34fb68509f67cb22aff7496a15f@group.calendar.google.com',
    'быт': 'abf9a5c21e9dfa401f3d234f74fe32c774ac0145825df35055fae318a81aab15@group.calendar.google.com',
    }


    def __init__(self):
        self.creds = None
        self.calendar_service = None
        self.tasks_service = None
        self._authenticate()

    def _authenticate(self):
        if os.path.exists(self.TOKEN_FILE):
            self.creds = Credentials.from_authorized_user_file(self.TOKEN_FILE, self.SCOPES)
        
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.CREDENTIALS_FILE, self.SCOPES
                )
                self.creds = flow.run_local_server(port=0)
            
            with open(self.TOKEN_FILE, 'w') as token:
                token.write(self.creds.to_json())

        self.calendar_service = build('calendar', 'v3', credentials=self.creds)
        self.tasks_service = build('tasks', 'v1', credentials=self.creds)

    def get_calendar_id(self, category: str) -> str:
        """Возвращает ID календаря по названию категории"""
        return self.CALENDAR_MAP.get(category.lower(), 'primary')
