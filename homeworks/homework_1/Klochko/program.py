import json
from math import pi, log, radians, cos
import numpy as np
from scipy.integrate import solve_ivp


def calc_ws(
        gamma_water: float
) -> float:
    """
    Функция для расчета солесодержания в воде

    :param gamma_water: относительная плотность по пресной воде с плотностью 1000 кг/м3, безразм.

    :return: солесодержание в воде, г/г
    """
    ws = (
            1 / (gamma_water * 1000) 
            * (1.36545 * gamma_water * 1000 - (3838.77 * gamma_water * 1000 - 2.009 * (gamma_water * 1000) ** 2) ** 0.5)
    )  
    # если значение отрицательное, значит скорее всего плотность ниже допустимой 992 кг/м3
    if ws > 0:
        return ws
    else:
        return 0

def calc_rho_w(
        ws: float,
        t: float
) -> float:
    """
    Функция для расчета плотности воды в зависимости от температуры и солесодержания

    :param ws: солесодержание воды, г/г
    :param t: температура, К

    :return: плотность воды, кг/м3
    """
    rho_w = 1000 * (1.0009 - 0.7114 * ws + 0.2605 * ws ** 2) ** (-1)

    return rho_w / (1 + (t - 273) * 1e-4 * (0.269 * (t - 273) ** 0.637 - 0.8))

def calc_mu_w(
        ws: float,
        t: float,
        p: float
) -> float:
    """
    Функция для расчета динамической вязкости воды по корреляции Matthews & Russel

    :param ws: солесодержание воды, г/г
    :param t: температура, К
    :param p: давление, МПа

    :return: динамическая вязкость воды, сПз
    """
    a = (
            109.574
            - (0.840564 * 1000 * ws)
            + (3.13314 * 1000 * ws ** 2)
            + (8.72213 * 1000 * ws ** 3)
    )
    b = (
            1.12166
            - 2.63951 * ws
            + 6.79461 * ws ** 2
            + 54.7119 * ws ** 3
            - 155.586 * ws ** 4
    )

    mu_w = (
            a * (1.8 * t - 460) ** (-b)
            * (0.9994 + 0.0058 * (p * 0.101325) + 0.6534 * 1e-4 * (p * 0.101325) ** 2)
    )
    return mu_w

def calc_n_re(
        rho_w: float,
        q_liq: float,
        mu_w: float,
        d_tub: float
) -> float:
    """
    Функция для расчета числа Рейнольдса

    :param rho_w: плотность воды, кг/м3
    :param q_liq: дебит жидкости, м3/с
    :param mu_w: динамическая вязкость воды, сПз
    :param d_tub: диаметр НКТ, м

    :return: число Рейнольдса, безразмерн.
    """
    v = q_liq / (pi * d_tub ** 2 / 4)
    return rho_w * v * d_tub / mu_w * 1000

def calc_f_churchill(
        n_re: float,
        roughness: float,
        d_tub: float
) -> float:
    """
    Функция для расчета коэффициента трения по корреляции Churchill

    :param n_re: число Рейнольдса, безразмерн.
    :param roughness: шероховатость стен трубы, м
    :param d_tub: диаметр НКТ, м

    :return: коэффициент трения, безразмерн.
    """
    a = (-2.457 * log((7 / n_re) ** 0.9 + 0.27 * (roughness / d_tub))) ** 16
    b = (37530 / n_re) ** 16

    f = 8 * ((8 / n_re) ** 12 + 1 / (a + b) ** 1.5) ** (1/12)
    return f

def dp(
        p, l, t,
        t_wh: float, 
        temp_grad: float, 
        md_vdp: float, 
        gamma_water: float, 
        roughness: float, 
        angle: float, 
        d_tub: float, 
        q_liq: float
):
    """
    Функция для расчета градиента давления для произвольного участка скважины

    :param t_wh: температура жидкости у буферной задвижки, градусы цельсия
    :param temp_grad: геотермический градиент, градусы цельсия/100 м
    :param md_vdp: измеренная глубина верхних дыр перфорации, м
    :param gamma_water: относительная плотность по пресной воде с плотностью 1000 кг/м3, безразм.
    :param angle: угол наклона скважины к горизонтали, градусы
    :param q_liq: дебит закачиваемой жидкости
    :param d_tub: диаметр НКТ, м

    :return: градиент давления для произвольного участка скважины
    """
    xi = 1 / 10 ** 6
    t = (t_wh + (temp_grad * l) / 100) + 273 
    ws = calc_ws(gamma_water)
    rho_w = calc_rho_w(ws, t)
    g = 9.81
    
    mu_w = calc_mu_w(ws, t, p)
    n_re = calc_n_re(rho_w, q_liq, mu_w, d_tub)
    f = calc_f_churchill(n_re, roughness, d_tub)
    
    dp = xi * (rho_w * g * cos(radians(angle)) - 0.815 * f * rho_w / d_tub ** 5 * q_liq ** 2)
     
    return dp

def main(**kwargs):
    
    q_liq = np.linspace(1, 400, 41)
    q_liq = [int(q_liq[_]) for _ in range(len(q_liq))]
    q_liq = np.array(q_liq)
    
    p_wf = []
    q_liq_sec = q_liq / (60 * 60 * 24)
    for _ in q_liq_sec:
        sol = solve_ivp(
                        dp, 
                        t_span = [0, kwargs['md_vdp']], 
                        y0 = [kwargs['p_wh'] * 0.101325],
                        args = (  
                                kwargs['t_wh'], kwargs['t_wh'], kwargs['temp_grad'], kwargs['md_vdp'],
                                kwargs['gamma_water'], kwargs['roughness'], kwargs['angle'], kwargs['d_tub'], _
                        ), 
                        t_eval = [kwargs['md_vdp']]
        )
        p_wf.append(sol.y[0][0] * 9.86923)
    
    q_liq = list(q_liq)
    q_liq = [int(q_liq[_]) for _ in range(len(q_liq))] 
    result = {'q_liq': q_liq, 'p_wf': p_wf}
    
    return result


if __name__ == "__main__":

    with open('8.json') as file:
        data = json.load(file)

    output = main(**data)

    with open(r"output.json", "w", ) as  file:
        json.dump(output, file, indent = 4)