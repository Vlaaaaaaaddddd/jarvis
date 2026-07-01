import asyncio
import time
import jarvis.config.ui_config as cfg
from jarvis.config import BaseLLM, BaseUI, BaseInputHandler, BaseOutputHandler

class JarvisEngine:
    def __init__(self, 
                 ui: BaseUI,
                 input_handler: BaseInputHandler, 
                 output_handler: BaseOutputHandler, 
                 llm: BaseLLM
                 ):
        self.ui = ui
        self.input_handler = input_handler
        self.output_handler = output_handler
        self.llm = llm
        self._is_running = False

    async def start(self):
        """Запуск основного цикла приложения"""
        await self.ui.start()
        self._is_running = True
        try:
            await self._command_processor()
        except asyncio.CancelledError:
            pass
        finally:
            self.stop()

    async def _command_processor(self):
        """Единый цикл обработки"""
        while self._is_running:
            command_text = await self.input_handler.listen()
            
            if command_text:
                if hasattr(self.ui, 'print_user_message'):
                    self.ui.print_user_message(command_text)
                
                self.ui.terminal_ui.status = "ДЖАРВИС ДУМАЕТ..."

                response = await self.llm.generate_response(command_text)
                
                self.ui.terminal_ui.status = "СИСТЕМА АКТИВНА"

                await self.output_handler.broadcast(response)

    async def _input_loop(self):
        pass

    def stop(self):
        """Корректное завершение работы и очистка терминала"""
        if self._is_running:
            self._is_running = False
            self.ui.stop()