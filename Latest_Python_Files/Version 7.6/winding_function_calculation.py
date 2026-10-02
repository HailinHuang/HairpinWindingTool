# -*- coding: utf-8 -*-
"""
Created on Thu Jul 24 15:34:33 2025

@author: ezzhh5
"""
import numpy as np
import matplotlib.pyplot as plt

def draw_gorges_diagram(Cond_info, num_slots, phase=0):
    """
    Draw Görges diagram for one phase, with one point per slot.
    
    Parameters
    ----------
    Cond_info : list of tuples
        Each: (slot, layer, phase_index, branch_id, cond_index, cond_phasor, pole_index)
    num_slots : int
        Total number of slots Q.
    phase : int
        Which phase to plot (0-based).
    """
    # 1) 每槽累加 MMF（正负由 pole_index 决定）
    mmf_per_slot = np.zeros(num_slots, dtype=int)
    for slot, layer, ph_idx, *_ , pole_idx in Cond_info:
        if ph_idx == phase:
            sign = 1 if (pole_idx % 2 == 0) else -1
            mmf_per_slot[slot] += sign

    # 2) 计算每槽的 phasor V_i
    slots = np.arange(num_slots)
    angles = 2 * np.pi * slots / num_slots
    slot_phasors = mmf_per_slot * np.exp(1j * angles)

    # 3) tip-to-tail 累加，得到多边形顶点
    polygon = np.cumsum(slot_phasors)

    # 4) 绘图
    plt.figure(figsize=(6,6))
    # 红色折线和点
    plt.plot(polygon.real, polygon.imag,
             '-o', color='red', markerfacecolor='red', label='GD')
    # 原点小十字
    span = max(abs(polygon.real).max(), abs(polygon.imag).max()) * 1.1
    plt.plot([-span, span], [0, 0], 'k-', linewidth=0.5)
    plt.plot([0, 0], [-span, span], 'k-', linewidth=0.5)

    plt.xlabel('MMF (A·turn)')
    plt.ylabel('MMF (A·turn)')
    plt.title(f'Görges Diagram — Phase {phase}')
    plt.axis('equal')
    plt.grid(True)
    plt.legend()
    plt.show()

def get_phase_cond_locations(cond_info, phase=0):
    """
    This first step in the determination of H is the sketch of conductor locations of each phase, the function can get the cond locationas for a given phase-id based on cond_info
    """
    cond_array = np.array(cond_info)
    num_slots = int(np.max(cond_array[:, 0])) + 1
    turns_per_pole_pair = 0
    phase_conds = [0] * num_slots
    
    for c in cond_info:
        slot = int(c[0])
        phase_index = int(c[2])
        pole_index = int(c[-1])  # 最后一列是 pole_index
        if phase_index == phase:
            sign = 1 if (pole_index % 2 == 0) else -1
            phase_conds[slot] += sign
            if pole_index == 0:
                turns_per_pole_pair += 1
    
    return phase_conds

def get_winding_function(phase_conds):
    """
    The function N_theta is obtained by counting the enclosed positive conductors at each value of theta.
    """
    winding_func = []
    running_sum = 0.0
    
    for val in phase_conds:
        running_sum += val
        winding_func.append(running_sum)
    """
    The function N_theta is then shifted vertically to achieve zero average value. 
    """
    avg = sum(winding_func) / len(winding_func)
    
    winding_func = [round(x - avg, 2) for x in winding_func]

    return winding_func

def plot_winding_function(winding_func,Winding_Para):
    wf_plot = list(winding_func)
    wf_plot.append(wf_plot[0])
    
    num_slots = Winding_Para.num_slots
    num_pole_pairs = Winding_Para.num_poles // 2
    
    angle_per_slot = 360 * num_pole_pairs / num_slots
    
    x_step = np.arange(len(wf_plot)) * angle_per_slot  # 电角度
    x_max = num_slots * angle_per_slot
    
    step_angle = x_max / num_pole_pairs / 4
    xticks = np.arange(0, x_max+ 1e-9, step_angle)
    
    plt.figure(figsize=(8, 3), dpi=300)
    plt.step(x_step, wf_plot, where='post', color='tab:red')
    plt.xlabel('Electrical Angle (deg)')
    plt.xlim(0, x_max)
    plt.xticks(xticks)  # 电角度刻度
    plt.ylabel('Winding Function')
    plt.grid(True, axis='y', linestyle=':')
    plt.tight_layout()
    plt.show()


