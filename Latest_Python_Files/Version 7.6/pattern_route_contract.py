"""Production Pattern route metadata and decision status."""
from dataclasses import dataclass
from fractions import Fraction


def rational_half_belt_translation_pitch(q, poles, layers, phases, *, pattern='TLP'):
    """Return the integer half-belt pitch for the implemented lap construction.

    Reduced q=a/b requires even a, odd b>2, q>1, b|(2m-1), P=2bR,
    and even L>=4. Native m=3 or odd m not divisible by three uses the
    canonical belt model needed by the slot-permutation proof.
    """
    q = Fraction(str(q))
    a, b = q.numerator, q.denominator
    if (q <= 1 or a % 2 or b <= 2 or b % 2 == 0
            or any(type(value) is not int or value <= 0
                   for value in (poles, layers, phases))
            or phases < 3 or phases % 2 == 0
            or (phases > 3 and phases % 3 == 0)
            or (2 * phases - 1) % b or poles % (2 * b)
            or layers < 4 or layers % 2
            or (pattern == 'SLP' and layers != 4)):
        return None
    return a * (2 * phases - 1) // (2 * b)


@dataclass(frozen=True)
class PatternRouteRule:
    """Declarative identity and configuration contract for a Pattern route."""

    rule_id: str
    pattern: str
    route_name: str | None
    pin_profile: tuple[str, ...]
    required_inlet: str
    configuration_capability: str = "regular_unshifted"


@dataclass(frozen=True)
class PatternRouteDecision:
    """Shared route decision; admission separates unsupported from rejected."""

    status: str
    rule_id: str
    reason: str
    pattern: str
    dividers: tuple[int | Fraction, int | Fraction, int | Fraction] | None
    route_name: str | None = None
    pin_profile: tuple[str, ...] = ()
    required_inlet: str = "insert"
    effective_configuration: str = "Regular"
    is_default: bool = False
    admission: str | None = None

    def __post_init__(self):
        if self.admission is None:
            object.__setattr__(
                self, 'admission',
                {'enabled': 'supported', 'candidate': 'Candidate'}.get(
                    self.status, 'rejected'))


