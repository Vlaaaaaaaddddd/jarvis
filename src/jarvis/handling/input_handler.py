import asyncio
from jarvis.config import BaseInputHandler
from jarvis.front.render import JarvisUI

class MainInputHandler(BaseInputHandler):
    def __init__(self, ui: JarvisUI, stt_service):
        self.ui = ui
        self.tts = stt_service
    
    async def listen(self) -> str:
        term = self.ui.terminal_ui.term
        self.ui.terminal_ui.input_buffer = ""

        while True:
            key = await asyncio.to_thread(term.inkey, timeout=None)

            if key.code == term.KEY_ENTER:
                user_command = self.ui.terminal_ui.input_buffer.strip()
                self.ui.terminal_ui.input_buffer = "" # Очищаем строку ввода
                return user_command

            elif key.code in (term.KEY_BACKSPACE, term.KEY_DELETE) or key == '\x7f':
                self.ui.terminal_ui.input_buffer = self.ui.terminal_ui.input_buffer[:-1]

            elif key.is_sequence:
                pass
                
            else:
                self.ui.terminal_ui.input_buffer += key