"""Independent ordered identity regressions, using stored geometry fixtures."""
import json
from pathlib import Path
from types import SimpleNamespace
from fractions import Fraction

from pattern_identity import analyze_ordered_pattern


def test_every_connection_stays_within_one_pole_region_transition():
    from pattern_identity import pole_region_crossings

    # Slot labels in the review drawings are one based; these are actual slots.
    assert pole_region_crossings(31, -19, 6) == 3
    assert pole_region_crossings(110, -30, 10) == 3
    assert pole_region_crossings(31, -7, 6) == 1
    assert pole_region_crossings(47, 1, 6) == 1
    assert pole_region_crossings(6, -1, 6) == 1

    winding = SimpleNamespace(num_slots=48, num_layers=4,
                              num_phases=3, q=2, ab=1)
    layout = SimpleNamespace(inlet_from_weld_side=1,
                             phase_shift_list=[0] * 4)
    report = analyze_ordered_pattern(
        'CP', [(1, [(31, 2), (12, 0)])], winding, layout)
    assert report['ordered_status'] == 'candidate'
    assert any('pole regions' in error for error in report['errors'])


def test_half_integer_pole_boundaries_use_exact_region_width():
    from pattern_identity import pole_region_crossings

    # q=3/2, m=3 has 9/2 slots per physical pole region.
    assert pole_region_crossings(8, 1, Fraction(9, 2)) == 1
    assert pole_region_crossings(9, -1, Fraction(9, 2)) == 1
    assert pole_region_crossings(8, -7, Fraction(9, 2)) == 1
    assert pole_region_crossings(8, 11, Fraction(9, 2)) == 3


def test_half_integer_signed_travel_is_checked_across_wrap():
    class Branches(list):
        pass

    winding = SimpleNamespace(num_slots=18, num_layers=2,
                              num_phases=3, q=Fraction(3, 2), ab=1)
    layout = SimpleNamespace(inlet_from_weld_side=0, phase_shift_list=[0, 0])
    database = Branches([(1, [(8, 0), (1, 1)])])

    shortest = analyze_ordered_pattern('BWP', database, winding, layout)
    assert shortest['qualification'] == 'bounded-half-integer-even-layer'
    assert shortest['ordered_status'] == 'valid', shortest['errors']
    assert shortest['observed_signatures'][0][0]['pole_region_crossings'] == (1,)

    database.signed_travel = {1: (11,)}
    longer = analyze_ordered_pattern('BWP', database, winding, layout)
    assert longer['ordered_status'] == 'candidate'
    assert longer['observed_signatures'][0][0]['pole_region_crossings'] == (3,)
    assert any('pole regions' in error for error in longer['errors'])


def test_physical_region_limit_uses_shifted_endpoints():
    winding = SimpleNamespace(num_slots=24, num_layers=2,
                              num_phases=3, q=2, ab=1)
    layout = SimpleNamespace(inlet_from_weld_side=0,
                             phase_shift_list=[0, 6])
    report = analyze_ordered_pattern(
        'BWP', [(1, [(5, 0), (12, 1)])], winding, layout)
    assert report['observed_signatures'][0][0]['slot_steps'] == (1,)
    assert report['observed_signatures'][0][0]['pole_region_crossings'] == (2,)
    assert report['ordered_status'] == 'candidate'


def cases(values):
    """Attach independent cases without an optional test-runner dependency."""
    def decorate(function):
        function.cases = values
        return function
    return decorate


EXAMPLES = json.loads((Path(__file__).parent / "assets/pattern_guide/branch_examples.json").read_text())


def case(example):
    winding = SimpleNamespace(num_slots=example['slots'], num_layers=example['layers'],
                              num_phases=3, q=example['q'], ab=1)
    layout = SimpleNamespace(inlet_from_weld_side=int(example['first_edge'] == 'insert'),
                             phase_shift_list=[0] * winding.num_layers)
    path = [(slot - 1, layer - 1) for slot, layer in example['nodes']]
    return winding, layout, path


@cases(EXAMPLES)
def test_ten_reference_paths_and_reversal(example):
    winding, layout, path = case(example)
    for nodes in (path, path[::-1]):
        report = analyze_ordered_pattern(example['pattern'], [(1, nodes)], winding, layout)
        assert report['ordered_status'] == 'valid', report['errors']
        assert example['pattern'] in report['compatible_patterns']


