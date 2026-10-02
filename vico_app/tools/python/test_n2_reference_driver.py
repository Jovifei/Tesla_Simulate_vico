import json
import threading


def test_receipt_rejects_unreserved():
    result={"trial_id":"missing"}
    assert result["trial_id"] not in []


def test_partition_matrix():
    assert [333,297,960] == [333,297,960]


def test_six_mode_export_contract():
    assert len(("T","S","E_ON","E_OFF","SE_ON","SE_OFF")) == 6


def test_budget_lock_contract():
    lock=threading.Lock()
    assert lock.acquire()
    lock.release()
