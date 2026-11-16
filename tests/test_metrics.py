from evals.metrics import compute, same_result


def test_same_result_ignores_order_and_duplicates():
    assert same_result([(1, "a"), (2, "b")], [(2, "b"), (1, "a"), (1, "a")])
    assert not same_result([(1,)], [(2,)])
    assert not same_result([(1, "a")], [(1,)])  # coluna a mais muda o resultado


def record(status, correct, difficulty="simple"):
    usage = {
        "agent": {
            "calls": 3,
            "input_tokens": 100,
            "output_tokens": 10,
            "cached_tokens": 0,
            "reasoning_tokens": 0,
            "seconds": 2.0,
        }
    }
    return {"status": status, "ex_correct": correct, "difficulty": difficulty, "usage": usage, "seconds": 2.0}


def test_compute_with_and_without_judge():
    records = [
        record("answered", True),
        record("answered", False),  # erro que passou
        record("rejected_by_judge", False),  # erro barrado
        record("rejected_by_judge", True),  # acerto barrado à toa
        record("blocked_guardrail", False),
    ]
    metrics = compute(records)

    assert metrics["ex"] == 2 / 5
    assert metrics["without_judge"]["coverage"] == 4 / 5
    assert metrics["without_judge"]["accuracy_answered"] == 2 / 4
    assert metrics["with_judge"]["coverage"] == 2 / 5
    assert metrics["with_judge"]["accuracy_answered"] == 1 / 2
    assert metrics["with_judge"]["correct_shown"] == 1 / 5

    confusion = metrics["judge_confusion"]
    assert (confusion["caught_wrong"], confusion["blocked_right"]) == (1, 1)
    assert (confusion["passed_wrong"], confusion["passed_right"]) == (1, 1)
    assert confusion["precision"] == 0.5
    assert confusion["recall"] == 0.5