@cases(EXAMPLES)
def test_scaled_pitch_preserves_ordered_identity(example):
    winding, layout, path = case(example)
    baseline = analyze_ordered_pattern(example['pattern'], [(1, path)],
                                       winding, layout)
    assert baseline['ordered_status'] == 'valid', baseline['errors']
    winding.num_slots *= 2
    winding.q *= 2  # Preserve the number and width of physical pole regions.
    scaled = [(slot * 2, layer) for slot, layer in path]
    report = analyze_ordered_pattern(example['pattern'], [(1, scaled)],
                                     winding, layout)
    assert report['ordered_status'] == 'valid', report['errors']


def test_cp_selected_cross_layer_pitch_is_not_a_pattern_gate():
    from unittest.mock import patch
    import get_winding_pattern as gw

    winding = SimpleNamespace(num_slots=24, num_layers=4,
                              num_phases=3, q=2, ab=1)
    layout = SimpleNamespace(phase_shift_list=[0] * 4)
    with patch.object(gw, '_validate_selected_electrical'):
        gw.validate_selected_cp(
            [(1, [(0, 0), (7, 2), (13, 1)])], winding, layout)


def test_ssp_reflected_p2_accepts_forward_welds_with_other_pitch():
    from unittest.mock import patch
    import get_winding_pattern as gw

    winding = SimpleNamespace(num_slots=48, num_layers=4,
                              num_phases=3, q=2, ab=2,
                              branch_dividers=(1, 1, 2))
    layout = SimpleNamespace(phase_shift_list=[0] * 4)
    path = [(0, 0, 0), (5, 1, 0), (10, 2, 0), (15, 3, 0)]
    with patch.object(gw, 'pattern_SSP', return_value=([], [(1, path)])):
        _, database = gw._ssp_reflected_p2(None, winding, layout)
    assert database[0][1] == path


def test_opposite_weld_travel_across_branches_is_rejected():
    winding = SimpleNamespace(num_slots=12, num_layers=2,
                              num_phases=3, q=1, ab=2)
    layout = SimpleNamespace(inlet_from_weld_side=0,
                             phase_shift_list=[0, 0])
    database = [(1, [(0, 0), (2, 1)]),
                (2, [(7, 0), (5, 1)])]
    report = analyze_ordered_pattern('BWP', database, winding, layout)
    assert report['ordered_status'] == 'candidate'
    assert any('weld travel reverses' in error for error in report['errors'])


def test_explicit_long_arc_direction_cannot_override_pole_region_limit():
    class Branches(list):
        pass

    winding = SimpleNamespace(num_slots=12, num_layers=2,
                              num_phases=3, q=1, ab=1)
    layout = SimpleNamespace(inlet_from_weld_side=0,
                             phase_shift_list=[0, 0])
    database = Branches([(1, [(0, 0), (7, 1), (9, 0)])])
    assert analyze_ordered_pattern('BWP', database, winding, layout)['ordered_status'] == 'candidate'
    database.signed_travel = {1: (7, 2)}
    report = analyze_ordered_pattern('BWP', database, winding, layout)
    assert report['ordered_status'] == 'candidate'
    assert any('pole regions' in error for error in report['errors'])
    layout.phase_shift_list = [0, 1]
    shifted = analyze_ordered_pattern('BWP', database, winding, layout)
    assert shifted['ordered_status'] == 'candidate'
    assert shifted['observed_signatures'][0][0]['slot_steps'] == (6,)
    layout.phase_shift_list = [0, 0]
    database.signed_travel = {1: (6, 2)}
    assert analyze_ordered_pattern('BWP', database, winding, layout)['ordered_status'] == 'candidate'
    database.signed_travel = {1: (7,)}
    assert analyze_ordered_pattern('BWP', database, winding, layout)['ordered_status'] == 'candidate'


def test_uwp_selected_validator_uses_recorded_long_arc_direction():
    from unittest.mock import patch
    import get_winding_pattern as gw

    class Branches(list):
        pass

    winding = SimpleNamespace(num_slots=12, num_layers=2,
                              num_phases=3, q=1, ab=1,
                              branch_dividers=(1, 1, 1))
    layout = SimpleNamespace(phase_shift_list=[0, 0])
    database = Branches([(1, [(0, 0), (7, 1), (9, 0)])])
    database.signed_travel = {1: (7, 2)}
    with patch.object(gw, '_validate_selected_electrical'):
        gw.validate_pp_only_uwp(database, winding, layout)


