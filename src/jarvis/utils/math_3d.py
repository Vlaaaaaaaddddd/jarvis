import numpy as np
import jarvis.config.ui_config as cfg

def generate_donut():
    """Генерирует базовую 3D-геометрию тора (пончика) и его нормали (вектора поверхности)"""
    # R1 - толщина самого пончика, R2 - радиус дырки
    R1 = 1.0
    R2 = 2.0
    
    # Создаем плотную сетку углов (theta - сечение, phi - вокруг главной оси)
    theta = np.arange(0, 2 * np.pi, 0.07)
    phi = np.arange(0, 2 * np.pi, 0.02)
    theta, phi = np.meshgrid(theta, phi)
    theta = theta.flatten()
    phi = phi.flatten()
    
    # 1. 3D-координаты поверхности тора
    x = (R2 + R1 * np.cos(theta)) * np.cos(phi)
    y = R1 * np.sin(theta)
    z = (R2 + R1 * np.cos(theta)) * np.sin(phi)
    
    # 2. Нормали поверхности (нужны для расчета теней/освещения)
    nx = np.cos(theta) * np.cos(phi)
    ny = np.sin(theta)
    nz = np.cos(theta) * np.sin(phi)
    
    return x, y, z, nx, ny, nz

def get_projected_donut(base_coords, t, radius, center_x, center_y):
    """Поворачивает тор и рассчитывает освещение для каждого пикселя"""
    bx, by, bz, bnx, bny, bnz = base_coords
    
    # Углы поворота от времени
    A = t * cfg.ROT_SPEED_X
    B = t * cfg.ROT_SPEED_Y
    
    cA, sA = np.cos(A), np.sin(A)
    cB, sB = np.cos(B), np.sin(B)
    
    # Вращение координат точек (X, затем Z)
    x1 = bx
    y1 = by * cA - bz * sA
    z1 = by * sA + bz * cA
    
    x2 = x1 * cB - y1 * sB
    y2 = x1 * sB + y1 * cB
    z2 = z1
    
    # Вращение нормалей (векторов, торчащих из поверхности)
    nx1 = bnx
    ny1 = bny * cA - bnz * sA
    nz1 = bny * sA + bnz * cA
    
    nx2 = nx1 * cB - ny1 * sB
    ny2 = nx1 * sB + ny1 * cB
    nz2 = nz1
    
    # РАСЧЕТ ОСВЕЩЕНИЯ (Shading)
    # Свет падает сверху-сзади-справа
    L = np.array([0, 1, -1])
    L = L / np.linalg.norm(L) 
    
    # Скалярное произведение нормали и вектора света дает яркость (чем больше, тем светлее)
    luminance = nx2 * L[0] + ny2 * L[1] + nz2 * L[2]
    
    # 3D ПРОЕКЦИЯ НА ЭКРАН
    K2 = 7.5  # Дистанция от "камеры" до пончика
    z_shifted = z2 + K2
    ooz = 1.0 / z_shifted  # Обратная глубина (1/Z) для Z-буфера
    
    K1 = radius * 2.0  # Масштабирование
    
    # x2 умножаем на 2.2, так как шрифты терминала вытянуты по вертикали
    proj_x = (center_x + K1 * ooz * x2 * 2.2).astype(int)
    proj_y = (center_y + K1 * ooz * y2).astype(int)
    
    return proj_x, proj_y, ooz, luminance