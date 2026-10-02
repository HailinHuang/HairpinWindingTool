"""Coherent publication unit for a completed winding calculation."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class CalculationState:
    """A read-only bundle installed only after every calculation step succeeds."""

    signature: tuple
    generation: int
    values: MappingProxyType

    @classmethod
    def create(cls, signature, generation, **values):
        return cls(tuple(signature), int(generation), MappingProxyType(dict(values)))

    def install(self, owner):
        for name, value in self.values.items():
            setattr(owner, name, value)
        owner.calculation_state = self
        owner._last_calculation_signature = self.signature