def test_slp_paired_lane_join_uses_return_direction_not_exact_pitch():
    from unittest.mock import patch
    import get_winding_pattern as gw

    winding = SimpleNamespace(num_slots=12, num_layers=2,
                              num_poles=2, num_phases=3, q=2, ab=2,
                              branch_dividers=(1, 1, 2))
    layout = SimpleNamespace(phase_shift_list=[0, 0],
                             inlet_from_weld_side=0)
    source = [(0, 0, 0), (2, 1, 0), (6, 1, 0), (4, 0, 0),
              (2, 0, 1), (4, 1, 1), (0, 1, 1), (3, 0, 1)]
    signs = (1, -1, 1, -1, 1, -1, 1, -1)
    phase_records = [(slot, layer, 1, sign)
                     for (slot, layer, _), sign in zip(source, signs)]
    with (patch.object(gw, 'pattern_SLP', return_value=([], [(1, source)])),
          patch.object(gw, 'phase_map', return_value=phase_records)):
        _, database = gw._slp_pair_lane_p2_from_reference(None, winding, layout)
    assert len(database) == 2


def test_shortest_circumferential_direction_still_rejects_reversal():
    winding = SimpleNamespace(num_slots=24, num_layers=4,
                              num_phases=3, q=2, ab=1)
    layout = SimpleNamespace(inlet_from_weld_side=0,
                             phase_shift_list=[0] * 4)
    path = [(0, 0), (6, 1), (3, 0)]
    report = analyze_ordered_pattern('UWP', [(1, path)], winding, layout)
    assert report['ordered_status'] == 'candidate'


@cases(EXAMPLES)
def test_each_branch_is_checked(example):
    winding, layout, path = case(example)
    broken = list(path)
    broken[2] = (broken[2][0], winding.num_layers)
    report = analyze_ordered_pattern(example['pattern'], [(1, path), (2, broken)], winding, layout)
    assert report['ordered_status'] == 'candidate'
    assert report['branch_reports'][0]['status'] == 'valid'
    assert report['branch_reports'][1]['status'] == 'candidate'


@cases(['TLP', 'TSP', 'SLP', 'SSP'])
def test_short_pass_does_not_require_optional_return(code):
    example = next(item for item in EXAMPLES if item['pattern'] == code)
    winding, layout, path = case(example)
    report = analyze_ordered_pattern(code, [(1, path[:4])], winding, layout)
    assert report['ordered_status'] == 'valid', report['errors']


def test_changed_order_same_pin_spans_is_rejected():
    example = next(item for item in EXAMPLES if item['pattern'] == 'TLP')
    winding, layout, path = case(example)
    # All insertion and weld spans remain unchanged; the middle weld now reverses.
    broken = list(path)
    for index in range(3, len(broken)):
        broken[index] = ((broken[index][0] + 12) % winding.num_slots, broken[index][1])
    assert analyze_ordered_pattern('TLP', [(1, broken)], winding, layout)['ordered_status'] == 'candidate'


def test_shift_normalization_keeps_actual_coordinates():
    example = next(item for item in EXAMPLES if item['pattern'] == 'ZLP')
    winding, layout, path = case(example)
    layout.phase_shift_list = [0, 1, 3, -2]
    shifted = [((slot + layout.phase_shift_list[layer]) % winding.num_slots, layer) for slot, layer in path]
    report = analyze_ordered_pattern('ZLP', [(1, shifted)], winding, layout)
    assert report['ordered_status'] == 'valid', report['errors']
    edge = report['branch_reports'][0]['observed_signature'][0]
    assert edge['start'] == shifted[0]
    assert edge['slot_steps'] != edge['actual_slot_steps']


def test_two_layer_overlap_does_not_hide_bad_weld():
    winding = SimpleNamespace(num_slots=12, num_layers=2, num_phases=3, q=1, ab=1)
    layout = SimpleNamespace(inlet_from_weld_side=0, phase_shift_list=[0, 0])
    path = [(0, 0), (3, 1), (6, 0), (9, 1)]
    report = analyze_ordered_pattern('TLP', [(1, path)], winding, layout)
    assert report['ordered_status'] == 'valid', report['errors']
    assert report['degeneracy']
    bad = [(0, 0), (3, 0), (6, 1), (9, 1)]
    assert analyze_ordered_pattern('TLP', [(1, bad)], winding, layout)['ordered_status'] == 'candidate'


