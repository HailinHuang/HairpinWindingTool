# -*- coding: utf-8 -*-
"""
Created on Mon Jun 24 09:11:45 2024

@author: ezzhh5
"""
import numpy as np
import math
from scipy.optimize import fsolve
import warnings

def connect_bend_theta_solve(L_conn_str, L_conn_bend_A, R_height_bend):
    """
    Solve for theta_bC using fsolve, but if convergence or runtime errors
    occur, return 0 as a default fallback.
    """
    # If there's no "connection length," define theta_bC as 0
    if L_conn_str == 0:
        return 0.0

    # Define the equation f(a) = 0 to find a = tan(theta_bC)
    def equation(a):
        term1 = a * L_conn_bend_A
        term2 = R_height_bend * a**2 / np.sqrt(1 + a**2)
        return term1 - term2 - L_conn_str / 2

    # Pick an initial guess that works reasonably well in most cases
    initial_guess = 0.4

    # Suppress warnings and catch solver issues
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # Ignore 'not making good progress' etc.

        try:
            # Run fsolve with some parameters tuned for more iterations if needed
            a_solution, info, ier, msg = fsolve(
                equation, 
                x0=initial_guess,
                full_output=True,
                maxfev=2000,
                xtol=1e-8
            )

            # If ier != 1, fsolve did not converge
            if ier != 1:
                return 0.0

            # Convert from a=tan(theta_bC) to theta_bC
            theta_bC = np.arctan(a_solution[0])

            # Ensure it's within [0, pi/2]
            theta_bC = np.clip(theta_bC, 0, np.pi / 2)
            return theta_bC

        except Exception:
            # If anything goes wrong (overflow, zero division, etc.), return 0
            return 0.0

def calculate_layer_beta_angle(EW_info, Winding_Para,Stator_Para, Inslot_Para):
    num_layers = Winding_Para.num_layers
    num_slots = Winding_Para.num_slots
    gcond_min = EW_info.gcond_min  #### Minimum side gap between conductors in mm
    Stack_length,SD1,SD2,H_yoke,TH1,TH2,ksw,kso = Stator_Para 
    H_cond, W_cond, G_cond, Cond_Radi, C_rad, C_side, d_coat, d_Ins, *extra = Inslot_Para
    Rm_layer = [0] * num_layers  # Initialize the list with zeros: mid radius of conductor layers
    SP_layer = [0] * num_layers  # Slot pitch of each layer of magnet Initialize the list with zeros
    Thetab_layer = [0] * num_layers  # minimum theta of bending for each layer
    # RL1 = SD1 / 2 - H_yoke - d_Ins - d_coat - C_rad - H_cond/2  ### Radius of the layer 1
    RL1 = SD1 / 2 - H_yoke - C_rad - d_Ins - d_coat * 2 - H_cond + Inslot_Para.Cond_Radi  ### Radius of the layer 1
    # Wire_OD =  (RL1-Inslot_Para.Cond_Radi) * 2 + H_cond + d_coat * 2
    d_cond = H_cond + G_cond + 2 * d_coat
    Wcond_T = W_cond + d_coat * 2
    for i in range(num_layers):
        Rm_layer[i] = RL1 - i * d_cond
        SP_layer[i] = Rm_layer[i] * 2 * math.pi / num_slots
        Thetab_layer[i] = math.asin((gcond_min+Wcond_T) / SP_layer[i]) 
    return (Rm_layer,SP_layer,Thetab_layer)

