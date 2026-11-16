from text2sql_agent.prefilter import check_question
from text2sql_agent.sanitizer import sanitize


def test_prefilter_allows_normal_question():
    assert check_question("How many schools are in Alameda county?") is None


def test_prefilter_blocks_empty_long_and_control_chars():
    assert check_question("   ") is not None
    assert check_question("a" * 5000) is not None
    assert check_question("hello\x00world") is not None


def test_sanitizer_removes_paths_tracebacks_and_secrets():
    text = (
        "Answer: 42. Read from C:\\data\\db\\shop.sqlite and /home/user/app/config.py. "
        "api_key=abc123 postgres://admin:pass@10.0.0.1/db"
    )
    clean = sanitize(text)
    assert "Answer: 42." in clean
    assert "C:\\data" not in clean
    assert "/home/user" not in clean
    assert "abc123" not in clean
    assert "admin:pass" not in clean


def test_sanitizer_removes_traceback():
    text = 'Sorry.\nTraceback (most recent call last):\n  File "x.py", line 1\nValueError: boom'
    assert sanitize(text).startswith("Sorry.")
    assert "ValueError" not in sanitize(text)


def test_sanitizer_keeps_normal_text():
    text = "There are 12 schools with a 3/4 ratio, average 1.5."
    assert sanitize(text) == text
