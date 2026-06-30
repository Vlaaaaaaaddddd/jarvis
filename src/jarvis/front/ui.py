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
        self.messages = [("Джарвис", "Отрисовка идет")]

        # Заранее создаем массив, где символы уже обернуты в цвета 
        ramp = cfg.SHADING_RAMP
        ramp_len = len(ramp)
        styled_list = []

        for i, char in enumerate(ramp):
            approx_L = i / (ramp_len - 1) if ramp_len > 1 else 0.0
            color = self.term.bold_green if approx_L > 0.8 else self.term.green
            styled_list.append(color(char))
        
        # Переводим в NumPy массив объектов, чтобы использовать векторный выбор
        self.styled_ramp = np.array(styled_list, dtype=object)

    def start(self):
        """Вход в полноэкранный режим"""
        print(self.term.enter_fullscreen + self.term.hide_cursor + self.term.clear)

    def stop(self):
        """Выход из полноэкранного режима """
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
        radius = min(cfg.ANIM_ZONE_W // 4, (h - 8) // 2)

        # Получаем спроецированные координаты, глубину и яркость из ядра
        px, py, ooz, luminance = m3d.get_projected_donut(self.base_donut, t, radius, center_x, center_y)

        # Создаем булеву маску: True только для точек, проецируемых внутрь зоны анимации и имеющих свет
        mask = (px > 1) & (px < cfg.ANIM_ZONE_W - 1) & (py > 3) & (py < h - 4) & (luminance > 0)

        if not np.any(mask):
            return
        
        # Фильтруем массивы, оставляя только валидные данные
        x = px[mask]
        y = py[mask]
        z = ooz[mask]
        L = luminance[mask]

        # Нам нужно отрисовать сначала далекие точки, затем ближние
        # np.argsort возвращает индексы от дальних к ближним
        sort_indices = np.argsort(z)
        x = x[sort_indices]
        y = y[sort_indices]
        L = L[sort_indices]

        ramp_len = len(self.styled_ramp)
        ramp_indices = (L * (ramp_len - 1)).astype(int)
        ramp_indices = np.clip(ramp_indices, 0, ramp_len - 1)

        # Извлекаем раскрашенные символы для всех точек ОДНИМ действием
        chars_to_draw = self.styled_ramp[ramp_indices]

        # Записываем все тысячи точек в матрицу кадра без циклов
        matrix[y, x] = chars_to_draw

    def render_frame(self, current_time: float):
        """Сборка кадра"""
        h, w = self.term.height, self.term.width
        if h < cfg.MIN_H or w < cfg.MIN_W:
            print(self.term.home + "Расширьте окно терминала...", end="", flush=True)
            return

        # Инициализируем пустую текстовую матрицу кадра
        frame = np.full((h, w), " ", dtype=object)

        # 1. Строим статические рамки киберпанк-дашборда
        frame[0, :] = self.term.cyan("-")
        frame[2, :] = self.term.cyan("-")
        frame[h - 4, :] = self.term.cyan("-")
        frame[h - 2, :] = self.term.cyan("-")
        frame[:, 0] = self.term.cyan("|")
        frame[:, w - 1] = self.term.cyan("|")
        frame[2:h-4, cfg.ANIM_ZONE_W] = self.term.cyan("│")

        self._draw_string(frame, 1, 4, "Jarvis v0.01", self.term.bold_cyan)
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