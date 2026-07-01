from jarvis.config import BaseOutputHandler

class MainOutputHandler(BaseOutputHandler):
    def __init__(self, ui, tts_service):
        self.ui = ui
        self.tts = tts_service

    async def broadcast(self, response_text: str) -> None:
        self.ui.print_message(response_text)
        
        if self.tts:
            await self.tts.speak(response_text)