def calculate_end_winding_length(L_start,L_end,S_span_insert,S_span_weld_A,S_span_weld_B,Winding_Para,Stator_Para,Inslot_Para,EW_info):
    L_str = EW_info.L_str ##Length of pin end straight part
    L_weld = EW_info.L_weld_str ##Length of weld straight part
    Stack_length,SD1,SD2,H_yoke,TH1,TH2,ksw,kso = Stator_Para 
    H_cond, W_cond, G_cond, Cond_Radi, C_rad, C_side, d_coat, d_Ins, *extra = Inslot_Para
    d_cond = H_cond + G_cond + 2 * d_coat
    Wcond_T = W_cond + d_coat * 2
    H_cond_T = H_cond + d_coat * 2
    if EW_info.fixed_Rbend == 1:
        Rbend_side_min = EW_info.Rbend_side_min
        Rbend_height_min = EW_info.Rbend_height_min
    else:
        Rbend_side_min = EW_info.K_bend_side * Wcond_T
        Rbend_height_min = EW_info.K_bend_height * H_cond_T
    Rm_layer,SP_layer,Thetab_layer = calculate_layer_beta_angle(EW_info, Winding_Para,Stator_Para, Inslot_Para)
    
    Length1 = L_str
    #### Get the min radius in calculating the SP_L and theta_bL
    Length2 = SP_layer[L_end] * S_span_insert * 0.5 / math.cos(Thetab_layer[L_end])
    Height_end = Length2 *  math.sin(Thetab_layer[L_end])
    Length3 = abs(L_end-L_start) * d_cond  ### This is the radial distance between two layers
    L_conn_str = Length3
    Length4 = math.sqrt(Height_end ** 2 + (SP_layer[L_start] * S_span_insert * 0.5) ** 2)
    Length5 = L_str
    R_side_bend = Rbend_side_min +  W_cond / 2 + d_coat
    R_height_bend =  Rbend_height_min + H_cond / 2 + d_coat
    ### to calculate the reduction of length due to the bending radius
    #### 1. The bending radius between Length1 and Length
    beta = math.pi / 4 - Thetab_layer[L_end] / 2
    delta_length_Rbend = 2 *  R_side_bend * (math.tan(beta)/2-beta)
    ####  To calculate the end winding length at the insert side 
    L_conn_bend_A = SP_layer[L_end] / 2 / math.cos(Thetab_layer[L_end]) - Wcond_T * (1+math.cos(2 * Thetab_layer[L_end])) / 2 / math.sin((2 * Thetab_layer[L_end]))
    theta_conn_bend = connect_bend_theta_solve(L_conn_str,L_conn_bend_A,R_height_bend)
    ##### theta_conn_bend is the 
    if theta_conn_bend == 0:
        delta_length_conn_bend = delta_length_Rbend
    else: 
        delta_length_conn_bend = 2 *  L_conn_bend_A + L_conn_str * (1-1/math.sin(theta_conn_bend)) + 2 * R_height_bend * (theta_conn_bend - math.tan(theta_conn_bend / 2))
    ##### Calculate the new L_str 
    New_L_str = L_str + R_side_bend * math.tan(beta)
    delta_L_str = R_side_bend * math.tan(beta)
    EndW_Length_insert = Length1 + Length2 + Length3 + Length4 + Length5 - delta_length_Rbend * 2 - delta_length_conn_bend + delta_L_str * 2
    
    #### Compared to the insert side, the weld side does not have the radial connection part (Length3), while it has the L-weld * 2.
#### Need to adjust here since on the welding side, the 
    
    Length_weld_A = SP_layer[L_start] * S_span_weld_A * 0.5 / math.cos(Thetab_layer[L_start])
    Length_weld_B = SP_layer[L_end] * S_span_weld_B * 0.5 / math.cos(Thetab_layer[L_end])
    EndW_Length_weld =  Length1 + Length5 + Length_weld_A + Length_weld_B + L_weld * 2 - delta_length_Rbend * 4 + delta_L_str * 2
    EndW_Length_total = EndW_Length_insert + EndW_Length_weld
    EndW_Height_insert = Height_end + New_L_str
    EndW_Height_weld = Height_end + New_L_str + L_weld
    Length_data = [L_str,Height_end,EndW_Height_insert,EndW_Length_insert,EndW_Height_weld,EndW_Length_weld,EndW_Length_total,New_L_str]

    return (Length_data)

