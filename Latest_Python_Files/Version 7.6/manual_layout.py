import numpy as np
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import cond_info_operation as cio
import csv_operation as csvo
import get_winding_pattern as gw
from collections import namedtuple
import copy
from tkinter import ttk

class SlotGame(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Hairpin Winding Layout Manual Design")
        self.geometry("1200x800")  # Adjusted size to accommodate labels and more slots
        self.history = []  # To track history of actions for undo feature
        
        # 创建 Main Para 框架
        self.main_para_frame = ttk.LabelFrame(self, text="Main Para", padding="10")
        self.main_para_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nw")
        
        
        # 创建 Layout Para 框架
        self.layout_para_frame = ttk.LabelFrame(self, text="Layout Para", padding="10")
        self.layout_para_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nw")
        
        # 创建 Button 框架
        self.button_frame = ttk.LabelFrame(self, text="Actions", padding="10")
        self.button_frame.grid(row=1, column=1, padx=10, pady=10, sticky="nw")
        
        # 创建 Output 框架
        self.output_frame = ttk.LabelFrame(self, text="Outputs", padding="10")
        self.output_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nw")
        
        
        # 创建 branch info 框架
        self.branch_frame = ttk.LabelFrame(self, text="Outputs", padding="10")
        self.branch_frame.grid(row=0, column=2, padx=10, pady=10, sticky="nw")
        self.q = 2
        self.m = 3
        self.num_poles = 4
        self.num_layers = 4
        self.naa = 2
        self.num_slots = int(self.q * self.m * self.num_poles)
        self.create_input_fields()
        self.create_widgets()
        # Initialize default values

        self.branch_colors = self.setup_branch_colors("rainbow", 8, alpha = 0.5)

        self.phase_shift = 1
        self.psl = 1
        self.branch_index = 0
        self.full_symmetry = 'N'
        self.num_slots = int(self.q*self.m*self.num_poles)
        self.group_size = int(self.num_slots * self.num_layers / self.naa / self.m)
        self.remaining_in_branch = self.group_size
        self.status_labels = []  # To hold a status label for each branch
        self.set_defaults()  # Call method to set defaults
        self.branch_info_history = []
        self.branch_info = [{} for _ in range(self.naa)]
        
        # self.initialize_branch_info()  # Initialize branch info
        self.current_number = 1
        self.current_position = None
        self.remaining_in_branch = 0
        self.buttons = []  # Initialize buttons array
        self.FL_connection = 0
        self.last_position = (0,0)
        self.positions = []
        self.cond_info_history = []
        # 在窗口底部添加注释文本
        self.bottom_label = tk.Label(self, text="*:Winding Pattern 1: BWP, 2: UWP, 3: SSP, 4: SLP, 5: TSP", anchor="w",fg='blue')
        self.bottom_label.grid(row=98, column=0, columnspan=4, sticky="ew", padx=5, pady=5)
        # 在窗口底部添加注释文本
        self.bottom_label = tk.Label(self, text="**:First-last layer connection with pin, N: disable Y: able", anchor="w",fg='blue')
        self.bottom_label.grid(row=99, column=0, columnspan=4, sticky="ew", padx=5, pady=5)
        # # Create main layout frames
        # self.left_frame = tk.Frame(self)
        # self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def create_input_fields(self):
        padx = 5
        pady = 5
        width = 5
        
        # 在 Main Para 框架中创建标签和输入框
        self.m_label = ttk.Label(self.main_para_frame, text="Num Phases (m):")
        self.m_label.grid(row=0, column=0, padx=padx, pady=pady, sticky="w")
        self.m_entry = ttk.Entry(self.main_para_frame, width=width, justify='center')
        self.m_entry.insert(0, "3")  # 默认值
        self.m_entry.grid(row=0, column=1, padx=padx, pady=pady)
        
        self.num_poles_label = ttk.Label(self.main_para_frame, text="Num Poles (p):")
        self.num_poles_label.grid(row=1, column=0, padx=padx, pady=pady, sticky="w")
        self.num_poles_entry = ttk.Entry(self.main_para_frame, width=width, justify='center')
        self.num_poles_entry.insert(0, "2")  # 默认值
        self.num_poles_entry.grid(row=1, column=1, padx=padx, pady=pady)

        self.num_layers_label = ttk.Label(self.main_para_frame, text="Num Layers:")
        self.num_layers_label.grid(row=2, column=0, padx=padx, pady=pady, sticky="w")
        self.num_layers_entry = ttk.Entry(self.main_para_frame, width=width, justify='center')
        self.num_layers_entry.insert(0, "2")  # 默认值
        self.num_layers_entry.grid(row=2, column=1, padx=padx, pady=pady)

        self.naa_label = ttk.Label(self.main_para_frame, text="Branches (Naa):")
        self.naa_label.grid(row=3, column=0, padx=padx, pady=pady, sticky="w")
        self.naa_entry = ttk.Entry(self.main_para_frame, width=width, justify='center')
        self.naa_entry.insert(0, "1")  # 默认值
        self.naa_entry.grid(row=3, column=1, padx=padx, pady=pady)

        self.q_label = ttk.Label(self.main_para_frame, text="SPPP (q):")
        self.q_label.grid(row=4, column=0, padx=padx, pady=pady, sticky="w")
        self.q_entry = ttk.Entry(self.main_para_frame, width=width, justify='center')
        self.q_entry.insert(0, "1")  # 默认值
        self.q_entry.grid(row=4, column=1, padx=padx, pady=pady)
        
        self.num_slots_label = ttk.Label(self.main_para_frame, text="Num Slots:")
        self.num_slots_label.grid(row=5, column=0, padx=padx, pady=pady, sticky="w")
        self.num_slots_entry = ttk.Entry(self.main_para_frame, width=width, justify='center')
        self.num_slots_entry.insert(0, str(self.num_slots))  # 默认值
        self.num_slots_entry.grid(row=5, column=1, padx=padx, pady=pady)

        # 在 Layout Para 框架中创建标签和输入框
        self.phase_shift_label = tk.Label(self.layout_para_frame, text="Phase Shift:")
        self.phase_shift_label.grid(row=0, column=0, padx=padx, pady=pady)
        self.phase_shift_entry = tk.Entry(self.layout_para_frame, width=width,justify='center')
        self.phase_shift_entry.insert(0, "0")  # Default value
        self.phase_shift_entry.grid(row=0, column=1, padx=padx, pady=pady)
        
        self.psl_label = tk.Label(self.layout_para_frame, text="Phase Shift Layer (PSL):")
        self.psl_label.grid(row=1, column=0, padx=padx, pady=pady)
        self.psl_entry = tk.Entry(self.layout_para_frame, width=width,justify='center')
        self.psl_entry.insert(0, "0")  # Default value
        self.psl_entry.grid(row=1, column=1, padx=padx, pady=pady)
        
        self.radial_shift_label = tk.Label(self.layout_para_frame, text="Radial Shift:")
        self.radial_shift_label.grid(row=2, column=0, padx=padx, pady=pady)
        self.radial_shift_entry = tk.Entry(self.layout_para_frame, width=width,justify='center')
        self.radial_shift_entry.insert(0, "0")  # Default value
        self.radial_shift_entry.grid(row=2, column=1, padx=padx, pady=pady)
        
        # Fields for Winding Pattern
        self.winding_pattern_label = tk.Label(self.layout_para_frame, text="Winding Pattern*:")
        self.winding_pattern_label.grid(row=3, column=0, padx=padx, pady=pady)
        self.winding_pattern_entry = tk.Entry(self.layout_para_frame, width=width, justify='center')
        self.winding_pattern_entry.insert(0, "0")  # Default or initial value
        self.winding_pattern_entry.grid(row=3, column=1, padx=padx, pady=pady)
        
        self.full_symmetry_label = tk.Label(self.layout_para_frame, text="Symmetry design:")
        self.full_symmetry_label.grid(row=4, column=0, padx=padx, pady=pady)
        
        self.symmetry_frame = tk.Frame(self.layout_para_frame)
        self.symmetry_frame.grid(row=4, column=1, padx=padx, pady=pady, sticky="w")
        
        self.symmetry_var = tk.StringVar(value="Y")
        self.symmetry_yes = tk.Radiobutton(self.symmetry_frame, text="Y", variable=self.symmetry_var, value="Y")
        self.symmetry_no = tk.Radiobutton(self.symmetry_frame, text="N", variable=self.symmetry_var, value="N")
        self.symmetry_yes.pack(side=tk.LEFT)
        self.symmetry_no.pack(side=tk.LEFT)
        
        # New fields for First-last Layer Connection
        self.FL_connection_label = tk.Label(self.layout_para_frame, text="First-last Layer Conn**:")
        self.FL_connection_label.grid(row=5, column=0, padx=padx, pady=pady)
        
        self.FL_connection_entry = tk.Entry(self.layout_para_frame, width=width, justify='center')
        self.FL_connection_entry.insert(0, "0")  # Default or initial value
        self.FL_connection_entry.grid(row=5, column=1, padx=padx, pady=pady)
        
        self.FLC_frame = tk.Frame(self.layout_para_frame)
        self.FLC_frame.grid(row=5, column=1, padx=padx, pady=pady, sticky="w")
        
        self.FLC_var = tk.StringVar(value="Y")
        self.FLC_yes = tk.Radiobutton(self.FLC_frame, text="Y", variable=self.FLC_var, value="Y")
        self.FLC_no = tk.Radiobutton(self.FLC_frame, text="N", variable=self.FLC_var, value="N")
        self.FLC_yes.pack(side=tk.LEFT)
        self.FLC_no.pack(side=tk.LEFT)
        
        self.iws_label = tk.Label(self.layout_para_frame, text="In from weld side:")
        self.iws_label.grid(row=6, column=0, padx=padx, pady=pady)
        self.iws_entry = tk.Entry(self.layout_para_frame, width=width,justify='center')
        self.iws_entry.insert(0, "0")  # Default value
        self.iws_entry.grid(row=6, column=1, padx=padx, pady=pady)
        

    def create_widgets(self):
        padx = 5
        pady = 5
        Row_Widgets = 6
        # Start Button
        self.start_button = tk.Button(self.button_frame, text="Start", command=self.start_game)
        self.start_button.grid(row=Row_Widgets, column=0, columnspan=1, padx=padx, pady=pady)
        
        # Previous Button
        self.previous_button = tk.Button(self.button_frame, text="Undo", command=self.undo_last_action)
        self.previous_button.grid(row=Row_Widgets, column=1, columnspan=1, padx=padx, pady=pady)
        
        # Finish Button
        self.finish_button = tk.Button(self.button_frame, text="Finish", command=self.close_window)
        self.finish_button.grid(row=Row_Widgets, column=2, columnspan=1, padx=padx, pady=pady)
        
        # # Status Label
        # self.status_label = tk.Label(self, text="")
        # self.status_label.grid(row=5, column=0, columnspan=6, padx=padx, pady=pady)
        
        Row_output = 90
        self.output_path_label = tk.Label(self.output_frame, text="Path:")
        self.output_path_label.grid(row= Row_output, column=0, padx=padx, pady=pady)
        self.output_path_entry = tk.Entry(self.output_frame, width=15, justify='center')
        self.output_path_entry.insert(0, "D:\\")  # Default or initial value
        self.output_path_entry.grid(row= Row_output, column=1, padx=padx, pady=pady)
        
        self.output_button = tk.Button(self.output_frame, text="Output", command=self.output_csv)
        self.output_button.grid(row= Row_output, column=2, columnspan=1, padx=padx, pady=pady)
        
    def output_csv(self):
        db_conductor_id = self.get_db_conductor_id_with_cond_info(Cond_info)
        file_path = self.output_path_entry.get()  # Get the file path from the entry widget
        csvo.output_branches_to_csv(self.Winding_Para,db_conductor_id,file_path)
    
    def open_layout_window(self):
        self.layout_window = tk.Toplevel(self)
        self.layout_window.title("Layout")
        self.layout_window.geometry("1200x800")
        self.create_slots_grid()
        self.setup_branch_status()
        self.display_branch_info()
        
    def close_window(self):
        start_conductor_ids = cio.get_start_conductor_id_with_cond_info(Cond_info)
        db_conductor_id = self.get_db_conductor_id_with_cond_info(Cond_info)
        self.result = start_conductor_ids, db_conductor_id,Cond_info  # Set the result before closing
        self.output_csv()
        self.destroy()
    
    def get_result(self):
        return self.result
    
    def undo_last_action(self):
        self.undo_place_number()
        
    def setup_branch_colors(self, cmap_name, n_colors, alpha=1.0):
        """
        Setup branch colors by generating n_colors from a colormap and converting them to hexadecimal format.
        """
        cmap = plt.get_cmap(cmap_name)  # Get the colormap
        colors = [cmap(i / n_colors) for i in range(n_colors)]  # Generate colors from colormap
        adjusted_colors = [
            (alpha * c[0] + (1 - alpha) * 1, alpha * c[1] + (1 - alpha) * 1, alpha * c[2] + (1 - alpha) * 1)
            for c in colors
        ]
        hex_colors = [mcolors.to_hex(color[:3]) for color in adjusted_colors]
        return hex_colors
    
    def initialize_branch_info(self):
            # Initialize branch info data structure
            self.branch_info = [
                {f'Phasor {p+1} Layer {l+1}': {'count': 0, 'left': int(self.num_poles / self.naa)}
                 for p in range(self.q) for l in range(self.num_layers)}
                for _ in range(self.naa)
            ]
            self.branch_info_history.append(self.branch_info)
            self.display_branch_info()
            self.setup_branch_status()  # Set up status labels for each branch
            
    def setup_branch_status(self):
        try:
            for label in self.status_labels:
                label.destroy()
        except AttributeError:
            self.status_labels = []
        num_digits = len(str(self.group_size))
        row_offset =  self.num_layers + 4  # Example initial offset for the status labels
        # Check if any buttons have been clicked using the helper method
        if self.branch_index == 0 and self.remaining_in_branch == self.group_size:
            # Initialize labels only if no slots have been filled
            self.remains = [self.group_size for i in range(self.naa)]
        else:
            self.remains[self.branch_index] = self.remaining_in_branch
        for i in range(self.naa):
            formatted_remains = f"{self.remains[i]:0{num_digits}d}"  # Format with leading zeros
            label = tk.Label(self, text=f"Branch {i+1}: {formatted_remains} conductors left")
            if self.remains[i] == 0:
                label.config(fg="green")
            else:
                label.config(fg="black")
            label.grid(row=row_offset, column=i, padx=2, pady=1, sticky="w")
            self.status_labels.append(label)
            
    def display_branch_info(self):
        # Clear existing labels if anyself.grid_propagate(False)  # Prevent resizing in grid
        try:
            for label in self.branch_labels:
                label.destroy()
        except AttributeError:
            self.branch_labels = []
            # Create new labels based on branch_info
        row_offset = self.num_layers + 6
        for branch_index, branch in enumerate(self.branch_info):
            for i, (key, value) in enumerate(branch.items()):
                label_text = f"{key}: {value['count']} ({value['left']} left)"
                label = tk.Label(self, text=label_text)
                if value['left'] == 0:
                    label.config(fg="green")
                else:
                    label.config(fg="black")
                label.grid(row=row_offset + i, column=branch_index, padx=2, pady=1, sticky="w")
                self.branch_labels.append(label)

                
    def set_defaults(self):
        self.num_poles_entry.delete(0, tk.END)
        self.num_poles_entry.insert(0, str(self.num_poles))
        
        self.num_layers_entry.delete(0, tk.END)
        self.num_layers_entry.insert(0, str(self.num_layers))
        
        self.naa_entry.delete(0, tk.END)
        self.naa_entry.insert(0, str(self.naa))
        
        self.q_entry.delete(0, tk.END)
        self.q_entry.insert(0, str(self.q))
        
        self.m_entry.delete(0, tk.END)
        self.m_entry.insert(0, str(self.m))
        
        self.phase_shift_entry.delete(0, tk.END)
        self.phase_shift_entry.insert(0, str(self.phase_shift))
        
        self.psl_entry.delete(0, tk.END)
        self.psl_entry.insert(0, str(self.psl))
        

        
        ## New Fields for TP 
        
    def test_symmetry_possible(self):
        # Retrieve the value from symmetry_var, which should be tied to the radio buttons for Y and N
        full_symmetry = self.symmetry_var.get()
        if full_symmetry == "Y" and self.num_poles % self.naa != 0:
        # Check if full symmetry is required and num_poles is not divisible by naa
            messagebox.showerror("Symmetry Error", "Full symmetry is selected but the number of poles is not divisible by the number of parallel branches (Naa).")
            return False
        return True

    def start_game(self):
        try:
            self.num_poles = int(self.num_poles_entry.get())
            self.num_layers = int(self.num_layers_entry.get())
            self.naa = int(self.naa_entry.get())
            self.q = int(self.q_entry.get())
            self.m = int(self.m_entry.get())
            self.phase_shift = int(self.phase_shift_entry.get())
            self.psl = int(self.psl_entry.get())
            self.full_symmetry = self.symmetry_var.get()
            self.WindingPattern = int(self.winding_pattern_entry.get())
            self.FL_connection = self.FLC_var.get()
            
        except ValueError:
            messagebox.showerror("Input Error", "Please enter valid numbers for all inputs.")
            return
        # After retrieving inputs, check if symmetry conditions are met
        if not self.test_symmetry_possible():
            return  # Stop the game setup if full symmetry selected but fail due to p/Naa unavaliable
        
        self.num_slots = self.q * self.m * self.num_poles
        self.num_slots_entry.delete(0, tk.END)  # Clear the existing text
        self.num_slots_entry.insert(0, str(self.num_slots))  # Insert the new text
        self.group_size = int(self.num_slots * self.num_layers / self.naa / self.m)
        self.slots = np.zeros((self.num_layers, self.num_slots))
        self.current_number = 1
        self.current_position = None
        self.branch_index = 0
        self.remaining_in_branch = self.group_size
        WindingParaGroup = namedtuple('WindingPara', ['q', 'num_poles', 'num_layers', 'num_phases', 'num_slots', 'ab'])
        self.Winding_Para = WindingParaGroup(self.q, self.num_poles, self.num_layers, self.m, self.num_slots, self.naa)
        self.clear_slots_grid()
        self.buttons = [[None for _ in range(self.num_slots)] for _ in range(self.num_layers)]  # Initialize buttons array
        self.initialize_branch_info()
        self.create_slots_grid()
        self.setup_branch_status()
        self.display_branch_info()
        ##### If Winding Pattern is selected 
        if self.WindingPattern != 0:
            Winding_Pattern_names = gw.get_available_patterns()
            if self.WindingPattern < 1 or self.WindingPattern > len(Winding_Pattern_names):
                raise ValueError(f"unsupported winding pattern number {self.WindingPattern}.")
            pattern_name = gw.normalize_pattern_name(Winding_Pattern_names[self.WindingPattern-1], allow_extra=False)
            tp_type = 'regular' 
            tp_times = self.q - 1 ### default tp_times
            tp_interval = 2
            uni_tp = 0
            pltp_fl = 0
            pltp_ll = 0
            jltp = 0
            jld = 1
            TP_infoGroup = namedtuple('TP_info', ['tp_type','tp_interval','tp_times','uni_tp','pltp_fl','pltp_ll','jltp','jld'])
            TP_info = TP_infoGroup(tp_type,tp_interval,tp_times,uni_tp,pltp_fl,pltp_ll,jltp,jld)
            in_out_connection = 0
            inlet_from_weld_side = 1 if pattern_name in ('ZPP', 'LPP') else 0
            phase_shift_pattern = 'Normal'
            phase_shift = 1
            PSL = 1
            radial_shift = 0
            Single_Phase_Draw = 1 # 1: draw line only for the first phase, 0: draw line for all the phases
            CW = 0
            phase_shift_list = gw.get_phase_shift_list(self.Winding_Para, phase_shift_pattern, phase_shift, PSL)
            LayoutParaGroup = namedtuple('LayoutPara', ['inlet_from_weld_side', 'phase_shift_pattern', 'phase_shift', 'PSL', 'radial_shift','Single_Phase_Draw','CW','in_out_connection','pattern_name','phase_shift_list'])
            Layout_Para = LayoutParaGroup(inlet_from_weld_side, phase_shift_pattern, phase_shift, PSL, radial_shift,Single_Phase_Draw,CW,in_out_connection,pattern_name,phase_shift_list)
            phase_A_id = gw.get_phaseA_winding_layout(pattern_name,TP_info,self.Winding_Para,Layout_Para)
            for branch,conductors in phase_A_id:
                for cond in conductors:
                    slot,layer,phasor = cond
                    # re_slot = self.re_slot_shift(slot,layer)
                    self.place_number((layer, slot))
        
    def clear_slots_grid(self):
        for row in self.buttons:
            for btn in row:
                if btn is not None:
                    btn.destroy()  # This destroys the button widget
        self.buttons = []  # Reset the list of button references
    
    def slot_shift(self,slot,layer):
        modi_slot = slot
        if self.q > 1 and self.phase_shift != 0 and self.psl > 0:
            if layer // self.psl % 2 == 1:
                modi_slot = (slot + self.phase_shift + self.num_slots) % self.num_slots
        return modi_slot
    
    def re_slot_shift(self,slot,layer):
        modi_slot = slot
        if self.q > 1 and self.phase_shift != 0 and self.psl > 0:
            if layer // self.psl % 2 == 1:
                modi_slot = (slot - self.phase_shift + self.num_slots) % self.num_slots
        return modi_slot
    
    def create_slots_grid(self):
        global Cond_info 
        Cond_info = []   # 0. slot, 1. layer, 2. phase, 3. branch, 4. cond_index 5. phasor 6. pole_index
        padx = 5
        pady = 5
        start_column = 3
        start_row = 0
        phase_colors = ["palegreen","lightcoral", "deepskyblue", "bisque", "thistle", "honeydew"]  # Colors for different phases
        phase_labels = [chr(65 + i) for i in range(self.m)]
        
        self.cond_frame = tk.Frame(self)
        self.cond_frame.grid(row=start_row, column=start_column, columnspan=12, rowspan=6, padx=padx, pady=pady, sticky="nsew")
        
        # Create frames around each phase region
        for phase in range(self.m):
            for pole in range(self.num_poles):
                phase_region_start = self.m * self.q * pole + self.q * phase + start_column + 1
                # phase_region_end = self.q * (phase + 1) + start_column
                phase_frame = tk.Frame(self.cond_frame, bd=2, relief="solid")
                phase_frame.grid(row=start_row, column=phase_region_start, rowspan= 1, columnspan=self.q, padx=1, pady=1, sticky="nsew")
                phase_index = phase_labels[phase]
                phase_color = phase_colors[phase] 
                phase_label = tk.Label(phase_frame, text=f"{phase_index}", anchor="center",bg=phase_color)
                phase_label.grid(row=0, column=0, sticky="nsew")
                phase_frame.grid_rowconfigure(0, weight=1)
                phase_frame.grid_columnconfigure(0, weight=1)
        
        # Display slot and layer indexes outside the button grid
        for j in range(self.num_slots):
            slot_label = tk.Label(self.cond_frame, text=f"{j + 1}")
            slot_label.grid(row=start_row+1, column=j+start_column + 1)
        
        # Display slot title
        slot_title = tk.Label(self.cond_frame, text='Slot')
        slot_title.grid(row=start_row+1, column=start_column)
        
        # Display phase
        phase_title = tk.Label(self.cond_frame, text='Phase')
        phase_title.grid(row=start_row, column=start_column)
        
        grid_width = 3 if self.num_slots < 36 else 2
        # Display layer labels on the left of the grid
        for layer in range(self.num_layers):
            layer_label = tk.Label(self.cond_frame, text=f"Layer {layer + 1}")
            layer_label.grid(row=layer + start_row + 2, column=start_column)
            for slot in range(self.num_slots):
                origin_slot = self.re_slot_shift(slot,layer)
                phase_index = (origin_slot % (self.q * self.m)) // self.q
                pole_index = int(origin_slot / (self.q * self.m))
                btn_text = ""  # Start with empty button text
                btn = tk.Button(self.cond_frame, text=btn_text, width=grid_width, height=1, padx=0, pady=0, bg=phase_colors[phase_index % len(phase_colors)], command=lambda x=layer, y=slot: self.on_slot_click(x, y))
                btn.grid(row=layer + start_row + 2, column=slot + start_column + 1, sticky="nsew")
                Cond_info.append((slot, layer, phase_index, -1, -1, -1,pole_index))
                self.buttons[layer][slot] = btn
        
        end_row = start_row + 2 + self.num_layers 
        # Display Pole
        pole_title = tk.Label(self.cond_frame, text='Pole')
        pole_title.grid(row=end_row, column=start_column)
        # Create frames around each pole region
        for pole in range(self.num_poles):
            pole_region_start = self.m * self.q * pole + start_column + 1
            pole_region_end = self.m * self.q * (pole + 1) + start_column
            pole_frame = tk.Frame(self.cond_frame, bd=2, relief="solid")
            pole_frame.grid(row=end_row, column=pole_region_start, rowspan=1, columnspan=self.m * self.q, padx=1, pady=1, sticky="nsew")   
            pole_index = 'S' if pole % 2 == 1 else 'N'
            # pole_color = 'lightblue' if pole_index == 'N' else 'mistyrose'
            # pole_index_position = pole_region_start + (self.m * self.q // 2) - 1
            pole_label = tk.Label(pole_frame, text=f"{pole_index}",anchor="center")
            pole_label.grid(row=0, column=0, sticky="nsew")
            pole_frame.grid_rowconfigure(0, weight=1)
            pole_frame.grid_columnconfigure(0, weight=1)
            pole_frame.grid(row=end_row, column=pole_region_start, rowspan=1, columnspan=self.m * self.q, padx=1, pady=1, sticky="nsew")  
            # pole_label.grid(row=self.num_layers + 1, column=pole_index_position - pole_region_start, columnspan=self.m * self.q, padx=padx, pady=pady)

                
    def on_slot_click(self, x, y):
        modi_slot = y
        layer = x
        origin_slot = self.re_slot_shift(modi_slot, layer)
        if origin_slot % (self.m * self.q) < self.q:  #### If at the first phase 
            self.place_number((x, y))
            # print('self.last_position',self.last_position)
        else:
             messagebox.showwarning("Invalid Move", "This is not a position for phase A.")
        

    def update_cond_info(self,slot,layer,branch_id,cond_index):
        global Cond_info
        origin_slot = self.re_slot_shift(slot,layer)
        phasor_index = (origin_slot) % self.q
        # 0. slot, 1. layer, 2. phase, 3. branch_id, 4. cond_index 5. phasor 6. pole_index
        for ci in Cond_info:
            for i in range(self.m):
                s = slot+self.q*i
                if ci[0] == s and ci[1] == layer:
                    new_branch_id = branch_id + self.naa*i
                    ci_list = list(ci)
                    ci_list[3] = new_branch_id
                    ci_list[4] = cond_index
                    ci_list[5] = phasor_index
                    Cond_info[Cond_info.index(ci)] = tuple(ci_list)
                    break
        db_conductor_id = self.get_db_conductor_id_with_cond_info(Cond_info)
        results = self.analyze_database(db_conductor_id)
        self.print_pin_info(results)
        # if self.branch_index == self.naa - 1 and self.remaining_in_branch == 0:
        #     self.print_pin_info(results)
        return Cond_info
    
    def get_db_conductor_id_with_cond_info(self,cond_info):
        db_conductor_id = {}
        for ci in cond_info:
            # if ci[2] == 0 and ci[3] > -1:  ### Only first phase Only filled positions
            if ci[3] > -1:  ### Only filled positions
                slot = ci[0]
                layer = ci[1]
                phase = ci[2]
                branch = ci[3]
                cond_index = ci[4]
                phasor = ci[5] 
                # Calculate the branch_id
                branch_id = phase * self.q + branch
                # Create the conductor tuple
                conductor = (slot, layer, phasor)
                # Add the conductor to the appropriate branch_id in db_conductor_id
                if branch_id not in db_conductor_id:
                    db_conductor_id[branch_id] = []
                db_conductor_id[branch_id].append((cond_index, conductor))
            # Sort the conductors by their index for each branch_id
        for branch_id in db_conductor_id:
            db_conductor_id[branch_id].sort()
        # Remove the indices, keeping only the conductor information
        for branch_id in db_conductor_id:
            db_conductor_id[branch_id] = [conductor for index, conductor in db_conductor_id[branch_id]]
        # Convert to the expected list of lists format
        db_conductor_id_list = [[branch_id+1, conductors] for branch_id, conductors in sorted(db_conductor_id.items())]
        return db_conductor_id_list
    
    def analyze_database(self, database, odd=True):
        in_out_connection = 0
        inlet_from_weld_side = 0
        results = []
        all_pin_shapes = {}  # 修改为字典，用于存储所有 branch 的 pin shapes 与其计数
        total_slot_distance_all = 0
        conductor_count_all = 0
        for branch_info in database:
            n_branch, group_conductors_id = branch_info
            pin_shapes = {}
            total_slot_distance = 0
            conductor_count = 0
            # 修改循环以包括从第一个到最后一个导体的连接
            if in_out_connection == 1:
                i = len(group_conductors_id) - 1 # 当 i 是最后一个元素时，与第一个元素形成闭环
                a, b = sorted([group_conductors_id[i][1], group_conductors_id[0][1]])
                y = abs(group_conductors_id[i][0] - group_conductors_id[0][0]) % self.num_slots
                side = int(1-inlet_from_weld_side)
                y = min(y, self.num_slots - y)

                if i % 2 == side:  # 检查 i 是否为奇数
                    pin_key = (a, b, y)
                    if pin_key in pin_shapes:
                        pin_shapes[pin_key] += 1
                    else:
                        pin_shapes[pin_key] = 1
                total_slot_distance += y
                conductor_count += 1
            for i in range(len(group_conductors_id)-1):
                a, b = sorted([group_conductors_id[i][1], group_conductors_id[i+1][1]])
                y = abs(group_conductors_id[i][0] - group_conductors_id[i+1][0]) % self.num_slots
                side = int(1-inlet_from_weld_side)
                y = min(y, self.num_slots - y)
                if i % 2 == side:  # 检查 i 是否为奇数
                    pin_key = (a, b, y)
                    if pin_key in pin_shapes:
                        pin_shapes[pin_key] += 1
                    else:
                        pin_shapes[pin_key] = 1
                total_slot_distance += y
                conductor_count += 1
            num_pin_shapes = len(pin_shapes)
            conductor_info = []
            for phasor_layer in set([(c[2], c[1]) for c in group_conductors_id]):
                num_conductor = len([c for c in group_conductors_id if c[2] == phasor_layer[0] and c[1] == phasor_layer[1]])
                conductor_info.append((phasor_layer[0], phasor_layer[1], num_conductor))

            for pin_shape, count in pin_shapes.items():
                all_pin_shapes[pin_shape] = all_pin_shapes.get(pin_shape, 0) + count

            total_slot_distance_all += total_slot_distance
            conductor_count_all += conductor_count
            average_slot_distance = round(total_slot_distance_all / conductor_count_all, 4) if conductor_count > 0 else 0
            results.append({'n_branch': n_branch, 'num_pin_shapes': num_pin_shapes, 'conductor_info': conductor_info, 'pin_shapes': pin_shapes, 'average_slot_distance': average_slot_distance, 'total_slot_distance': total_slot_distance,'total_conductors':conductor_count})
        average_slot_distance_all = round(total_slot_distance_all / conductor_count_all, 4) if conductor_count_all > 0 else 0
        results.append({'n_branch': 'All', 'num_pin_shapes': len(all_pin_shapes), 'conductor_info': [], 'pin_shapes': all_pin_shapes, 'average_slot_distance': average_slot_distance_all, 'total_slot_distance': total_slot_distance_all,'total_conductors':conductor_count_all})
        return results
         

    def print_pin_info(self, results):
        try:
            for label in self.pin_labels:
                label.destroy()
        except AttributeError:
            self.pin_labels = []
        
         # Create new labels based on results
        result = results[-1]
        sorted_pin_shapes = sorted(list(result['pin_shapes'].items()), key=lambda x: x[0])
        
        # Update the GUI to display pin shapes
        start_row = self.num_layers + 4  # Adjust the starting row as needed
        start_col = self.naa + 1
        row = start_row
        label_text = f'\t\tPin shapes:   {len(sorted_pin_shapes)}'
        label = tk.Label(self, text=label_text)
        label.grid(row=row, column=start_col, padx=2, pady=1, sticky="w")
        self.pin_labels.append(label) 
        for pin_shape, count in sorted_pin_shapes:
            row += 1 
            if pin_shape[0] == pin_shape[1]:
                pintype = 'Parallel'
            elif abs(pin_shape[0]-pin_shape[1]) == 1:
                pintype = 'Adjacent'
            elif abs(pin_shape[0]-pin_shape[1]) == self.num_layers - 1:
                pintype = 'First-last'
            else:
                pintype = 'Others'
            if pin_shape[2] == self.m*self.q:
                Pitchtype = 'Full'
            elif pin_shape[2] < self.m*self.q:
                Pitchtype = 'Short'
            else:
                Pitchtype = 'Long'
            label_text = f'\t\t[Layer] {pin_shape[0]+1},  [Layer] {pin_shape[1]+1},  [y]: {pin_shape[2]},  [num]: {count},  [Type]: {pintype},  [Pitch]: {Pitchtype}'
            label = tk.Label(self, text=label_text)
            label.grid(row=row, column=start_col, padx=2, pady=1, sticky="w")
            self.pin_labels.append(label) 

            
    def place_number(self, position):
        global Cond_info
        # Append the current state to history before making changes
        self.positions.append(position)
        layer, slot = position
        custom_font = tkfont.Font(family="Helvetica", size=10, weight="bold")
        branch_color = self.branch_colors[self.branch_index % len(self.branch_colors)]
        self.slots[layer][slot] = self.current_number
        self.buttons[layer][slot].config(text=str(self.current_number), state="disabled", bg = branch_color, fg='#ffffff', font = custom_font,padx=0, pady=0)  # Set vertical padding to zero
        self.current_position = self.positions[-1]
        cond_index = self.current_number - 1
        self.current_number += 1
        self.remaining_in_branch -= 1
        self.update_cond_info(slot,layer,self.branch_index,cond_index)
        self.update_branch_info(*position)  # Update branch info with new placement
        self.setup_branch_status()  # Update the branch status
        if self.remaining_in_branch == 0:
            self.branch_index += 1
            self.current_number = 1 ##re_initialize current_number
            self.remaining_in_branch = self.group_size
        self.highlight_valid_positions()
        self.print_pin_info(self.analyze_database(self.get_db_conductor_id_with_cond_info(Cond_info)))
        
        self.branch_info_history.append(self.branch_info)
        self.cond_info_history.append(Cond_info)
        
        
    def undo_place_number(self):
        global Cond_info
        # Check if there are any positions to undo
        if not self.positions:
            print("No more numbers to undo.")
            return
        position = self.positions.pop()
        layer, slot = position
        # Pop the previous states from history
        self.branch_info = self.branch_info_history.pop()
        Cond_info = self.cond_info_history.pop()
        # print(self.branch_info)
        # Decrease the current_number and handle branch index if needed
        if self.current_number == 1:
            if self.branch_index == 0:
                print("No more numbers to undo.")
                return
            self.branch_index -= 1
            self.current_number = self.group_size
            self.remaining_in_branch = 0
        else:
            self.current_number -= 1
            self.remaining_in_branch += 1
            
        # Reset the button's state and style
        self.buttons[layer][slot].config(text="", state="normal", bg="lightgreen", fg="black", font=("Helvetica", 10, "normal"), padx=0, pady=0)
        
        # Update slots array
        self.slots[layer][slot] = 0
        
        # Update the position
        self.current_position = self.positions[-1]
        # print(self.current_position)

        # Update the branch status labels
        self.setup_branch_status()
        
        # Undo the branch info update
        self.update_branch_info(layer, slot, undo=True)
        
        # Update valid positions
        self.highlight_valid_positions()
    
        # Print the pin info
        self.print_pin_info(self.analyze_database(self.get_db_conductor_id_with_cond_info(Cond_info)))

    
    def update_branch_info(self, x, y, undo=False):
        origin_slot = self.re_slot_shift(y, x)
        phasor_index = (origin_slot) % self.q
        self.temp_phasor_index = phasor_index
        layer_index = x
        key = f'Phasor {phasor_index + 1} Layer {layer_index + 1}'
    
        if not undo:
            # Record the current state before making changes for undo functionality
            if 'count' not in self.branch_info[self.branch_index][key]:
                self.branch_info[self.branch_index][key]['count'] = 0
            if 'left' not in self.branch_info[self.branch_index][key]:
                self.branch_info[self.branch_index][key]['left'] = self.group_size
    
            self.branch_info_history.append(copy.deepcopy(self.branch_info[self.branch_index][key]))
            self.branch_info[self.branch_index][key]['count'] += 1
            self.branch_info[self.branch_index][key]['left'] -= 1
        else:
            # Revert to the previous state during an undo operation
            if self.branch_info_history:
                prev_state = self.branch_info_history.pop()
                self.branch_info[self.branch_index][key]['count'] = prev_state['count']
                self.branch_info[self.branch_index][key]['left'] = prev_state['left']
    
        self.display_branch_info()

    def get_origin_position(self,current_position):
        layer,modi_slot = current_position
        origin_slot = self.re_slot_shift(modi_slot, layer)
        current_pole_index = origin_slot // (self.m * self.q)
        return layer,origin_slot,current_pole_index
    
    def return_manufacturing_valid_layers(self, current_position):
        current_layer,current_slot,current_pole_index = self.get_origin_position(current_position)
        if self.FL_connection == 'N':
            if current_layer == 0:
                next_layers = [(layer+self.num_layers)%self.num_layers for layer in [current_layer,current_layer+1]]
            elif current_layer == self.num_layers-1:
                next_layers = [(layer+self.num_layers)%self.num_layers for layer in [current_layer-1,current_layer]]
            else:
                next_layers = [(layer+self.num_layers)%self.num_layers for layer in [current_layer-1,current_layer,current_layer+1]]
        else:
            next_layers = [(layer+self.num_layers)%self.num_layers for layer in [current_layer-1,current_layer,current_layer+1]]
        unique_layers = list(dict.fromkeys(next_layers))
        return unique_layers
    
    def return_winding_theory_valid_positions(self, current_position):
        valid_positions = []
        current_layer,current_slot,current_pole_index = self.get_origin_position(current_position)
        next_pole_indexs = [(index+self.num_poles)%self.num_poles for index in [current_pole_index+1,current_pole_index-1]]
        valid_layers = self.return_manufacturing_valid_layers(current_position)
        for pole in next_pole_indexs:
            for i in range(self.q):
                slot = pole * (self.m * self.q) + i
                for layer in valid_layers:
                    modi_slot = self.slot_shift(slot, layer)
                    position = (layer,modi_slot)
                    valid_positions.append(position)
        unique_positions = list(dict.fromkeys(valid_positions))
        return unique_positions
    
    def return_symmetry_positions(self, current_position):
        valid_positions = []
        Winding_valid_positions = self.return_winding_theory_valid_positions(current_position)
        for (layer,slot) in Winding_valid_positions:
            origin_slot = self.re_slot_shift(slot, layer)
            phasor_index = origin_slot % self.q + 1
            layer_index = layer + 1
            key = f'Phasor {phasor_index} Layer {layer_index}'
            if self.branch_info[self.branch_index][key]['left'] > 0 or self.full_symmetry == 'N':
                if self.slots[layer][slot] == 0:
                    valid_positions.append((layer, slot)) 
        return valid_positions
    
        
    def get_valid_positions(self, current_position, current_number):
        #### 1. Symmetry Rule  
        #### 2. Manufacturing Rule
        #### 3. Winding Theory Rule
        
        if self.branch_index > 0 and self.current_number == 1:  #### Start the next branch
            valid_positions = []
            for slot in range(self.num_slots):
                for layer in range(self.num_layers):
                    modi_slot = self.slot_shift(slot, layer)
                    if slot % (self.m * self.q) < self.q: 
                        if self.slots[layer][modi_slot] == 0:
                            valid_positions.append((layer, modi_slot)) 
        else:           
            valid_positions = self.return_symmetry_positions(current_position)
        return valid_positions


    def highlight_valid_positions(self):
        valid_positions = self.get_valid_positions(self.current_position, self.current_number-1)
        # print (valid_positions)
        for i in range(self.num_layers):
            for j in range(self.num_slots):
                if self.buttons[i][j]['state'] == 'disabled':  # Ensure not to override already placed numbers
                    continue
                self.buttons[i][j].config(bg="SystemButtonFace")  # Reset color only if not disabled
        for (x, y) in valid_positions:
            if self.buttons[x][y]['state'] != 'disabled':  # Ensure we do not highlight disabled buttons
                self.buttons[x][y].config(bg="lightgreen") 
                next_position = (x, y)
                next_number = self.current_number
                next_valid_positions = self.get_valid_positions(next_position, next_number)
                if not next_valid_positions:
                    self.buttons[x][y].config(bg="orange")  # Orange highlight the button 
                else:
                    valid_test = 0
                    for next_valid_position in next_valid_positions:
                        # self.buttons[x][y]['state'] = 'disabled'
                        next_2_position = next_valid_position
                        next_2_number = self.current_number + 1
                        next_2_valid_positions = self.get_valid_positions(next_2_position, next_2_number)
                        if next_position in next_2_valid_positions:
                            next_2_valid_positions.remove(next_position)
                        if next_2_valid_positions:
                            valid_test = 1
                    if valid_test == 0:
                        self.buttons[x][y].config(bg="yellow")  # Yellow highlight the button 
                    else:
                        self.buttons[x][y].config(bg="lightgreen")  



if __name__ == "__main__":
    app = SlotGame()
    app.mainloop()




