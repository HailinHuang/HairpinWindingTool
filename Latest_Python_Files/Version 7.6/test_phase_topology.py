import cmath
import math
import unittest
from phase_topology import (
    phase_map, electrical_summary, supports_phase_count,
    supports_phase_layer_allocation, winding_q,
)
from get_winding_pattern import get_phase_shift_list
from types import SimpleNamespace


class PhaseTopologyTests(unittest.TestCase):
    def test_invalid_count_types_fail_with_clear_value_error(self):
        from phase_topology import default_phase_map, apply_layer_shifts
        for slots, poles, phases in ((18, 4, 0), (18.0, 4, 3), (18, True, 3)):
            with self.subTest(slots=slots, poles=poles, phases=phases):
                with self.assertRaises(ValueError):
                    winding_q(slots, poles, phases)
        for layers in (0, -1, 1.5, True):
            with self.assertRaises(ValueError):
                default_phase_map(18, 4, layers)
        for shift in (float('inf'), float('nan'), None):
            with self.assertRaises(ValueError):
                apply_layer_shifts(default_phase_map(18, 4, 1), 18, 1, [shift])

    @staticmethod
    def angular_reference(slots, poles, layers, shifts):
        """Independent nearest-axis assignment, then translate physical slots."""
        labels = ((0, 1), (1, -1), (2, 1), (0, -1), (1, 1), (2, -1))
        fractional = slots % (3 * poles) != 0
        records = []
        for slot in range(slots):
            for layer in range(layers):
                odd = fractional and layer % 2
                offset = math.ceil(slots / poles) if odd else 0
                angle = math.pi * poles * (slot + offset) / slots
                distances = [abs(cmath.phase(cmath.exp(
                    1j * (angle + 1e-10 - (axis + .5) * math.pi / 3))))
                    for axis in range(6)]
                phase, sign = labels[distances.index(min(distances))]
                records.append(((slot + shifts[layer]) % slots, layer,
                                phase, -sign if odd else sign))
        return records

    def test_nonhalf_q_and_odd_layers_against_independent_reference(self):
        for slots, poles in ((12, 6), (15, 4), (21, 10), (27, 8),
                             (18, 4), (30, 4), (42, 4), (60, 8), (84, 8)):
            for layers in (1, 3, 5, 6):
                for mode in ('None', 'Normal', 'Increment'):
                    for psl in (0, 1, 2, layers, layers + 1):
                        with self.subTest(slots=slots, poles=poles, layers=layers,
                                          mode=mode, psl=psl):
                            shifts = get_phase_shift_list(
                                SimpleNamespace(num_layers=layers), mode,
                                -slots - 1, psl, log=lambda _: None)
                            reference = self.angular_reference(slots, poles, layers, shifts)
                            actual = phase_map(slots, poles, layers, shifts)
                            self.assertEqual(actual, reference)
                            self.assertEqual(len({r[:2] for r in actual}), slots * layers)
                            self.assertTrue(all(p in range(3) and d in (-1, 1)
                                                for _, _, p, d in actual))
                            result = electrical_summary(actual, slots, poles)
                            for phase in range(3):
                                selected = [(s, d) for s, _, p, d in reference if p == phase]
                                real = math.fsum(d * math.cos(math.pi * poles * s / slots)
                                                 for s, d in selected)
                                imag = math.fsum(d * math.sin(math.pi * poles * s / slots)
                                                 for s, d in selected)
                                self.assertAlmostEqual(abs(result['emf'][phase] -
                                                           complex(real, imag)), 0, places=8)
                                self.assertEqual(result['counts'][phase], len(selected))

    def test_phase_shift_mode_semantics_and_validation(self):
        winding = SimpleNamespace(num_layers=5)
        for mode, psl, expected in (
                ('None', 2, [0, 0, 0, 0, 0]),
                ('Normal', 2, [0, 0, -3, -3, 0]),
                ('Increment', 2, [0, 0, -3, -3, -6]),
                ('Normal', 0, [0, 0, 0, 0, 0]),
                ('Increment', 0, [0, 0, 0, 0, 0]),
                ('Normal', 6, [0, 0, 0, 0, 0]),
                ('Increment', 6, [0, 0, 0, 0, 0])):
            self.assertEqual(get_phase_shift_list(winding, mode, -3, psl,
                                                  log=lambda _: None), expected)
        for mode, shift, psl in (('Bad', 0, 1), ('Normal', .5, 1),
                                  ('Normal', 0, -.5), ('Normal', 0, -1),
                                  ('Increment', 1, 1.5)):
            with self.assertRaises(ValueError):
                get_phase_shift_list(winding, mode, shift, psl, log=lambda _: None)

    def test_invalid_phase_inputs_and_exact_q(self):
        from fractions import Fraction
        from phase_topology import parse_q, default_phase_map, apply_layer_shifts
        self.assertEqual(parse_q(' 5/2 '), Fraction(5, 2))
        self.assertEqual(parse_q('2.5'), Fraction(5, 2))
        self.assertEqual(winding_q(15, 4), Fraction(5, 4))
        for value in ('0', '-1', '', 'bad'):
            with self.assertRaises(ValueError):
                parse_q(value)
        for slots, poles in ((0, 4), (14, 4), (18, 3), (18, 0), (-18, 4)):
            with self.assertRaises(ValueError):
                winding_q(slots, poles)
        for layers in (0, -1):
            with self.assertRaises(ValueError):
                default_phase_map(18, 4, layers)
        defaults = default_phase_map(18, 4, 3)
        for shifts in ([0, 0], [0, 0, 0, 0], [0, .5, 0], [0, True, 0]):
            with self.assertRaises(ValueError):
                apply_layer_shifts(defaults, 18, 3, shifts)

    def test_multiples_of_three_array_three_phase_sets_by_layer(self):
        phases_to_check = (3, 5, 6, 7, 9, 12, 15, 18)
        for phases in phases_to_check:
            with self.subTest(phases=phases):
                self.assertTrue(supports_phase_count(phases))
                set_count = phases // 3 if phases % 3 == 0 else 1
                layers = 3 * set_count if phases % 3 == 0 else 6
                poles, q = 4, 4
                slots = phases * poles * q
                expected = []
                for slot in range(slots):
                    for layer in range(layers):
                        if phases % 3 == 0:
                            phase_set = layer // (layers // set_count)
                            set_q = q * set_count
                            slot_offset = 2 * q * phase_set
                            set_belt = math.floor(
                                (slot - slot_offset) / set_q + 1e-10)
                            phase = 3 * phase_set + set_belt % 3
                            sign = (-1) ** set_belt
                        else:
                            electrical_angle = math.pi * poles * slot / slots
                            belt = math.floor(
                                electrical_angle * phases / math.pi + 1e-10)
                            phase, pole_sector = belt % phases, belt // phases
                            sign = (-1) ** (phase + pole_sector)
                        expected.append((slot, layer, phase, sign))

                actual = phase_map(slots, poles, layers, phases=phases)
                self.assertEqual(actual, expected)
                self.assertEqual(
                    electrical_summary(actual, slots, poles, phases)['counts'],
                    [slots * layers // phases] * phases,
                )
                if phases > 3 and phases % 3 == 0:
                    summary = electrical_summary(actual, slots, poles, phases)
                    self.assertEqual(summary['balance_model'],
                                     'independent_three_phase_sets')
                    self.assertTrue(summary['balanced'], summary)
                    self.assertTrue(summary['array_aligned'], summary)
                    self.assertEqual(len(summary['sets']), phases // 3)
                    for phase_set, group in enumerate(summary['sets']):
                        self.assertAlmostEqual(
                            group['array_offset_degrees'],
                            phase_set * 360 / phases)
                        self.assertAlmostEqual(
                            group['observed_array_offset_degrees'],
                            phase_set * 360 / phases)
                        self.assertTrue(group['array_aligned'], group)

        for phases in (0, 1, 2, 4, 8, True, 6.0):
            with self.subTest(unsupported_phases=phases):
                self.assertFalse(supports_phase_count(phases))
                with self.assertRaises(ValueError):
                    phase_map(24, 4, 6, phases=phases)
        for phases, layers in ((6, 5), (9, 4), (12, 6)):
            with self.subTest(phases=phases, layers=layers):
                self.assertTrue(supports_phase_count(phases))
                self.assertFalse(supports_phase_layer_allocation(phases, layers))
                with self.assertRaisesRegex(ValueError, 'layers divisible'):
                    phase_map(phases * 4, 4, layers, phases=phases)

    def test_canonical_topology_contains_phase_records_and_set_transforms(self):
        from phase_topology import build_phase_topology

        for phases in (3, 5, 6, 7, 9, 12):
            set_count = phases // 3 if phases % 3 == 0 else 1
            layers = 2 * set_count if set_count > 1 else 4
            poles, q = 4, 2
            slots = phases * poles * q
            topology = build_phase_topology(slots, poles, layers, phases)
            with self.subTest(phases=phases):
                self.assertEqual(topology.phases, phases)
                self.assertEqual(topology.set_count, set_count)
                self.assertEqual(len(topology.records), slots * layers)
                self.assertEqual(
                    {(r.slot, r.layer) for r in topology.records},
                    {(slot, layer) for slot in range(slots)
                     for layer in range(layers)},
                )
                self.assertEqual(
                    tuple((r.slot, r.layer, r.phase, r.sign)
                          for r in topology.records),
                    tuple(phase_map(slots, poles, layers, phases=phases)),
                )
                self.assertEqual(
                    topology.phase_model,
                    ('arrayed_three_phase_sets' if set_count > 1
                     else 'symmetric_polyphase'),
                )
                self.assertTrue(all(r.sign in (-1, 1) for r in topology.records))
                for spec in topology.phase_sets:
                    expected_offset = (spec.set_index * 360 / phases
                                       if set_count > 1 else 0)
                    self.assertAlmostEqual(
                        float(spec.electrical_offset_degrees), expected_offset)
                    for slot, layer in ((0, spec.layer_start),
                                         (slots - 1,
                                          spec.layer_start + spec.layer_count - 1)):
                        local = spec.to_local(slot, layer)
                        self.assertEqual(spec.to_global(*local), (slot, layer))
                    for local_phase in range(len(spec.phases)):
                        phase = spec.global_phase(local_phase)
                        self.assertEqual(spec.local_phase(phase), local_phase)

    def test_topology_feasibility_uses_the_requested_layer_count(self):
        from phase_topology import phase_division_feasibility

        valid = phase_division_feasibility(48, 4, 4, 6)
        invalid = phase_division_feasibility(48, 4, 3, 6)
        self.assertTrue(valid.feasible, valid.reason)
        self.assertEqual(valid.q.numerator, 2)
        self.assertEqual(valid.q.denominator, 1)
        self.assertEqual(valid.set_count, 2)
        self.assertEqual(valid.phase_model, 'arrayed_three_phase_sets')
        self.assertFalse(invalid.feasible)
        self.assertIn('layers divisible by 2', invalid.reason)

    def test_legacy_cond_info_is_a_topology_adapter(self):
        from phase_topology import build_phase_topology, legacy_cond_info

        slots, poles, layers, phases = 24, 4, 4, 3
        topology = build_phase_topology(slots, poles, layers, phases)
        winding = SimpleNamespace(
            q=slots / (poles * phases), num_slots=slots, num_poles=poles,
            num_layers=layers, num_phases=phases)
        layout = SimpleNamespace(phase_shift_list=[0] * layers)
        legacy = legacy_cond_info(topology)
        wrapped = __import__('get_winding_pattern').Winding_Phase_division(
            winding, layout, log=lambda _: None)
        self.assertEqual(legacy, wrapped)

    def test_default_is_immutable_and_reapply_does_not_accumulate(self):
        from phase_topology import default_phase_map, apply_layer_shifts
        for slots in (36,60,84):
            defaults = default_phase_map(slots, 8, 6)
            shifts = [0,1,0,1,0,1]
            first = apply_layer_shifts(defaults,slots,6,shifts)
            second = apply_layer_shifts(defaults,slots,6,shifts)
            self.assertEqual(first,second)
            self.assertEqual(defaults,default_phase_map(slots,8,6))
            self.assertEqual(apply_layer_shifts(first,slots,6,[-s for s in shifts]),list(defaults))
            with self.assertRaises(ValueError):
                apply_layer_shifts(defaults,slots,6,[0,.5,0,0,0,0])

    def test_connection_follows_shifted_endpoints(self):
        from phase_topology import shifted_connection_slot
        for slots, pitches in ((36,(4,5)),(60,(7,8)),(84,(10,11))):
            for delta in (*pitches, *(-p for p in pitches)):
                for shifts in ([0,1],[2,-1],[slots,slots]):
                    start = (slots-2+shifts[0]) % slots
                    end = shifted_connection_slot(delta,start,0,1,shifts,slots)
                    self.assertEqual(end,(slots-2+delta+shifts[1]) % slots)

    def test_legacy_direction_convention_adapter(self):
        from get_winding_pattern import Winding_Phase_division
        for q in (1,1.5,2,2.5,3,3.5):
            for poles in (4,8):
                for layers in (4,6,8):
                    slots = int(q*3*poles)
                    winding = SimpleNamespace(q=q,num_slots=slots,num_poles=poles,num_layers=layers,num_phases=3)
                    for mode in ('None','Normal','Increment'):
                        shifts = get_phase_shift_list(winding,mode,-1,1,log=lambda _:None)
                        old = Winding_Phase_division(winding,SimpleNamespace(phase_shift_list=shifts),log=lambda _:None)
                        actual = {(s,l):(p,d) for s,l,p,d in phase_map(slots,poles,layers,shifts)}
                        for s,l,p,branch,index,phasor,pole in old:
                            self.assertEqual(actual[s,l], (p,(-1)**(pole+p)))

    def test_legacy_odd_layer_mismatch_is_a_known_connection_boundary(self):
        # This records a legacy limitation, not acceptance of that generator.
        # Remove this diagnostic when its separate connection migration is approved.
        from get_winding_pattern import Winding_Phase_division
        for slots, poles, layers in ((18, 4, 3), (30, 4, 5), (84, 8, 5)):
            winding = SimpleNamespace(q=slots / (3 * poles), num_slots=slots,
                                      num_poles=poles, num_layers=layers, num_phases=3)
            old = Winding_Phase_division(winding, SimpleNamespace(
                phase_shift_list=[0] * layers), log=lambda _: None)
            reference = {(s, l): (p, d) for s, l, p, d in
                         self.angular_reference(slots, poles, layers, [0] * layers)}
            self.assertTrue(any(reference[s, l] != (p, (-1) ** (pole + p))
                                for s, l, p, _, _, _, pole in old),
                            'Legacy odd-layer behavior changed; review its support boundary.')

    def test_independent_angular_sector_reference(self):
        # Enumerate the six signed phase axes, rather than floor(slot / q).
        labels = ((0, 1), (1, -1), (2, 1), (0, -1), (1, 1), (2, -1))
        for slots in (12, 18, 24, 30, 36, 42, 48, 60, 72, 84):
            poles = 4 if slots < 36 else 8
            fractional = slots % (3 * poles) != 0
            for slot, layer, phase, sign in phase_map(slots, poles, 6):
                offset = math.ceil(slots / poles) if fractional and layer % 2 else 0
                angle = (math.pi * poles * (slot + offset) / slots) % (2 * math.pi)
                # A tiny forward perturbation resolves exact half-open boundaries.
                distances = [abs(cmath.phase(cmath.exp(1j * (angle + 1e-10 - (k+.5)*math.pi/3))))
                             for k in range(6)]
                expected_phase, expected_sign = labels[distances.index(min(distances))]
                if fractional and layer % 2:
                    expected_sign *= -1
                self.assertEqual((phase, sign), (expected_phase, expected_sign))

    def test_target_matrix_and_shift_covariance(self):
        for q in (1, 1.5, 2, 2.5, 3, 3.5):
            for poles in (4, 8):
                for layers in (4, 6, 8):
                    slots = int(q * 3 * poles)
                    base = phase_map(slots, poles, layers)
                    self.assertEqual(len({r[:2] for r in base}), slots * layers)
                    summary = electrical_summary(base, slots, poles)
                    self.assertTrue(summary['balanced'], (q, poles, layers, summary))
                    for shift in (-1, 0, 1, slots, slots + 1):
                        moved = phase_map(slots, poles, layers, [shift] * layers)
                        expected = [v * cmath.exp(1j * math.pi * poles * shift / slots)
                                    for v in summary['emf']]
                        actual = electrical_summary(moved, slots, poles)['emf']
                        for a, b in zip(actual, expected):
                            self.assertAlmostEqual(abs(a-b), 0, places=8)

    def test_partial_layer_shift(self):
        for mode in ('Normal', 'Increment'):
            for psl in (0, 1, 2, 8):
                shifts = get_phase_shift_list(SimpleNamespace(num_layers=6), mode, -2, psl, log=lambda _: None)
                base = phase_map(36, 8, 6)
                moved = phase_map(36, 8, 6, shifts)
                self.assertEqual(moved, [((s+shifts[l]) % 36, l, p, d) for s,l,p,d in base])

    def test_arithmetic_conditions_do_not_imply_symmetry(self):
        self.assertEqual(str(winding_q(6, 6)), '1/3')
        self.assertFalse(electrical_summary(phase_map(6, 6, 4), 6, 6)['balanced'])


if __name__ == '__main__':
    unittest.main()
