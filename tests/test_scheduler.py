"""Tests for the scheduler module and scheduler service."""

from unittest.mock import patch, MagicMock

import pytest

from app.scheduler import configure_scheduler, get_scheduler_info, scheduler


class TestSchedulerConfiguration:
    def test_configure_creates_job(self):
        configure_scheduler(hour=10, minute=0, user_id=1)
        job = scheduler.get_job("daily_linkedin_post")
        assert job is not None
        assert job.name == "Daily LinkedIn Post"

    def test_configure_replaces_existing_job(self):
        configure_scheduler(hour=10, minute=0, user_id=1)
        configure_scheduler(hour=11, minute=30, user_id=2)
        job = scheduler.get_job("daily_linkedin_post")
        assert job is not None
        # Only one job should exist
        all_jobs = scheduler.get_jobs()
        linkedin_jobs = [j for j in all_jobs if j.id == "daily_linkedin_post"]
        assert len(linkedin_jobs) == 1

    def test_max_instances_is_one(self):
        configure_scheduler(hour=10, minute=0, user_id=1)
        job = scheduler.get_job("daily_linkedin_post")
        assert job.max_instances == 1

    def test_misfire_grace_time(self):
        configure_scheduler(hour=10, minute=0, user_id=1)
        job = scheduler.get_job("daily_linkedin_post")
        assert job.misfire_grace_time == 3600


class TestSchedulerInfo:
    def test_returns_dict(self):
        info = get_scheduler_info()
        assert isinstance(info, dict)
        assert "running" in info
        assert "next_run" in info
        assert "job_exists" in info

    def test_job_exists_after_configure(self):
        configure_scheduler(hour=10, minute=0, user_id=1)
        info = get_scheduler_info()
        assert info["job_exists"] is True
