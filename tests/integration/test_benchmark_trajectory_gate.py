from evaluation.gate import compute_gate_report
from models.evaluation import ValidationStatus


def test_gate_pass_at_ninety_percent():
    statuses = [ValidationStatus.COMPLETE] * 9 + [ValidationStatus.INCOMPLETE]
    report = compute_gate_report(statuses, threshold=0.9)
    assert report.total == 10
    assert report.gate_passed is True
    assert report.complete == 9


def test_gate_fail_below_threshold():
    statuses = [ValidationStatus.COMPLETE] * 8 + [ValidationStatus.INCOMPLETE] * 2
    report = compute_gate_report(statuses, threshold=0.9)
    assert report.gate_passed is False