def fast_fft_wf(winding_func, Winding_Para,max_iter=8):
    """
    Compute the winding factors with extended N_theta samples for order 1 to num_slots/2
    """
    
    num_slots = Winding_Para.num_slots
    num_pole_pairs = Winding_Para.num_poles // 2
    angle_per_slot = (2 * np.pi * num_pole_pairs) / num_slots
    turns_per_pole_per_phase = Winding_Para.num_layers * Winding_Para.q / 2
    
    theta_max = 2 * np.pi * num_pole_pairs
    
    # 初始采样密度
    K_per_slot = 32
    last_result = None
    K_ho_rounded = None
    for _ in range(max_iter):
        num_samples = num_slots * K_per_slot
        theta_max = 2 * np.pi * num_pole_pairs
        theta = np.linspace(0, theta_max, num_samples, endpoint=False)
        N_theta = np.zeros_like(theta)

        # 构造阶梯函数
        for i, th in enumerate(theta):
            slot_idx = int(th // angle_per_slot)
            if slot_idx >= len(winding_func):
                slot_idx = len(winding_func) - 1
            N_theta[i] = winding_func[slot_idx]

        # FFT
        N = len(N_theta)
        fft_res = np.fft.fft(N_theta)
        h_all = np.arange(1, N // 2)
        mag = np.abs(fft_res[h_all]) / N * 2
        K_all = mag / turns_per_pole_per_phase * (np.pi / 4) * h_all / num_pole_pairs

        # 保留前 num_slots//2 个谐波
        max_ho = num_slots // 2
        h_o = h_all[:max_ho]
        K_ho = K_all[:max_ho]

        # 过滤：只保留 num_pole_pairs 的倍数,,且过滤掉  num_slots // 2
        mask = (h_o % num_pole_pairs == 0)
        K_ho_filtered = K_ho.copy()
        K_ho_filtered[~mask] = 0.0
        K_ho_filtered[h_o == num_slots//2] = 0.0

        # 四舍五入到 4 位小数
        K_ho_check = np.round(K_ho_filtered, 4)

        # 检查是否收敛
        if last_result is not None:
            if np.allclose(K_ho_check, last_result, atol=0.0):
                # 收敛，结束
                break
        
        last_result = K_ho_check.copy()
        K_per_slot *= 2  # 提高采样精度
        
    K_ho_rounded = np.round(K_ho_check, 3)
    return h_o, K_ho_rounded, K_per_slot // 2

    
def get_winding_factor(winding_func, Winding_Para, harmonic_order):
    """
    Compute the winding factor for a single specified harmonic order.

    Parameters
    ----------
    winding_func : list or np.ndarray
        Winding function per slot (length = num_slots).
    Winding_Para : object
        Must have attributes: num_slots, num_poles, num_layers, q
    harmonic_order : int
        Harmonic order h to compute (1-based, e.g. 1 = fundamental)

    Returns
    -------
    K_h : float
        Winding factor for that harmonic order
    """
    wf_temp = list(winding_func)
    wf_temp = np.array(wf_temp, dtype=float)
    N = len(wf_temp)
    
    num_slots = Winding_Para.num_slots
    num_pole_pairs = Winding_Para.num_poles // 2
    turns_per_pole_per_phase = Winding_Para.num_layers * Winding_Para.q // 2
    num_phases = Winding_Para.num_phases
    
    # FFT on slot-level data
    fft_res = np.fft.fft(wf_temp)
    h_all = np.arange(1, N//2)
    mag = np.abs(fft_res[h_all]) / (N/2)  # scale to amplitude
    
    # Convert to winding factor
    K_all = mag / turns_per_pole_per_phase * (np.pi/4) * h_all / num_pole_pairs
    
    # Optional: filter out harmonics not aligned with winding symmetry
    for idx, h in enumerate(h_all):
        if (h % num_pole_pairs != 0) or ((h // num_pole_pairs) % num_phases == 0):
            K_all[idx] = 0.0
    
    ho = int(harmonic_order % num_slots)
    if ho > num_slots // 2:
        ho = num_slots - ho
    elif ho == num_slots // 2:
        ho = 0
    K_ho = K_all[ho]
    
    
    return K_ho
    

def plot_winding_factor(winding_func, Winding_Para,max_ho=50):
    """
    Compute winding factors by first extending winding_func into N_theta(theta),
    then doing FFT and plotting both N_theta(theta) and winding factor spectrum.

    Parameters
    ----------
    winding_func : list or np.ndarray
        Winding function values per slot
    Winding_Para : object
        Must have attributes: num_slots, num_poles, num_layers, q
    harmonic_order : int
        Which harmonic order's winding factor to return (1-based, e.g. 1 for fundamental)

    Returns
    -------
    K_h : float
        Winding factor of the given harmonic order
    """
    wf_temp = list(winding_func)
    wf_temp.append(wf_temp[0])
    wf_temp = np.array(wf_temp, dtype=float)
    num_slots = Winding_Para.num_slots
    num_pole_pairs = Winding_Para.num_poles // 2
    num_phases = Winding_Para.num_phases


    # 每槽对应的电角度（弧度）
    angle_per_slot = (2 * np.pi * num_pole_pairs) / num_slots
    theta_max = 2 * np.pi * num_pole_pairs  # θ范围
    # ------------------------------
    # 绘制 N_theta(theta)
    # ------------------------------
    plt.figure(figsize=(8,6), dpi=300)
    plt.subplot(2,1,1)
    x_max = theta_max * 180 / np.pi
    step_angle = x_max / (num_pole_pairs * 4)
    x_step = np.arange(len(wf_temp)) * angle_per_slot * 180 / np.pi
    xticks = np.arange(0, x_max+1e-9, step_angle)
    # # 绘制槽级阶梯
    plt.step(x_step, wf_temp, where='post', color='tab:red', alpha=0.6, label='Discrete per slot')
    plt.xlabel('Electrical Angle θ (deg)')
    plt.ylabel('N(θ)')
    plt.title('Winding Function N(θ)')
    plt.xlim(0, x_max)
    
    plt.xticks(xticks)
    plt.grid(True, axis='y', linestyle=':')

    # FFT on slot-level data
    h_all, K_all,K_per_slot = fast_fft_wf(winding_func, Winding_Para)
    
    ho_plot = np.arange(0, max_ho)
    K_plot = np.zeros(max_ho)
    
    for h in range(len(ho_plot)-1):
        ho = int(h % num_slots) 
        
        if ho == 0:
            K_plot[h] = 0
        elif ho == int(num_slots // 2):
            ho = 0
            K_plot[h] = 0
        elif ho > int(num_slots // 2):
            ho = num_slots - ho
            K_plot[h] = K_all[ho-1]
        else:
            K_plot[h] = K_all[ho-1]
             

    # ------------------------------
    # 绘制 FFT 谐波谱
    # ------------------------------

    plt.subplot(2,1,2)
    # 过滤掉为 0 的谐波  以及 三相对称基波倍数次谐波
    base_harmonic = int(num_pole_pairs * num_phases)
    mod_result = np.mod(ho_plot, base_harmonic)
    not_multiple = ~np.isclose(mod_result, 0, atol=1e-6)
    mask = (K_plot != 0) & not_multiple
    ho_nonzero = ho_plot[mask]        # 只取对应的横坐标
    K_nonzero = K_plot[mask]         # 只取对应的纵坐标
    plt.stem(ho_nonzero, K_nonzero, basefmt=" ")

    max_h = ho_plot[-1] if len(ho_plot) > 0 else 0
    tick_step = num_pole_pairs
    xticks = np.arange(0, max_h + 1, tick_step)
    plt.xticks(xticks)
    plt.xlim(0, max_h)
    plt.xlabel('Harmonic Order h')
    plt.ylabel('Winding Factor K')
    plt.title('Winding Factors Spectrum')
    
    plt.ylim(0, 1)
    plt.grid(True, axis='y', linestyle=':')
    plt.tight_layout()
    plt.show()
    

def plot_winding_factor_ax(winding_func, Winding_Para, max_ho=50, ax1=None, ax2=None):
    """
    Same as plot_winding_factor, but plots on given axes (ax1 for N(θ), ax2 for spectrum).

    Parameters
    ----------
    winding_func : list or np.ndarray
        Winding function values per slot
    Winding_Para : object
        Must have attributes: num_slots, num_poles, num_layers, q
    max_ho : int
        Max harmonic order to plot
    ax1 : matplotlib.axes.Axes
        Axis for N(theta)
    ax2 : matplotlib.axes.Axes
        Axis for harmonic spectrum

    """
    import numpy as np

    if ax1 is None or ax2 is None:
        raise ValueError("Both ax1 and ax2 must be provided for embedded plotting.")

    wf_temp = list(winding_func)
    wf_temp.append(wf_temp[0])
    wf_temp = np.array(wf_temp, dtype=float)
    num_slots = Winding_Para.num_slots
    num_pole_pairs = Winding_Para.num_poles // 2
    num_phases = Winding_Para.num_phases
    angle_per_slot = (2 * np.pi * num_pole_pairs) / num_slots
    theta_max = 2 * np.pi * num_pole_pairs
    x_max = theta_max * 180 / np.pi
    step_angle = x_max / (num_pole_pairs * 4)
    x_step = np.arange(len(wf_temp)) * angle_per_slot * 180 / np.pi
    xticks = np.arange(0, x_max + 1e-9, step_angle)

    # ------------------------------
    # 绘制 N_theta(theta)
    # ------------------------------
    ax1.clear()
    ax1.step(x_step, wf_temp, where='post', color='tab:red', alpha=0.6, label='Discrete per slot')
    ax1.set_xlabel('Electrical Angle θ (deg)')
    ax1.set_ylabel('N(θ)')
    # ax1.set_title('Winding Function N(θ)',pad=10)
    ax1.set_xlim(0, x_max)
    ax1.set_xticks(xticks)
    ax1.grid(True, axis='y', linestyle=':')
    ax1.figure.subplots_adjust(hspace=0.4)  # Adjust vertical space between subplots
    
    # ------------------------------
    # 计算 FFT
    # ------------------------------
    h_all, K_all, K_per_slot = fast_fft_wf(winding_func, Winding_Para)

    ho_plot = np.arange(0, max_ho)
    K_plot = np.zeros(max_ho)

    for h in range(len(ho_plot) - 1):
        ho = int(h % num_slots)
        if ho == 0 or ho == int(num_slots // 2):
            K_plot[h] = 0
        elif ho > int(num_slots // 2):
            ho = num_slots - ho
            if 0 <= ho - 1 < len(K_all):
                K_plot[h] = K_all[ho - 1]
        else:
            if 0 <= ho - 1 < len(K_all):
                K_plot[h] = K_all[ho - 1]

    # ------------------------------
    # 绘制 FFT 谐波谱
    # ------------------------------
    ax2.clear()
    base_harmonic = int(num_pole_pairs * num_phases)
    mod_result = np.mod(ho_plot, base_harmonic)
    not_multiple = ~np.isclose(mod_result, 0, atol=1e-6)
    
    mask = (K_plot != 0) & not_multiple
    ho_nonzero = ho_plot[mask]
    K_nonzero = K_plot[mask]

    ax2.stem(ho_nonzero, K_nonzero, basefmt=" ")
    # Add value labels above each bar
    for x, y in zip(ho_nonzero, K_nonzero):
        ax2.text(x + 0.7, y, f"{y:.3f}", ha='left', va='center', fontsize=8)
    max_h = ho_plot[-1] if len(ho_plot) > 0 else 0
    xticks = np.arange(0, max_h + 1, num_pole_pairs)
    ax2.set_xticks(xticks)
    ax2.set_xlim(0, max_h)
    ax2.set_xlabel('Harmonic Order h')
    ax2.set_ylabel('Winding Factor K')
    # ax2.set_title('Winding Factors Spectrum',pad=10)
    ax2.set_ylim(0, 1.05)
    ax2.axhline(y=1.0, color='gray', linestyle='--', linewidth=0.5, alpha=0.4)
    ax2.grid(True, axis='y', linestyle=':')
    








