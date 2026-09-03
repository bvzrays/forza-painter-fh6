"""Orchestration tests for parallel image generation.

These drive ``App._run_parallel_generations`` against a stub that stands in for
the app, so the job pool can be tested without Tk or a real generator.
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path

import pytest

pytest.importorskip("tkinter")

from app import App


class FakeApp:
    """Only the attributes ``_run_parallel_generations`` actually touches."""

    def __init__(self, behaviour):
        self.shutdown_event = threading.Event()
        self.queue = queue.Queue()
        self.lang = "en"
        self.behaviour = behaviour
        self.details = []
        self.started = []
        self._lock = threading.Lock()

    # --- stand-ins for the real methods -------------------------------
    def _record_detail(self, message):
        with self._lock:
            self.details.append(message)

    def _run_one_generation(self, image_path, setting, generator_env, prefix="", track_eta=True):
        with self._lock:
            self.started.append(image_path.name)
        action = self.behaviour[image_path.name]
        if isinstance(action, BaseException):
            raise action
        return action

    # --- helpers ------------------------------------------------------
    def messages(self, kind):
        collected = []
        while True:
            try:
                item_kind, payload = self.queue.get_nowait()
            except queue.Empty:
                return collected
            if item_kind == kind:
                collected.append(payload)


def run(behaviour, jobs=3, shutdown=False):
    images = [Path(name) for name in behaviour]
    fake = FakeApp(behaviour)
    if shutdown:
        fake.shutdown_event.set()
    outcome = App._run_parallel_generations(fake, images, {"path": Path("s.ini")}, {}, jobs)
    return outcome, fake


class TestOutcomeAggregation:
    def test_all_successful(self):
        outcome, _ = run({"a.png": "done", "b.png": "done", "c.png": "done"})
        assert outcome == "done"

    def test_single_failure_fails_the_run(self):
        outcome, _ = run({"a.png": "done", "b.png": "failed", "c.png": "done"})
        assert outcome == "failed"

    def test_stopped_job_stops_the_run(self):
        outcome, _ = run({"a.png": "done", "b.png": "stopped", "c.png": "done"})
        assert outcome == "stopped"

    def test_shutdown_before_start_reports_stopped(self):
        outcome, fake = run({"a.png": "done", "b.png": "done"}, shutdown=True)
        assert outcome == "stopped"
        assert fake.started == []

    def test_more_images_than_jobs_are_all_processed(self):
        behaviour = {f"img{index}.png": "done" for index in range(7)}
        outcome, fake = run(behaviour, jobs=2)
        assert outcome == "done"
        assert sorted(fake.started) == sorted(behaviour)


class TestWorkerExceptions:
    """A job thread must never let an exception escape.

    Regression test: an exception raised outside the subprocess polling block
    (image preprocessing, Popen, output handling) used to kill the runner
    thread without recording an outcome, and the run then reported success for
    an image that was never generated.
    """

    def test_exception_fails_the_run_instead_of_reporting_done(self):
        outcome, _ = run({"a.png": "done", "b.png": OSError("disk on fire"), "c.png": "done"})
        assert outcome == "failed"

    def test_exception_is_logged_with_the_image_name(self):
        _, fake = run({"a.png": "done", "b.png": OSError("disk on fire")})
        logs = fake.messages("log")
        assert any("b.png" in line and "disk on fire" in line for line in logs), logs

    def test_exception_reaches_the_detailed_log(self):
        _, fake = run({"a.png": ValueError("bad settings")})
        assert any("GENERATION EXCEPTION" in detail and "bad settings" in detail
                   for detail in fake.details), fake.details

    def test_every_image_still_reports_progress(self):
        behaviour = {"a.png": "done", "b.png": OSError("nope"), "c.png": "done"}
        _, fake = run(behaviour)
        assert fake.messages("progress")[-1] == "3/3 images done"

    def test_other_jobs_still_run_after_one_raises(self):
        behaviour = {"a.png": "done", "b.png": RuntimeError("nope"), "c.png": "done"}
        _, fake = run(behaviour, jobs=2)
        assert sorted(fake.started) == ["a.png", "b.png", "c.png"]

    def test_preprocess_error_is_not_special_cased(self):
        from utils import PreprocessError

        outcome, fake = run({"a.png": PreprocessError("unsupported mode")})
        assert outcome == "failed"
        assert any("unsupported mode" in line for line in fake.messages("log"))


class TestIncompleteResults:
    def test_missing_outcome_never_reports_done(self):
        # A BaseException is deliberately outside the `except Exception` guard,
        # so the runner dies without leaving an outcome. The backstop has to
        # catch the short result set rather than reporting success.
        outcome, fake = run({"a.png": "done", "b.png": KeyboardInterrupt(), "c.png": "done"})
        assert outcome == "failed"
        assert any("2 of 3" in line for line in fake.messages("log"))
