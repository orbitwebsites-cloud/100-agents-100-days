"""Helpers shared by the e-commerce agents (stdlib only; skipped by the registry).

Statistics that inventory, CRO and pricing tools all lean on: the standard normal
CDF and its inverse (Acklam's rational approximation, |error| < 1.2e-9), service
level → z-score, and small validation/rounding conveniences.
"""

from __future__ import annotations

import math

from ...core import ToolError

# Acklam's coefficients for the inverse normal CDF.
_A = (-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02, 1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00)
_B = (-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02, 6.680131188771972e01, -1.328068155288572e01)
_C = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00, -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00)
_D = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00, 3.754408661907416e00)


def norm_cdf(x: float) -> float:
    """P(Z <= x) for the standard normal."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_ppf(p: float) -> float:
    """Inverse standard normal CDF (z such that P(Z <= z) = p)."""
    if not 0.0 < p < 1.0:
        raise ToolError(f"Probability must be strictly between 0 and 1, got {p}")
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q + _C[5]) / ((((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q + _C[5]) / ((((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((_A[0] * r + _A[1]) * r + _A[2]) * r + _A[3]) * r + _A[4]) * r + _A[5]) * q / (((((_B[0] * r + _B[1]) * r + _B[2]) * r + _B[3]) * r + _B[4]) * r + 1)


def z_for_service_level(service_level: float) -> float:
    """Cycle-service-level (0.90 or 90) → safety-factor z. 50% → 0, 95% → 1.645, 99% → 2.326."""
    sl = service_level / 100.0 if service_level > 1.0 else service_level
    if not 0.5 <= sl < 1.0:
        raise ToolError(f"Service level must be between 50% and 99.99%, got {service_level}")
    return norm_ppf(sl)


def as_fraction(value: float, name: str = "rate") -> float:
    """Accept 15 or 0.15 for a percentage-like input; return 0.15."""
    if value < 0:
        raise ToolError(f"{name} cannot be negative (got {value})")
    if value > 100:
        raise ToolError(f"{name} looks wrong: {value}. Pass a percent (15) or a fraction (0.15).")
    return value / 100.0 if value > 1.0 else value


def require_positive(name: str, value: float, allow_zero: bool = False) -> float:
    if value is None or (value < 0 if allow_zero else value <= 0):
        raise ToolError(f"{name} must be {'>= 0' if allow_zero else '> 0'}, got {value!r}")
    return float(value)


def money(x: float) -> float:
    return round(float(x) + 0.0, 2)


def pct(x: float, digits: int = 1) -> float:
    return round(100.0 * x, digits)


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def stdev(xs: list[float], sample: bool = True) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1 if sample else n))


def median(xs: list[float]) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def percentile(xs: list[float], p: float) -> float:
    """Linear-interpolated percentile, p in [0, 100]."""
    if not xs:
        return 0.0
    s = sorted(xs)
    k = (len(s) - 1) * (p / 100.0)
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] + (s[c] - s[f]) * (k - f)