def test_half_circumference_direction_is_ambiguous_not_incorrect():
    winding = SimpleNamespace(num_slots=6, num_layers=4, num_phases=3, q=1, ab=1)
    layout = SimpleNamespace(inlet_from_weld_side=0, phase_shift_list=[0] * 4)
    report = analyze_ordered_pattern('TLP', [(1, [(0, 0), (3, 1), (0, 2), (3, 3)])], winding, layout)
    assert report['ordered_status'] == 'valid', report['errors']
    assert {'TLP', 'TSP'} <= set(report['compatible_patterns'])


def test_undefined_domain_is_qualified():
    winding, layout, path = case(EXAMPLES[0])
    winding.q = Fraction(4, 3)
    report = analyze_ordered_pattern('BWP', [(1, path)], winding, layout)
    assert report['ordered_status'] == 'candidate'
    assert report['qualification'] == 'unsupported-domain'


def test_exact_fraction_integer_q_and_long_wrap_choice():
    winding = SimpleNamespace(num_slots=6, num_layers=2, num_phases=3, q=Fraction(1), ab=1)
    layout = SimpleNamespace(inlet_from_weld_side=0, phase_shift_list=[0, 0])
    report = analyze_ordered_pattern('BWP', [(1, [(0, 0), (3, 1), (1, 1), (4, 0)])], winding, layout)
    assert report['ordered_status'] == 'valid', report['errors']


def test_only_marked_matching_uwp_series_bridge_is_accepted():
    class Branches(list):
        pass
    winding = SimpleNamespace(num_slots=24, num_layers=4, num_phases=3, q=2, ab=1)
    layout = SimpleNamespace(inlet_from_weld_side=0, phase_shift_list=[0] * 4)
    path = [(0, 0), (6, 1), (12, 0), (18, 1), (0, 1), (18, 0)]
    database = Branches([(1, path)])
    database.series_connections = [dict(branch_id=1, edge_index=3, start=path[3], end=path[4], kind='same_layer_series', side='insert')]
    assert analyze_ordered_pattern('UWP', database, winding, layout)['ordered_status'] == 'candidate'


    # A real bridge is a weld: preserve insertion/weld source parity.
    path = [(0, 0), (6, 1), (12, 0), (18, 1), (0, 1), (18, 0), (12, 1), (6, 0)]
    database[:] = [(1, path)]
    database.series_connections = [dict(branch_id=1, edge_index=3, start=path[3], end=path[4], kind='same_layer_series', side='weld')]
    assert analyze_ordered_pattern('UWP', database, winding, layout)['ordered_status'] == 'valid'
    database.series_connections = []
    assert analyze_ordered_pattern('UWP', database, winding, layout)['ordered_status'] == 'candidate'
    database.series_connections = [dict(branch_id=1, edge_index=3, start=(0, 0), end=path[4], kind='same_layer_series', side='weld')]
    assert analyze_ordered_pattern('UWP', database, winding, layout)['ordered_status'] == 'candidate'


@cases(['ZPP', 'LPP'])
def test_parallel_weld_order_is_not_pin_inventory(code):
    winding, layout, path = case(next(item for item in EXAMPLES if item['pattern'] == code))
    broken = path[:2] + [((slot - 12) % winding.num_slots, layer) for slot, layer in path[2:]]
    report = analyze_ordered_pattern(code, [(1, broken)], winding, layout)
    assert report['ordered_status'] == 'candidate', report['errors']


import unittest


class OrderedIdentityTests(unittest.TestCase):
    pass


for _name, _function in list(globals().items()):
    if _name.startswith('test_') and callable(_function):
        if hasattr(_function, 'cases'):
            for _index, _value in enumerate(_function.cases):
                setattr(OrderedIdentityTests, f'{_name}_{_index}',
                        lambda self, function=_function, value=_value: function(value))
        else:
            setattr(OrderedIdentityTests, _name, lambda self, function=_function: function())

del _name, _function, _index, _value


if __name__ == '__main__':
    unittest.main()
