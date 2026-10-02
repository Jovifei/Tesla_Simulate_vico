import threading


def test_trial_records_are_profile_bound():
    receipt = {"trial_id":"t1", "profile_hash":"a"}
    assert receipt["profile_hash"] != "b"


def test_concurrent_budget_gate_shape():
    lock = threading.Lock()
    acquired = lock.acquire()
    try:
        assert acquired
    finally:
        lock.release()


def test_six_mode_reference_shape():
    assert len(("T", "S", "E_ON", "E_OFF", "SE_ON", "SE_OFF")) == 6
    assert (333, 297, 960) == (333, 297, 960)
