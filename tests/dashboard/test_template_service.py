"""Unit tests for dashboard template service."""

from __future__ import annotations

from datetime import datetime

from aspara.catalog import ProjectInfo, RunInfo
from aspara.dashboard.services.template_service import (
    TemplateService,
    create_breadcrumbs,
    render_mustache_response,
)
from aspara.models import RunStatus


class TestCreateBreadcrumbs:
    """Tests for create_breadcrumbs()."""

    def test_single_item(self) -> None:
        items = [{"label": "Home", "url": "/"}]
        result = create_breadcrumbs(items)
        assert len(result) == 1
        assert result[0]["label"] == "Home"
        assert result[0]["is_not_first"] is False
        assert result[0]["is_home"] is True

    def test_multiple_items(self) -> None:
        items = [
            {"label": "Home", "url": "/"},
            {"label": "Project A", "url": "/projects/a"},
        ]
        result = create_breadcrumbs(items)
        assert len(result) == 2
        assert result[0]["is_not_first"] is False
        assert result[1]["is_not_first"] is True

    def test_first_item_gets_home_flag(self) -> None:
        items = [{"label": "Home", "url": "/"}]
        result = create_breadcrumbs(items)
        assert result[0]["is_home"] is True

    def test_existing_is_home_preserved(self) -> None:
        items = [{"label": "Home", "url": "/", "is_home": False}]
        result = create_breadcrumbs(items)
        assert result[0]["is_home"] is False

    def test_does_not_mutate_input(self) -> None:
        items = [{"label": "Home", "url": "/"}]
        original = items[0].copy()
        create_breadcrumbs(items)
        assert items[0] == original

    def test_empty_list(self) -> None:
        assert create_breadcrumbs([]) == []


class TestFormatProjectForTemplate:
    """Tests for TemplateService.format_project_for_template()."""

    def test_basic_project(self) -> None:
        project = ProjectInfo(
            name="my_project",
            run_count=5,
            last_update=datetime(2024, 6, 1, 12, 0, 0),
        )
        result = TemplateService.format_project_for_template(project)
        assert result["name"] == "my_project"
        assert result["run_count"] == 5
        assert result["tags"] == []
        assert result["last_update"] == int(datetime(2024, 6, 1, 12, 0, 0).timestamp() * 1000)
        assert "formatted_last_update" in result

    def test_with_tags(self) -> None:
        project = ProjectInfo(
            name="proj",
            run_count=0,
            last_update=datetime(2024, 6, 1),
        )
        result = TemplateService.format_project_for_template(project, tags=["alpha", "beta"])
        assert result["tags"] == ["alpha", "beta"]

    def test_zero_run_count(self) -> None:
        project = ProjectInfo(
            name="empty",
            run_count=0,
            last_update=datetime(2024, 6, 1),
        )
        result = TemplateService.format_project_for_template(project)
        assert result["run_count"] == 0

    def test_none_last_update(self) -> None:
        project = ProjectInfo(
            name="no_update",
            run_count=1,
            last_update=datetime(2024, 1, 1),
        )
        result = TemplateService.format_project_for_template(project)
        assert result["last_update"] == int(datetime(2024, 1, 1).timestamp() * 1000)
        assert result["formatted_last_update"] != "N/A"


class TestFormatRunForList:
    """Tests for TemplateService.format_run_for_list()."""

    def test_basic_run(self) -> None:
        run = RunInfo(
            name="run_1",
            param_count=3,
            last_update=datetime(2024, 6, 1, 12, 0, 0),
            tags=["x"],
            is_finished=False,
            status=RunStatus.WIP,
        )
        result = TemplateService.format_run_for_list(run)
        assert result["name"] == "run_1"
        assert result["param_count"] == 3
        assert result["tags"] == ["x"]
        assert result["has_tags"] is True
        assert result["is_finished"] is False
        assert result["is_wip"] is True
        assert result["status"] == "wip"

    def test_corrupted_run(self) -> None:
        run = RunInfo(
            name="bad",
            param_count=0,
            is_corrupted=True,
            error_message="File missing",
            status=RunStatus.WIP,
        )
        result = TemplateService.format_run_for_list(run)
        assert result["is_corrupted"] is True
        assert result["error_message"] == "File missing"

    def test_finished_run(self) -> None:
        run = RunInfo(
            name="done",
            param_count=1,
            is_finished=True,
            status=RunStatus.COMPLETED,
        )
        result = TemplateService.format_run_for_list(run)
        assert result["is_finished"] is True
        assert result["is_wip"] is False
        assert result["status"] == "completed"

    def test_no_tags(self) -> None:
        run = RunInfo(
            name="notags",
            param_count=0,
            tags=[],
            status=RunStatus.WIP,
        )
        result = TemplateService.format_run_for_list(run)
        assert result["has_tags"] is False


class TestFormatRunForProjectDetail:
    """Tests for TemplateService.format_run_for_project_detail()."""

    def test_normal_run(self) -> None:
        run = RunInfo(
            name="run_1",
            param_count=1,
            last_update=datetime(2024, 6, 1),
            is_finished=True,
            status=RunStatus.COMPLETED,
        )
        result = TemplateService.format_run_for_project_detail(run)
        assert result is not None
        assert result["name"] == "run_1"
        assert result["is_finished"] is True
        assert result["status"] == "completed"

    def test_corrupted_run_returns_none(self) -> None:
        run = RunInfo(
            name="bad",
            param_count=0,
            is_corrupted=True,
            status=RunStatus.WIP,
        )
        assert TemplateService.format_run_for_project_detail(run) is None


class TestFormatArtifactForTemplate:
    """Tests for TemplateService.format_artifact_for_template()."""

    def test_code_category(self) -> None:
        artifact = {"name": "script.py", "category": "code", "file_size": 100}
        result = TemplateService.format_artifact_for_template(artifact)
        assert result["is_code"] is True
        assert result["is_config"] is False
        assert result["is_model"] is False
        assert result["is_data"] is False
        assert result["is_other"] is False

    def test_none_category_is_other(self) -> None:
        artifact = {"name": "file.bin", "category": None, "file_size": 50}
        result = TemplateService.format_artifact_for_template(artifact)
        assert result["is_other"] is True
        assert result["is_code"] is False

    def test_missing_category_is_other(self) -> None:
        artifact = {"name": "file.bin", "file_size": 50}
        result = TemplateService.format_artifact_for_template(artifact)
        assert result["is_other"] is True

    def test_preserves_original_fields(self) -> None:
        artifact = {"name": "model.pt", "category": "model", "file_size": 999, "description": "best model"}
        result = TemplateService.format_artifact_for_template(artifact)
        assert result["name"] == "model.pt"
        assert result["file_size"] == 999
        assert result["description"] == "best model"
        assert result["is_model"] is True

    def test_all_categories(self) -> None:
        for cat, flag in [
            ("code", "is_code"),
            ("config", "is_config"),
            ("model", "is_model"),
            ("data", "is_data"),
            ("other", "is_other"),
        ]:
            artifact = {"name": "x", "category": cat}
            result = TemplateService.format_artifact_for_template(artifact)
            assert result[flag] is True, f"Failed for category {cat}"


class TestRenderMustacheResponse:
    """Tests for render_mustache_response() common context."""

    def test_exposes_server_max_notes_length_on_body(self) -> None:
        """The server-side max_notes_length is rendered into the layout so
        the client can use it as the single source of truth."""
        html = render_mustache_response("projects_list", {"has_projects": False})
        from aspara.config import get_resource_limits

        expected = f'data-max-notes-length="{get_resource_limits().max_notes_length}"'
        assert expected in html
