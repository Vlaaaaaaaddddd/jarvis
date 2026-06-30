# jarvis/core/engine.py
import asyncio
import time
import jarvis.config.ui_config as cfg
from jarvis.front.ui import TerminalUI

class JarvisEngine:
    def __init__(self):
        self.ui = TerminalUI()
        self._is_running = False

    async def start(self):
        """Запуск основного цикла приложения (сборка цикла)"""
        self.ui.start()
        self._is_running = True
        
        start_time = time.time()
        try:
            while self._is_running:
                # Считаем прошедшее время для математики вращения сферы
                current_time = time.time() - start_time
                
                # Передаем время в UI для рендеринга текущего состояния сферы
                self.ui.render_frame(current_time)
                
                # Контролируем частоту кадров (FPS) без блокировки потока
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