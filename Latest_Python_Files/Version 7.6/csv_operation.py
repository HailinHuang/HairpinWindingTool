# -*- coding: utf-8 -*-
"""
Created on Fri Jun 21 15:56:18 2024

@author: ezzhh5
"""

import csv 
import os

# csv functions

def output_to_csv(path, value): 
    """Write a list of values to a CSV file at the specified path."""
    try:
        with open(path, "w", newline="") as file:
            writer = csv.writer(file)
            for row in value:
                writer.writerow(row)
    except Exception as e:
        print(f"Error writing to CSV: {e}")
        
def Loadcsv(path):
	with open(path, 'r') as f: 
		csvdata = list(csv.reader(f))
		return csvdata

def generate_branch_csv(Winding_Para,branch_data,branch_name,file_path):
    matrix = [['' for _ in range(Winding_Para.num_slots)] for _ in range(Winding_Para.num_layers)]
    # Fill in slot indices in the first row (starting from column 1)
    for slot in range(1, Winding_Para.num_slots + 1):
        matrix[0][slot] = str(slot)
    
    # Fill in layer indices in the first column (starting from row 1)
    for layer in range(1, Winding_Para.num_layers + 1):
        matrix[layer][0] = str(layer)
        
    # Fill in conductor numbers, offset by 1 for both row and column due to indices
    for idx, (col, row, _) in enumerate(branch_data):
        matrix[row + 1][col + 1] = str(idx + 1)
        
    # Write to CSV file
    with open(file_path, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(matrix)
    return file_path

def output_branches_to_csv(Winding_Para, db_conductor_id, base_file_path=None):
    # If base_file_path is not provided, use the directory of the current script
    if base_file_path is None:
        base_file_path = os.path.dirname(os.path.abspath(__file__))

    # Write to CSV file
    for branch in db_conductor_id:
        branch_name = f"branch{branch[0]}"
        file_path = os.path.join(base_file_path, f"{branch_name}.csv")
        generate_branch_csv(Winding_Para, branch[1], branch_name, file_path)
        print(f"Output successfully written to {file_path}")

