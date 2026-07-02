import numpy as np
from blessed import Terminal
import jarvis.config.ui_config as cfg
import jarvis.utils.math_3d as m3d

class TerminalUI:
    def __init__(self, message=None):
        self.term = Terminal()
        self.status = "СИСТЕМА АКТИВНА"
        self.input_buffer = ""
        self._cbreak_ctx = None
        self.messages = [("Джарвис", message)] if message else []

        # Генерируем базовые точки один раз при инициализации
        self.base_donut = m3d.generate_donut()

        # Заранее создаем массив, где символы уже обернуты в цвета 
        ramp = cfg.SHADING_RAMP
        ramp_len = len(ramp)
        styled_list = []

        for i, char in enumerate(ramp):
            approx_L = i / (ramp_len - 1) if ramp_len > 1 else 0.0
            color = self.term.bold_white if approx_L > 0.8 else self.term.grey
            styled_list.append(color(char))
        
        # Переводим в NumPy массив объектов, чтобы использовать векторный выбор
        self.styled_ramp = np.array(styled_list, dtype=object)

    def start(self):
        """Вход в полноэкранный режим"""
        self._cbreak_ctx = self.term.cbreak()
        self._cbreak_ctx.__enter__()
        print(self.term.enter_fullscreen + self.term.hide_cursor + self.term.clear)

    def stop(self):
        """Выход из полноэкранного режима """
        print(self.term.exit_fullscreen + self.term.normal_cursor)
        if self._cbreak_ctx:
            self._cbreak_ctx.__exit__(None, None, None)

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

        self._draw_borders(frame, h, w)
        self._draw_headers(frame)
        self._embed_donut(frame, h, current_time)      # Твоя математическая сфера
        self._draw_chat_history(frame, h, w)           # Правая часть (вывод ответов)
        self._draw_input_zone(frame, h, w)

        frame[h - 1, w - 1] = "" 
        output_data = "".join("".join(row) for row in frame)
        print(self.term.home + output_data, end="", flush=True)

    def _draw_borders(self, frame, h: int, w: int):
        """Отрисовка сетки"""
        # Горизонтальные линии
        self._draw_string(frame, 0, 0, "-" * w, self.term.cyan)
        self._draw_string(frame, 2, 0, "-" * w, self.term.cyan)
        self._draw_string(frame, h - 4, 0, "-" * w, self.term.cyan)
        self._draw_string(frame, h - 2, 0, "-" * w, self.term.cyan)

        # Вертикальные границы
        for r in range(h):
            self._draw_string(frame, r, 0, "|", self.term.cyan)
            self._draw_string(frame, r, w - 1, "|", self.term.cyan)

        # Разделитель между анимацией и текстовым контентом
        for r in range(2, h - 4):
            self._draw_string(frame, r, cfg.ANIM_ZONE_W, "│", self.term.cyan)

    def _draw_headers(self, frame):
        """Отрисовка статичных заголовков панелей"""
        self._draw_string(frame, 1, 4, "Jarvis v0.01", self.term.bold_cyan)
        self._draw_string(frame, 3, cfg.ANIM_ZONE_W + 3, "ДИАЛОГОВЫЙ КОНТЕНТ", self.term.bold_green)

    def _draw_chat_history(self, frame, h: int, w: int):
        chat_x = cfg.ANIM_ZONE_W + 3
        chat_w = w - chat_x - 3
        max_lines = h - 8
        
        display_lines = []  # Список кортежей вида: (sender_to_draw, text_chunk)

        for sender, text in self.messages:
            if not text:
                continue
                
            # 1. Разбиваем текст по явным переносам строк (\n)
            lines = text.splitlines()
            if not lines and text:  # Обработка строк, состоящих только из \n
                lines = [""]

            for i, line in enumerate(lines):
                if i == 0:
                    # Для первой строки сообщения учитываем префикс "{sender}: "
                    prefix_len = len(sender) + 2
                    avail_w = chat_w - prefix_len
                    
                    # Кладем первый кусок вместе с именем отправителя
                    display_lines.append((sender, line[:avail_w]))
                    
                    # Если остаток строки не влезает, режем его по полной ширине chat_w
                    remaining = line[avail_w:]
                    while remaining:
                        display_lines.append(("", remaining[:chat_w]))
                        remaining = remaining[chat_w:]
                else:
                    # Для последующих строк (после \n) режем по полной ширине chat_w.
                    # Важно: для ASCII-арта и стихов не добавляем отступ, чтобы не плыла геометрия!
                    if not line:
                        display_lines.append(("", ""))
                        continue
                    
                    remaining = line
                    while remaining:
                        display_lines.append(("", remaining[:chat_w]))
                        remaining = remaining[chat_w:]

        # 2. Оставляем только те строки, которые физически влезают в окно по высоте
        visible_lines = display_lines[-max_lines:]

        # 3. Построчно отрисовываем в матрицу кадра
        for idx, (sender, text_chunk) in enumerate(visible_lines):
            row_idx = 4 + idx
            
            if sender:
                # Подсвечиваем и рисуем имя отправителя
                sender_color = self.term.green if sender == "Джарвис" else self.term.magenta
                self._draw_string(frame, row_idx, chat_x, f"{sender}:", sender_color)
                # Выводим текст сразу за именем
                self._draw_string(frame, row_idx, chat_x + len(sender) + 2, text_chunk)
            else:
                # Выводим перенесенный текст или строки ASCII-арта с начала текстовой панели
                self._draw_string(frame, row_idx, chat_x, text_chunk)

    def _draw_input_zone(self, frame, h: int, w: int):
        # Строка статуса
        status_line = f" СТАТУС » {self.status} "[:w - 4]
        self._draw_string(frame, h - 3, 2, status_line, self.term.black_on_yellow)

        # Активный инпут пользователя
        input_line = f" USER:_> {self.input_buffer}"[:w - 4]
        self._draw_string(frame, h - 1, 2, input_line, self.term.bold_white)