def calculate_pin_winding_length(L_start,L_end,S_span_insert,S_span_weld,Winding_Para,Stator_Para,Inslot_Para,EW_info):
    L_str = EW_info.L_str ##Length of pin end straight part
    L_weld = EW_info.L_weld_str ##Length of weld straight part
    Stack_length,SD1,SD2,H_yoke,TH1,TH2,ksw,kso = Stator_Para 
    H_cond,W_cond,G_cond,Cond_Radi,C_rad, C_side, d_coat, d_Ins = Inslot_Para
    d_cond = H_cond + G_cond + 2 * d_coat
    Wcond_T = W_cond + d_coat * 2
    H_cond_T = H_cond + d_coat * 2
    if EW_info.fixed_Rbend == 1:
        Rbend_side_min = EW_info.Rbend_side_min
        Rbend_height_min = EW_info.Rbend_height_min
    else:
        Rbend_side_min = EW_info.K_bend_side * Wcond_T
        Rbend_height_min = EW_info.K_bend_height * H_cond_T
    Rm_layer,SP_layer,Thetab_layer = calculate_layer_beta_angle(EW_info, Winding_Para,Stator_Para, Inslot_Para)
    
    L_start, L_end = min(L_start, L_end), max(L_start, L_end)  #### ensure L_end > L_start
    Length1 = L_str
    #### Get the min radius in calculating the SP_L and theta_bL
    Length2 = SP_layer[L_end] * S_span_insert * 0.5 / math.cos(Thetab_layer[L_end])
    Height_end = Length2 *  math.sin(Thetab_layer[L_end])
    Length3 = abs(L_end-L_start) * d_cond  ### This is the radial distance between two layers
    L_conn_str = Length3
    Length4 = math.sqrt(Height_end ** 2 + (SP_layer[L_start] * S_span_insert * 0.5) ** 2)
    Length5 = L_str
    R_side_bend = Rbend_side_min +  W_cond / 2 + d_coat
    R_height_bend =  Rbend_height_min + H_cond / 2 + d_coat
    ### to calculate the reduction of length due to the bending radius
    #### 1. The bending radius between Length1 and Length
    beta = math.pi / 4 - Thetab_layer[L_end] / 2
    delta_length_Rbend = 2 *  R_side_bend * (math.tan(beta)-beta)
    ####  To calculate the end winding length at the insert side 
    L_conn_bend_A = SP_layer[L_end] / 2 / math.cos(Thetab_layer[L_end]) - Wcond_T * (1+math.cos(2 * Thetab_layer[L_end])) / 2 / math.sin((2 * Thetab_layer[L_end]))
    theta_conn_bend = connect_bend_theta_solve(L_conn_str,L_conn_bend_A,R_height_bend)
    ##### theta_conn_bend is the 
    if theta_conn_bend == 0:
        delta_length_conn_bend = delta_length_Rbend
    else: 
        delta_length_conn_bend = 2 *  L_conn_bend_A + L_conn_str * (1-1/math.sin(theta_conn_bend)) + 2 * R_height_bend * (theta_conn_bend - math.tan(theta_conn_bend / 2))
    # delta_length_conn_bend = 0
    ##### Calculate the new L_str 
    New_L_str = L_str + R_side_bend * math.tan(beta)
    New_L_weld = L_weld + R_side_bend * math.tan(beta)
    delta_L_str = R_side_bend * math.tan(beta)
    EndW_Length_insert = Length1 + Length2 + Length3 + Length4 + Length5 - delta_length_Rbend * 2 - delta_length_conn_bend + delta_L_str * 2
    #### Compared to the insert side, the weld side does not have the radial connection part (Length3), while it has the L-weld * 2.

    EndW_Length_weld = Length1 + Length2 + Length4 + Length5 + L_weld * 2 - delta_length_Rbend * 4 + delta_L_str * 4
    EndW_Length_total = EndW_Length_insert + EndW_Length_weld
    EndW_Height_insert = Height_end + New_L_str + H_cond_T / 2
    EndW_Height_weld = Height_end + New_L_str + New_L_weld
    Length_data = [L_str,Height_end,EndW_Height_insert,EndW_Length_insert,EndW_Height_weld,EndW_Length_weld,EndW_Length_total,New_L_str,New_L_weld]
    return (Length_data)

