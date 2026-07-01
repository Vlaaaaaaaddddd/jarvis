import asyncio
import time
import jarvis.config.ui_config as cfg
from jarvis.config import BaseUI, BaseLLM

class JarvisEngine:
    def __init__(self, ui: BaseUI, llm: BaseLLM):
        self.ui = ui
        self.llm = llm
        self._is_running = False

    async def start(self):
        """Запуск основного цикла приложения"""
        self.ui.start()
        self._is_running = True
        
        start_time = time.time()
        try:
            while self._is_running:
                current_time = time.time() - start_time
                
                self.ui.render_frame(current_time)
                
                await asyncio.sleep(cfg.RENDER_INTERVAL)
                
        except asyncio.CancelledError:
            pass
        finally:
            self.stop()

    def stop(self):
        """Корректное завершение работы и очистка терминала"""
        if self._is_running:
            self._is_running = False
            self.ui.stop()