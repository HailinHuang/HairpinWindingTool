# -*- coding: utf-8 -*-
"""
Created on Mon Jun 24 10:17:37 2024

@author: ezzhh5
"""

# 0. slot, 1. layer, 2. phase, 3. branch_id, 4. Cond_index, 5. Cond_Phasor 6. Pole_index 

def find_phase_conductors(phase_index, cond_info):
    return [cond for cond in cond_info if cond[2] == phase_index]

def get_phase_index(slot, layer, cond_info):
    for info in cond_info:
        if info[0] == slot and info[1] == layer:
            return info[2]
    return None  # Return None if no matching slot and layer are found

def get_branch_index(slot, layer, cond_info):
    for info in cond_info:
        if info[0] == slot and info[1] == layer:
            return info[3]
    return None  # Return None if no matching slot and layer are found

def get_pole_index(slot, layer, cond_info):
    for info in cond_info:
        if info[0] == slot and info[1] == layer:
            return info[6]
    return None  # Return None if no matching slot and layer are found

def update_cond_info_with_branch_data(cond_info, db_conductor_id):
    """
    For each branch's conductor sequence, assign branch_id and *its*
    branch_index to a distinct cond_info row, preserving the original
    order (so later retrieval sorted by branch_index matches the path).

    Assumes cond_info rows look like:
      (slot, layer, phase_idx, branch_id, branch_index, phasor, ...)
    where branch_id starts as -1 and branch_index starts as -1.
    """

    # Build lookup maps of available cond_info rows by keys and
    # also track which rows we have already used/assigned in this pass.
    from collections import defaultdict

    by_slp = defaultdict(list)   # (slot, layer, phasor) -> [indices]
    by_sl  = defaultdict(list)   # (slot, layer)         -> [indices]
    for i, ci in enumerate(cond_info):
        s, l, *_ = ci
        p = ci[5] if len(ci) > 5 else None
        by_sl[(s, l)].append(i)
        if p is not None:
            by_slp[(s, l, p)].append(i)

    used = set()  # indices in cond_info already assigned for this update

    def take_index(slot, layer, phasor):
        """Pick an unused cond_info row matching (slot, layer, phasor) if possible,
        otherwise any unused row matching (slot, layer)."""
        # Prefer exact (slot, layer, phasor)
        cand = by_slp.get((slot, layer, phasor), [])
        for idx in cand:
            if idx not in used:
                used.add(idx)
                return idx
        # Fallback: any (slot, layer)
        cand = by_sl.get((slot, layer), [])
        for idx in cand:
            if idx not in used:
                used.add(idx)
                return idx
        return None  # no available row (shouldn't happen if cond_info is consistent)

    # Assign each occurrence its own row and its own branch_index
    for branch_id, conductors in db_conductor_id:
        for index, (slot, layer, phasor) in enumerate(conductors):
            k = take_index(slot, layer, phasor)
            if k is None:
                # Optional: log or raise to help diagnose mismatches
                # print(f"Warning: no cond_info row for ({slot},{layer},{phasor})")
                continue
            ci = list(cond_info[k])
            ci[3] = branch_id         # branch id
            ci[4] = index             # branch index (draw order)
            ci[5] = phasor            # ensure correct phasor stored for this occurrence
            cond_info[k] = tuple(ci)

    return cond_info


def get_start_conductor_id_with_cond_info(cond_info):
    start_conductor_ids = []
    for ci in cond_info:
        # if ci[2] == 0 and ci[3] > -1:  ### Only first phase Only filled positions
        if ci[4] == 0:  ### the first conductor
            slot = ci[0]
            layer = ci[1]
            phasor = ci[5]
            start_conductor_id = (slot,layer,phasor)
            start_conductor_ids.append(start_conductor_id)
    start_conductor_ids = sort_conductor_ids_with_branch_index(start_conductor_ids, cond_info)
    return start_conductor_ids

def get_db_conductor_id_with_cond_info(cond_info):
    db_conductor_id = {}
    for ci in cond_info:
        slot = ci[0]
        layer = ci[1]
        branch_id = ci[3]
        cond_index = ci[4]
        phasor = ci[5] 
        # Create the conductor tuple
        conductor = (slot, layer, phasor)
        # Add the conductor to the appropriate branch_id in db_conductor_id
        if branch_id != 0:
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
    db_conductor_id_list = [[branch_id, conductors] for branch_id, conductors in sorted(db_conductor_id.items())]
    return db_conductor_id_list

def sort_conductor_ids_with_branch_index(start_conductor_ids, cond_info):
    def get_branch(conductor_id):
        slot, layer, phasor = conductor_id
        return get_branch_index(slot, layer, cond_info)
    sorted_conductor_ids = sorted(start_conductor_ids, key=get_branch)
    return sorted_conductor_ids

def sort_conductor_ids_with_phase_index(start_conductor_ids, cond_info):
    def get_phase(conductor_id):
        slot, layer, phasor = conductor_id
        return get_phase_index(slot, layer, cond_info)
    sorted_conductor_ids = sorted(start_conductor_ids, key=get_phase)
    return sorted_conductor_ids

def get_cond_ids_with_cond_info(cond_info,branch_index):
    db_conductor_id = get_db_conductor_id_with_cond_info(cond_info)
    for branch,conductors in db_conductor_id:
        if branch == branch_index:
            cond_ids = conductors
    return cond_ids

def get_start_cond_ids_with_cond_info(cond_info):
    start_cond_ids = []
    db_conductor_id = get_db_conductor_id_with_cond_info(cond_info)
    for branch,conductors in db_conductor_id:
        start_cond = conductors[0]
        start_cond_ids.append(start_cond)
    return start_cond_ids
                