PATTERN_ROUTE_RULES = {
    "slp_rational_half_belt_translation": PatternRouteRule(
        "slp_rational_half_belt_translation", "SLP", "slp_rational_half_belt_translation",
        ("ALLP", "SLPP"), "weld"),
    "tlp_rational_half_belt_translation": PatternRouteRule(
        "tlp_rational_half_belt_translation", "TLP", "tlp_rational_half_belt_translation",
        ("ALLP", "CLLP"), "weld"),
    "uwp_half_integer_p2": PatternRouteRule(
        "uwp_half_integer_p2", "UWP", "uwp_half_integer_p2",
        ("ALWP",), "insert", "fractional_wave"),
    "uwp_half_integer_q_pp": PatternRouteRule(
        "uwp_half_integer_q_pp", "UWP", "uwp_half_integer_q_pp",
        ("ALWP",), "insert", "fractional_wave"),
    "bwp_fractional_sector_array": PatternRouteRule(
        "bwp_fractional_sector_array", "BWP", "bwp_fractional_sector_array",
        ("ALWP", "SLPP"), "insert", "fractional_wave"),
    "uwp_fractional_sector_array": PatternRouteRule(
        "uwp_fractional_sector_array", "UWP", "uwp_fractional_sector_array",
        ("ALWP",), "insert", "fractional_wave"),
    "zlp_p2_mirrored": PatternRouteRule(
        "zlp_p2_mirrored", "ZLP", "zlp_p2_mirrored", ("ALLP", "SLPP"), "insert"),
    "zlp_pp_p2_source_cut": PatternRouteRule(
        "zlp_pp_p2_source_cut", "ZLP", "zlp_pp_p2_source_cut",
        ("ALLP", "SLPP"), "insert"),
    "ssp_p2_reflected": PatternRouteRule(
        "ssp_p2_reflected", "SSP", "ssp_p2_reflected", ("ALWP", "SLPP"), "insert"),
    "tsp_q_pp_two": PatternRouteRule(
        "tsp_q_pp_two", "TSP", "tsp_q_pp_two", ("ALWP", "CLWP"), "insert"),
    "tsp_pp_only_q_p2_identity": PatternRouteRule(
        "tsp_pp_only_q_p2_identity", "TSP",
        "tsp_pp_only_q_p2_identity", ("ALWP", "CLWP"), "insert"),
    "tsp_q_only_pair_join": PatternRouteRule(
        "tsp_q_only_pair_join", "TSP", "tsp_q_only_pair_join",
        ("ALWP", "CLWP"), "insert"),
    "tlp_q_only_pair_join": PatternRouteRule(
        "tlp_q_only_pair_join", "TLP", "tlp_q_only_pair_join",
        ("ALLP", "CLLP"), "insert"),
    "tlp_q_pp_q_parent_slices": PatternRouteRule(
        "tlp_q_pp_q_parent_slices", "TLP", "tlp_q_pp_q_parent_slices",
        ("ALLP", "CLLP"), "insert"),
    "tlp_even_gcd_parent_slices": PatternRouteRule(
        "tlp_even_gcd_parent_slices", "TLP", "tlp_even_gcd_parent_slices",
        ("ALLP", "CLLP"), "insert"),
    "tlp_p2_parent_slices": PatternRouteRule(
        "tlp_p2_parent_slices", "TLP", "tlp_p2_parent_slices",
        ("ALLP", "CLLP"), "insert"),
    "tsp_pp_p2_sector": PatternRouteRule(
        "tsp_pp_p2_sector", "TSP", "tsp_pp_p2_sector",
        ("ALWP", "CLWP"), "insert"),
    "tsp_spiral_pass_partition": PatternRouteRule(
        "tsp_spiral_pass_partition", "TSP", "tsp_spiral_pass_partition",
        ("ALWP", "CLWP"), "insert"),
    "cp_q_pp_two": PatternRouteRule(
        "cp_q_pp_two", "CP", "cp_q_pp_two", ("CLWP",), "insert"),
    "zpp_q_pp_two": PatternRouteRule(
        "zpp_q_pp_two", "ZPP", "zpp_q_pp_two", ("SLPP",), "weld"),
    "tlp_q_pp_two": PatternRouteRule(
        "tlp_q_pp_two", "TLP", "tlp_q_pp_two", ("ALLP", "CLLP"), "insert"),
    "tlp_pp_only_two": PatternRouteRule(
        "tlp_pp_only_two", "TLP", "tlp_pp_only_two", ("ALLP", "CLLP"), "insert"),
    "tlp_pp_only_even": PatternRouteRule(
        "tlp_pp_only_even", "TLP", "tlp_pp_only_even", ("ALLP", "CLLP"), "insert"),
    "tlp_pp_p2_short_unit": PatternRouteRule(
        "tlp_pp_p2_short_unit", "TLP", "tlp_pp_p2_short_unit",
        ("ALLP", "CLLP"), "insert"),
    "tlp_q_pp_p2_parent_slices": PatternRouteRule(
        "tlp_q_pp_p2_parent_slices", "TLP",
        "tlp_q_pp_p2_parent_slices", ("ALLP", "CLLP"), "insert"),
    "uwp_short_p2_weld": PatternRouteRule(
        "uwp_short_p2_weld", "UWP", "uwp_short_p2_weld", ("ALWP",), "weld"),
    "ssp_pp_only": PatternRouteRule(
        "ssp_pp_only", "SSP", "pp_only", ("ALWP", "SLPP"), "insert"),
    "slp_pp_only": PatternRouteRule(
        "slp_pp_only", "SLP", "pp_only", ("ALLP", "SLPP"), "insert"),
    "ssp_q_pp_parent_cut": PatternRouteRule(
        "ssp_q_pp_parent_cut", "SSP", "ssp_q_pp_parent_cut",
        ("ALWP", "SLPP"), "insert"),
    "slp_q_pp_parent_cut": PatternRouteRule(
        "slp_q_pp_parent_cut", "SLP", "slp_q_pp_parent_cut",
        ("ALLP", "SLPP"), "insert"),
    "slp_p2_from_reference": PatternRouteRule(
        "slp_p2_from_reference", "SLP", "slp_p2_from_reference",
        ("ALLP", "SLPP"), "insert"),
    "slp_full_q_p2": PatternRouteRule(
        "slp_full_q_p2", "SLP", "slp_full_q_p2",
        ("ALLP", "SLPP"), "insert"),
    "slp_q_pp_p2_parent_cut": PatternRouteRule(
        "slp_q_pp_p2_parent_cut", "SLP", "slp_q_pp_p2_parent_cut",
        ("ALLP", "SLPP"), "insert"),
    "slp_p2_belt_pass_partition": PatternRouteRule(
        "slp_p2_belt_pass_partition", "SLP", "slp_p2_belt_pass_partition",
        ("ALLP", "SLPP"), "insert"),
    "slp_pair_lane_p2": PatternRouteRule(
        "slp_pair_lane_p2", "SLP", "slp_pair_lane_p2",
        ("ALLP", "SLPP"), "insert"),
    "slp_pp_p2_sector": PatternRouteRule(
        "slp_pp_p2_sector", "SLP", "slp_pp_p2_sector",
        ("ALLP", "SLPP"), "insert"),
    "zlp_q_pp": PatternRouteRule(
        "zlp_q_pp", "ZLP", "zlp", ("ALLP", "SLPP"), "insert"),
    "zpp_q_pp_p2": PatternRouteRule(
        "zpp_q_pp_p2", "ZPP", "zpp", ("SLPP",), "weld"),
    "zpp_actual_lane_endpoint_gcd_partition": PatternRouteRule(
        "zpp_actual_lane_endpoint_gcd_partition", "ZPP",
        "zpp_actual_lane_endpoint_gcd_partition", ("SLPP",), "weld"),
    "zpp_pp_only_half_turn": PatternRouteRule(
        "zpp_pp_only_half_turn", "ZPP", "zpp_pp_only_half_turn",
        ("SLPP",), "weld"),
    "zpp_pp_only_indexed_translation": PatternRouteRule(
        "zpp_pp_only_indexed_translation", "ZPP",
        "zpp_pp_only_indexed_translation", ("SLPP",), "weld"),
    "zpp_pp_only_centered_entry_translation": PatternRouteRule(
        "zpp_pp_only_centered_entry_translation", "ZPP",
        "zpp_pp_only_centered_entry_translation", ("SLPP",), "weld"),
    "cp_pp_p2": PatternRouteRule(
        "cp_pp_p2", "CP", "cp", ("CLWP",), "insert"),
    "cp_pp_four_pass_weave": PatternRouteRule(
        "cp_pp_four_pass_weave", "CP", "cp_pp_four_pass_weave",
        ("CLWP",), "insert"),
    "cp_q_only_pair_join": PatternRouteRule(
        "cp_q_only_pair_join", "CP", "cp_q_only_pair_join", ("CLWP",), "insert"),
    "cp_q_pp_q_parent_slices": PatternRouteRule(
        "cp_q_pp_q_parent_slices", "CP", "cp_q_pp_q_parent_slices",
        ("CLWP",), "insert"),
    "cp_gcd_quartet_parent_slices": PatternRouteRule(
        "cp_gcd_quartet_parent_slices", "CP", "cp_gcd_quartet_parent_slices",
        ("CLWP",), "insert"),
    "cp_odd_half_span_parent_slices": PatternRouteRule(
        "cp_odd_half_span_parent_slices", "CP", "cp_odd_half_span_parent_slices",
        ("CLWP",), "insert"),
    "cp_two_layer_tlp_transfer": PatternRouteRule(
        "cp_two_layer_tlp_transfer", "CP", "cp_two_layer_tlp_transfer",
        ("CLWP",), "insert"),
    "cp_q_pp_full_parent_slices": PatternRouteRule(
        "cp_q_pp_full_parent_slices", "CP", "cp_q_pp_full_parent_slices",
        ("CLWP",), "insert"),
    "cp_q_pp_p2_parent_slices": PatternRouteRule(
        "cp_q_pp_p2_parent_slices", "CP", "cp_q_pp_p2_parent_slices",
        ("CLWP",), "insert"),
    "cp_pp_parent_half_translation": PatternRouteRule(
        "cp_pp_parent_half_translation", "CP",
        "cp_pp_parent_half_translation", ("CLWP",), "insert"),
    "cp_pp_sector_slices": PatternRouteRule(
        "cp_pp_sector_slices", "CP", "cp_pp_sector_slices",
        ("CLWP",), "insert"),
    "lpp_pp_default": PatternRouteRule(
        "lpp_pp_default", "LPP", None, ("SLPP",), "weld"),
}

SLP_ROTATED_WELD_ROUTES = frozenset((
    'slp_p2_from_reference', 'slp_pair_lane_p2', 'slp_pp_p2_sector',
    'slp_p2_belt_pass_partition'))


PATTERN_DEFAULT_PIN_PROFILES = {
    "BWP": ("ALWP", "SLPP"),
    "UWP": ("ALWP",),
    "SSP": ("ALWP", "SLPP"),
    "TSP": ("ALWP", "CLWP"),
    "SLP": ("ALLP", "SLPP"),
    "ZLP": ("ALLP", "SLPP"),
    "CP": ("CLWP",),
    "ZPP": ("SLPP",),
    "TLP": ("ALLP", "CLLP"),
    "LPP": ("SLPP",),
}


