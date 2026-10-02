import unittest
from explicit_connections import compile_edges, validate_branches


class ExplicitConnectionTests(unittest.TestCase):
    def test_shifted_endpoints_and_side_are_explicit(self):
        edges = compile_edges([(34,0),(2,1),(7,0)],36,[0,1], [4,5])
        self.assertEqual((edges[0].start,edges[0].end,edges[0].signed_pitch),((34,0),(3,1),5))
        self.assertEqual([e.side for e in edges],['insert','weld'])
        self.assertEqual(edges[1].signed_pitch,4)

    def test_rejects_duplicate_and_missing_conductors(self):
        records = [(0,0,0,1),(1,0,0,-1)]
        report = validate_branches([[(0,0),(0,0)]],records,6,2,1,phases=1)
        self.assertFalse(report['topology_valid'])
        self.assertIn('duplicate_conductor',report['errors'])

    def test_rejects_wrong_direction_even_when_occupancy_passes(self):
        records = [(0,0,0,1),(1,0,0,1)]
        report = validate_branches([[(0,0),(1,0)]],records,6,2,1,phases=1)
        self.assertTrue(report['topology_valid'])
        self.assertIn('direction_sequence',report['errors'])

    def test_branch_voltage_is_measured_not_inferred_from_count(self):
        records = [(0,0,0,1),(3,0,0,-1),(1,0,0,1),(4,0,0,-1)]
        report = validate_branches([[(0,0),(3,0)],[(1,0),(4,0)]],records,6,2,2,phases=1)
        self.assertTrue(report['topology_valid'])
        self.assertIn('parallel_emf_mismatch',report['errors'])


if __name__ == '__main__':
    unittest.main()
