from types import SimpleNamespace

from app.models import ReadingStatus, SectionStatus
from app.services.worker import compute_reading_status


def _sections(*statuses: SectionStatus):
    return [SimpleNamespace(status=status) for status in statuses]


def test_all_ready():
    assert compute_reading_status(_sections(SectionStatus.ready, SectionStatus.ready)) == (
        ReadingStatus.ready
    )


def test_all_failed():
    assert compute_reading_status(_sections(SectionStatus.failed, SectionStatus.failed)) == (
        ReadingStatus.failed
    )


def test_ready_plus_failed_is_partial():
    assert compute_reading_status(_sections(SectionStatus.ready, SectionStatus.failed)) == (
        ReadingStatus.partial
    )


def test_pending_only_is_queued():
    assert compute_reading_status(_sections(SectionStatus.pending, SectionStatus.pending)) == (
        ReadingStatus.queued
    )


def test_processing_is_processing():
    assert compute_reading_status(
        _sections(SectionStatus.processing, SectionStatus.pending)
    ) == ReadingStatus.processing


def test_ready_plus_pending_is_processing():
    assert compute_reading_status(
        _sections(SectionStatus.ready, SectionStatus.pending)
    ) == ReadingStatus.processing


def test_empty_sections_failed():
    assert compute_reading_status([]) == ReadingStatus.failed