def parallel_impedance(impedances):
    if not impedances:
        return float('inf')
    inverse_total = sum(1.0 / Z for Z in impedances if Z)
    return 1.0 / inverse_total if inverse_total else float('inf')

def calculate_end_parameters_by_results(Winding_Para,Stator_Para,Inslot_Para,EW_info,results):
    num_slots = Winding_Para.num_slots
    num_poles = Winding_Para.num_poles
    num_layers = Winding_Para.num_layers
    num_phases = Winding_Para.num_phases
    ab = Winding_Para.ab
    num_slot_per_pole = num_slots / num_poles
    beta = math.pi / num_slot_per_pole
    q = num_slots / num_poles / num_phases  # assuming q represents the slots per pole per phase
    kd = math.sin(q * beta / 2) / (q * math.sin(beta / 2))
    u0 = 4 * math.pi / 10000000
    Total_turns_per_phase = int(num_slots * num_layers / num_phases / 2)
    Cond_Width = Inslot_Para.Cond_Width
    Cond_Height = Inslot_Para.Cond_Height
    Cond_Radi = Inslot_Para.Cond_Radi
    Area_Cond = Cond_Width * Cond_Height - (4-math.pi)*Cond_Radi*Cond_Radi
    Curesistivity = Inslot_Para.Curesistivity_Eff
    branch_resistances = []
    branch_inductances = []
    total_end_winding_length = 0
    
    # Process each branch
    weld_span_list = results[-1]["weld_span_list"]
    for result in results:
        if result['n_branch'] != 'All' and result['n_branch'] <= ab:   ### Only get single Phase data
            
            branch_end_winding_length = 0
            branch_inductance = 0
            Avg_Lew = 0
            Avg_kw = 0
            pin_count = 0
            
            for pin_shape, count in result['pin_shapes'].items():
                L_start, L_end, S_span_insert = pin_shape
                L_start, L_end = min(L_start, L_end), max(L_start, L_end)  #### ensure L_end > L_start
                S_span_weld_A =  weld_span_list[L_start]
                S_span_weld_B =  weld_span_list[L_end]
                L_str,Height_end,EndW_Height_insert,EndW_Length_insert,EndW_Height_weld,EndW_Length_weld,EndW_Length_total,New_L_str = calculate_end_winding_length(L_start,L_end,S_span_insert,S_span_weld_A,S_span_weld_B,Winding_Para,Stator_Para,Inslot_Para,EW_info)
                pin_length = EndW_Length_total * count
                #### Lew used for pin inductance calculation 
                Lew = New_L_str + Height_end / 2  #### Update the Lstr.
                Avg_Lew += Lew*count
                pin_count += count
                S_span_delta = S_span_insert - num_slot_per_pole
                alpha = abs(S_span_delta * math.pi / num_slots * num_poles)
                kp = abs(math.cos(alpha / 2))
                kw = kp * kd
                Avg_kw += kw*count
                pin_inductance = kw ** 2 * 12 * 2.4 * u0 * Total_turns_per_phase / num_slots * Lew / 1000 * count
                branch_end_winding_length += pin_length
                branch_inductance += pin_inductance
            total_end_winding_length += branch_end_winding_length
            branch_resistance = (branch_end_winding_length / Area_Cond * Curesistivity * 1000)
            branch_resistances.append(branch_resistance)
            branch_inductances.append(branch_inductance)
    phase_resistance = parallel_impedance(branch_resistances)
    phase_inductance = parallel_impedance(branch_inductances)
    return phase_resistance, phase_inductance, total_end_winding_length



