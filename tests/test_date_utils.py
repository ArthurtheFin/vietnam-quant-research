from src.utils.date_utils import to_ssi_date, chunk_date_range


def test_to_ssi_date():
    assert to_ssi_date('2026-06-18') == '18/06/2026'


def test_chunk_date_range():
    chunks = list(chunk_date_range('2026-01-01', '2026-02-05', chunk_days=30))
    assert chunks == [('01/01/2026', '30/01/2026'), ('31/01/2026', '05/02/2026')]
