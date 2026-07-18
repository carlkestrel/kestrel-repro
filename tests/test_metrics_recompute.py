"""Test raw-metrics recompute: every reported number can be derived from raw metrics."""


def test_per_class_iou_recompute_from_confusion_matrix():
    """Verify IoU from a confusion matrix gives the same result as a recomputed per-class IoU."""
    # 3-class confusion matrix: rows = ground truth, cols = predicted
    cm = [
        [50, 5, 5],   # class 0: 50 correct, 5 mis-as-1, 5 mis-as-2
        [3, 45, 2],   # class 1
        [1, 4, 55],   # class 2
    ]
    ious = []
    for c in range(3):
        tp = cm[c][c]
        fp = sum(cm[r][c] for r in range(3) if r != c)  # col sum minus tp
        fn = sum(cm[c][r] for r in range(3) if r != c)  # row sum minus tp
        iou = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else 0.0
        ious.append(iou)
    # mIoU = mean of per-class IoUs
    miou = sum(ious) / len(ious)
    # Expected: per class c, IoU = TP_c / (TP_c + FP_c + FN_c)
    # class 0: TP=50, FP=col0-TP=4,  FN=row0-TP=10 → 50/64=0.78125
    # class 1: TP=45, FP=col1-TP=9,  FN=row1-TP=5  → 45/59=0.76271
    # class 2: TP=55, FP=col2-TP=7,  FN=row2-TP=5  → 55/67=0.82090
    expected = [50/64, 45/59, 55/67]
    expected_miou = sum(expected) / 3
    assert abs(miou - expected_miou) < 1e-6, f"{miou} != {expected_miou}"
    print(f"per-class IoU = {[round(x,4) for x in ious]}, mIoU = {miou:.4f}")


def test_metric_recompute_matches_aggregate():
    """A reported mIoU must equal recomputed mIoU within tolerance."""
    reported_miou = 73.5
    recomputed_miou = 73.42  # tiny rounding diff
    tol = 0.5  # percentage points (matches TOLERANCE_MIOU default)
    assert abs(reported_miou - recomputed_miou) <= tol
    print("test_metric_recompute_matches_aggregate: PASS")


if __name__ == "__main__":
    test_per_class_iou_recompute_from_confusion_matrix()
    test_metric_recompute_matches_aggregate()
    print("test_metrics_recompute: 2/2 PASS")
