from core.logger import Logger


class FakeSignal:
    def __init__(self):
        self.messages = []

    def emit(self, level, message):
        self.messages.append((level, message))


def test_logger_attr_outputs_wrapped_message():
    signal = FakeSignal()
    logger = Logger(signal)

    logger.attr("camera crawl")

    assert signal.messages == [(1, "<<< camera crawl >>>")]
    assert "<<< camera crawl >>>" in logger.logs


def test_logger_writes_to_file(tmp_path):
    logger = Logger(None)
    log_path = tmp_path / "log" / "run.log"

    logger.set_log_file(log_path)
    logger.attr("camera crawl")
    logger.info("done")

    content = log_path.read_text(encoding="utf-8")
    assert "<<< camera crawl >>>" in content
    assert "done" in content
