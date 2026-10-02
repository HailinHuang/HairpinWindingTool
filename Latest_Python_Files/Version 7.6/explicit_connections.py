"""Explicit connection records and generator-independent branch checks."""
from collections import Counter, defaultdict
from dataclasses import dataclass
import cmath
import math

EMF_ASYMMETRY_ERRORS = frozenset({
    'parallel_emf_mismatch', 'three_phase_emf_mismatch', 'multi_phase_emf_mismatch'})


@dataclass(frozen=True)
class ConnectionEdge:
    start: tuple
    end: tuple
    default_signed_pitch: int
    signed_pitch: int
    side: str
    kind: str


def compile_edges(default_path, slots, shifts, signed_pitches, first_side='insert'):
    if slots <= 0 or len(signed_pitches) != len(default_path)-1:
        raise ValueError('One signed integer pitch is required per edge.')
    if first_side not in ('insert','weld'):
        raise ValueError('Unknown connection side.')
    if any(type(x) is not int for x in (*shifts,*signed_pitches)):
        raise ValueError('Pitches and layer shifts must be integers.')
    edges=[]
    for i, (a,b,pitch) in enumerate(zip(default_path,default_path[1:],signed_pitches)):
        if not (0 <= a[1] < len(shifts) and 0 <= b[1] < len(shifts)):
            raise ValueError('Invalid layer.')
        if (b[0]-a[0]-pitch) % slots:
            raise ValueError('Default pitch does not reach the specified conductor.')
        start=((a[0]+shifts[a[1]]) % slots,a[1])
        end=((b[0]+shifts[b[1]]) % slots,b[1])
        side=first_side if i%2==0 else ('weld' if first_side=='insert' else 'insert')
        kind='same_layer' if a[1]==b[1] else ('adjacent_layer' if abs(a[1]-b[1])==1 else 'jump_layer')
        edges.append(ConnectionEdge(start,end,pitch,pitch+shifts[b[1]]-shifts[a[1]],side,kind))
    return edges


def validate_branches(branches, phase_records, slots, poles, ab, phases=3, tolerance=1e-8):
    """Validate actual occupancy and signed conductor EMF, not a template count.

    This checks topology/electrics only; mode-specific edge constraints must
    additionally be checked against the selected pattern specification.
    """
    errors=[]
    records={(s,l):(p,d) for s,l,p,d in phase_records}
    if len(records)!=len(phase_records):
        raise ValueError('Reference map contains duplicate conductors.')
    keys=[tuple(c[:2]) for branch in branches for c in branch]
    counts=Counter(keys)
    if any(n>1 for n in counts.values()): errors.append('duplicate_conductor')
    if set(keys)-set(records): errors.append('unknown_conductor')
    if set(records)-set(keys): errors.append('missing_conductor')
    if len(branches)!=ab*phases: errors.append('branch_count')
    if ab<=0 or phases<=0: raise ValueError('Positive phase and branch counts required.')
    expected=len(records)/(ab*phases)
    if any(len(b)!=expected for b in branches): errors.append('branch_length')
    topology_valid=not errors
    voltages=defaultdict(list)
    for branch in branches:
        if not branch or any(tuple(c[:2]) not in records for c in branch): continue
        metadata=[records[tuple(c[:2])] for c in branch]
        phase=metadata[0][0]
        if any(p!=phase for p,d in metadata): errors.append('mixed_phase_branch')
        if any(d!=metadata[0][1]*(-1)**i for i,(p,d) in enumerate(metadata)):
            errors.append('direction_sequence')
        voltage=sum(d*cmath.exp(1j*math.pi*poles*c[0]/slots) for c,(p,d) in zip(branch,metadata))
        voltages[phase].append(voltage)
    for phase in range(phases):
        values=voltages[phase]
        if len(values)!=ab: errors.append('phase_branch_count'); continue
        scale=max(map(abs,values))
        if scale<1e-12: errors.append('zero_fundamental')
        elif any(abs(v-values[0])/scale>tolerance for v in values): errors.append('parallel_emf_mismatch')
    if phases>=3 and all(voltages[p] for p in range(phases)):
        v=[sum(voltages[p])/len(voltages[p]) for p in range(phases)]
        scale=max(map(abs,v))
        if scale>1e-12:
            steps=(step for step in range(1, phases) if math.gcd(step, phases)==1)
            residual=min(max(abs(v[k]-v[0]*cmath.exp(step*2j*math.pi*k/phases))
                             for k in range(phases))/scale for step in steps)
            if residual>tolerance:
                errors.append('three_phase_emf_mismatch' if phases==3
                              else 'multi_phase_emf_mismatch')
    return {'topology_valid':topology_valid,'electrically_valid':not errors,
            'layout_retained': not (set(errors) - EMF_ASYMMETRY_ERRORS),
            'layout_status': ('not strong symmetry layout'
                              if set(errors) & EMF_ASYMMETRY_ERRORS else 'no EMF asymmetry detected'),
            'errors':sorted(set(errors)),
            'branch_emf':{str(p):[[v.real,v.imag] for v in values] for p,values in voltages.items()}}
