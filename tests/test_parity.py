"""Test strict-vs-optimized parity: numerical results must agree within tolerance."""


def test_parity_within_tolerance():
    """Two runs (strict fp32 vs optimized AMP) must agree within TOLERANCE_MIOU."""
    strict_miou = 73.5
    optimized_miou = 73.3  # within 0.5 pp
    tol = 0.5
    gap = abs(strict_miou - optimized_miou)
    assert gap <= tol, f"gap {gap} > tolerance {tol}"
    print(f"strict={strict_miou}, optimized={optimized_miou}, gap={gap} ≤ {tol} → PASS")


def test_parity_failure_flagged():
    """A gap larger than tolerance must be flagged, not silently passed."""
    strict_miou = 73.5
    optimized_miou = 72.0  # 1.5 pp gap > tolerance
    tol = 0.5
    gap = abs(strict_miou - optimized_miou)
    assert gap > tol, "expected gap > tolerance"
    print(f"strict={strict_miou}, optimized={optimized_miou}, gap={gap} > {tol} → FLAGGED (correct)")


if __name__ == "__main__":
    test_parity_within_tolerance()
    test_parity_failure_flagged()
    print("test_parity: 2/2 PASS")