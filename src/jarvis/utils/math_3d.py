import numpy as np
import jarvis.config.ui_config as cfg

def generate_donut():
    """База тора"""
    # Создаем сетку углов (theta - x, phi - y)
    theta = np.arange(0, 2 * np.pi, 0.15)
    phi = np.arange(0, 2 * np.pi, 0.05)
    theta, phi = np.meshgrid(theta, phi)
    theta = theta.flatten()
    phi = phi.flatten()
    
    # 3D-координаты поверхности тора
    x = (cfg.R2 +cfg.R1 * np.cos(theta)) * np.cos(phi)
    y =cfg.R1 * np.sin(theta)
    z = (cfg.R2 +cfg.R1 * np.cos(theta)) * np.sin(phi)
    
    # Нормали поверхности
    nx = np.cos(theta) * np.cos(phi)
    ny = np.sin(theta)
    nz = np.cos(theta) * np.sin(phi)
    
    return x, y, z, nx, ny, nz

def get_projected_donut(base_coords, t, radius, center_x, center_y):
    """Поворачивает тор через матрицы и рассчитывает проекцию и освещение"""
    bx, by, bz, bnx, bny, bnz = base_coords
    
    # Углы поворота от времени
    A = t * cfg.ROT_SPEED_X
    B = t * cfg.ROT_SPEED_Y
    
    cA, sA = np.cos(A), np.sin(A)
    cB, sB = np.cos(B), np.sin(B)
    
    # Сборка матриц данных
    points = np.vstack((bx, by, bz))
    normals = np.vstack((bnx, bny, bnz))
    
    # Матрицы поворота
    R_x = np.array([[1, 0, 0], [0, cA, -sA], [0, sA, cA]])
    R_z = np.array([[cB, -sB, 0], [sB, cB, 0], [0, 0, 1]])
    
    # Полная трансформация
    R_total = R_z @ R_x
    
    # Вращение
    x2, y2, z2 = R_total @ points
    nx2, ny2, nz2 = R_total @ normals
    
    # Расчет освещения
    L = np.array([0, 1, -1])
    L = L / np.linalg.norm(L)
    # Используем векторное умножение для яркости
    luminance = nx2 * L[0] + ny2 * L[1] + nz2 * L[2]
    
    # Проекция
    K1 = radius * 2.0
    K2 = 7.5
    z_shifted = z2 + K2
    ooz = 1.0 / z_shifted
    
    
    proj_x = (center_x + K1 * ooz * x2 * 2.2).astype(int)
    proj_y = (center_y + K1 * ooz * y2).astype(int)
    
    return proj_x, proj_y, ooz, luminance