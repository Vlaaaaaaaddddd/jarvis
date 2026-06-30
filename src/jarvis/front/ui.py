# front/ui.py
import sys
import numpy as np
from blessed import Terminal
import jarvis.config.ui_config as cfg
import jarvis.utils.math_3d as m3d

class TerminalUI:
    def __init__(self):
        self.term = Terminal()
        # Генерируем базовые точки один раз при инициализации
        self.base_donut = m3d.generate_donut()
        
        # Временные заглушки для демонстрации разметки интерфейса
        self.status = "СИСТЕМА АКТИВНА"
        self.input_buffer = ""
        self.messages = [("Джарвис", "Контур отрисовки запущен. Вычислительное ядро готово.")]

    def start(self):
        """Вход в полноэкранный режим"""
        print(self.term.enter_fullscreen + self.term.hide_cursor + self.term.clear)

    def stop(self):
        """Выход из полноэкранного режима (Graceful Shutdown)"""
        print(self.term.exit_fullscreen + self.term.normal_cursor)

    def _draw_string(self, matrix, row, col, text, color_func=None):
        """Прямая безопасная запись строки в двумерную матрицу кадра"""
        h, w = matrix.shape
        if row < 0 or row >= h:
            return
        for i, char in enumerate(text):
            cc = col + i
            if 0 <= cc < w - 1:
                matrix[row, cc] = color_func(char) if color_func else char

    def _embed_donut(self, matrix, h: int, t: float):
        center_x = cfg.ANIM_ZONE_W // 2
        center_y = (h - 6) // 2 + 3
        
        # Масштаб пончика
        radius = min(cfg.ANIM_ZONE_W // 4, (h - 8) // 2)

        # Получаем спроецированные координаты, глубину и яркость из ядра
        px, py, ooz, luminance = m3d.get_projected_donut(self.base_donut, t, radius, center_x, center_y)

        # Создаем Z-буфер (массив нулей), чтобы передние точки перекрывали задние
        zbuffer = np.zeros((h, cfg.ANIM_ZONE_W), dtype=float)
        
        ramp = cfg.SHADING_RAMP
        ramp_len = len(ramp)

        for i in range(len(px)):
            x, y = px[i], py[i]
            z = ooz[i]
            L = luminance[i]
            
            # Проверка границ зоны анимации
            if 1 < x < cfg.ANIM_ZONE_W - 1 and 3 < y < h - 4:
                # ТЕСТ Z-БУФЕРА: Рисуем точку, только если она ближе к нам (z больше), чем то, что уже нарисовано
                if z > zbuffer[y, x]:
                    zbuffer[y, x] = z
                    
                    # Если на точку падает свет (Luminance > 0)
                    if L > 0:
                        # Конвертируем яркость в индекс символа
                        idx = int(L * (ramp_len - 1))
                        char = ramp[max(0, min(idx, ramp_len - 1))]
                        
                        # Эстетика терминала: яркие блики белые, тело зеленое
                        color = self.term.bold_white if L > 0.8 else self.term.bold_green
                        matrix[y, x] = color(char)

    def render_frame(self, current_time: float):
        """Полная сборка кадра (Интерфейс + Сфера) внутри UI"""
        h, w = self.term.height, self.term.width
        if h < cfg.MIN_H or w < cfg.MIN_W:
            print(self.term.home + "Расширьте окно терминала...", end="", flush=True)
            return

        # Инициализируем пустую текстовую матрицу кадра
        frame = np.full((h, w), " ", dtype=object)

        # 1. Строим статические рамки киберпанк-дашборда
        frame[0, :] = self.term.cyan("═")
        frame[2, :] = self.term.cyan("─")
        frame[h - 4, :] = self.term.cyan("─")
        frame[h - 2, :] = self.term.cyan("═")
        frame[:, 0] = self.term.cyan("║")
        frame[:, w - 1] = self.term.cyan("║")
        frame[2:h-4, cfg.ANIM_ZONE_W] = self.term.cyan("│")

        # 2. Добавляем текстовые маркеры блоков
        self._draw_string(frame, 1, 4, "J.A.R.V.I.S. // CORE CORE_ENGINE", self.term.bold_cyan)
        self._draw_string(frame, 3, 2, "КИНЕТИЧЕСКОЕ ЯДРО", self.term.bold_yellow)
        self._draw_string(frame, 3, cfg.ANIM_ZONE_W + 3, "ДИАЛОГОВЫЙ КОНТЕНТ", self.term.bold_green)

        self._embed_donut(frame, h, current_time)

        # 4. Выводим лог сообщений (правая часть)
        chat_x = cfg.ANIM_ZONE_W + 3
        chat_w = w - chat_x - 3
        visible_msg = self.messages[-(h - 8):]
        for idx, (sender, text) in enumerate(visible_msg):
            line = f"{sender}: {text}"[:chat_w]
            color = self.term.green if sender == "Джарвис" else self.term.magenta
            self._draw_string(frame, 4 + idx, chat_x, line)
            self._draw_string(frame, 4 + idx, chat_x, f"{sender}:", color)

        # 5. Строка статуса и буфер ввода
        self._draw_string(frame, h - 3, 2, f" СТАТУС » {self.status} ", self.term.black_on_yellow)
        self._draw_string(frame, h - 1, 2, f" USER@JARVIS:_> {self.input_buffer}", self.term.bold_white)

        # Двойная буферизация: склеиваем матрицу в одну строку и отдаем в stdout за один системный вызов
        output_data = "".join("".join(row) for row in frame)
        print(self.term.home + output_data, end="", flush=True)