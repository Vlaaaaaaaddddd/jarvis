import asyncio
import time
import jarvis.config.ui_config as cfg
from jarvis.config import BaseUI
from jarvis.front.ui import TerminalUI

class JarvisUI(BaseUI):
    def __init__(self):
        self._is_running = False
        self._render_task = None
        self._status_task = None
        self.terminal_ui = TerminalUI()

    async def start(self):
        self.terminal_ui.start()
        self._is_running = True
        self._render_task = asyncio.create_task(self._render_loop())
    
    async def _render_loop(self):
        start_time = time.time()
        while self._is_running:
            current_time = time.time() - start_time
            self.render_frame(current_time)

            interval = cfg.RENDER_INTERVAL * 0.001 if self.terminal_ui.status == 'ДЖАРВИС ДУМАЕТ...' else cfg.RENDER_INTERVAL
            await asyncio.sleep(interval)

    def render_frame(self, current_time: float):
        self.terminal_ui.render_frame(current_time)

    def stop(self):
        if self._is_running:
            self._is_running = False
            if self._render_task:
                self._render_task.cancel()
            self.terminal_ui.stop()

    def set_status(self, status: str) -> None:
        if self._status_task and not self._status_task.done():
            self._status_task.cancel()
        self.terminal_ui.status = status

    def set_temporary_status(self, status: str, duration: float = 3.0, fallback: str = "СИСТЕМА АКТИВНА") -> None:
        """Выставляет статус на duration секунд, не блокируя работу программы"""
        if self._status_task and not self._status_task.done():
            self._status_task.cancel()

        async def _timer():
            self.terminal_ui.status = status
            await asyncio.sleep(duration)
            # Возвращаем исходный статус, ТОЛЬКО если за эти секунды 
            # статус не был изменен чем-то более важным
            if self.terminal_ui.status == status:
                self.terminal_ui.status = fallback

        self._status_task = asyncio.create_task(_timer())

    def print_message(self, text: str):
        self.terminal_ui.add_message("Джарвис", text)

    def print_user_message(self, text: str):
        self.terminal_ui.add_message("Вы", text)

    def update_input_buffer(self, text: str) -> None:
        self.terminal_ui.input_buffer = text

        
        
