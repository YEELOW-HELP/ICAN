from __future__ import annotations

import inspect

from fastapi.routing import APIRoute

from app.mongo_runtime import admin_match


def _route(path: str, method: str) -> APIRoute:
    for route in admin_match.router.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route
    raise AssertionError(f"missing {method} {path}")


def _dependency_names(route: APIRoute) -> set[str]:
    return {dep.call.__name__ for dep in route.dependant.dependencies if dep.call is not None}


def test_entry_requirement_modes_are_explicit_and_backward_safe():
    assert admin_match.ENTRY_MODES == {"standard", "open_entry", "incomplete"}
    assert admin_match._mode({}) == "incomplete"
    assert admin_match._mode({"entry_requirements_mode": "unknown"}) == "incomplete"
    assert admin_match._mode({"entry_requirements_mode": "standard"}) == "standard"
    assert admin_match._mode({"entry_requirements_mode": "open_entry"}) == "open_entry"


def test_manager_can_preview_and_search_skills_but_not_edit_career_kb():
    preview = _route("/v1/mnp/admin/match/preview", "POST")
    search = _route("/v1/mnp/admin/skills/search", "GET")
    editor_read = _route("/v1/mnp/admin/careers/{career_id}/editor", "GET")
    editor_write = _route("/v1/mnp/admin/careers/{career_id}/editor", "PUT")
    verify = _route("/v1/mnp/admin/careers/{career_id}/verify", "POST")

    assert "current_staff" in _dependency_names(preview)
    assert "current_staff" in _dependency_names(search)
    assert "privileged_staff" in _dependency_names(editor_read)
    assert "privileged_staff" in _dependency_names(editor_write)
    assert "privileged_staff" in _dependency_names(verify)


def test_preview_reuses_existing_matching_engine_pure_scoring():
    source = inspect.getsource(admin_match.match_preview)
    assert "compute_weighted_coverage_fit" in source
    assert "RequirementInput" in source
    assert "PersonLevelInput" in source
    assert "score_percent" in source


def test_incomplete_mode_never_gets_automatic_score():
    source = inspect.getsource(admin_match.match_preview)
    incomplete_block = source.split('if mode == "incomplete":', 1)[1].split('elif mode == "open_entry"', 1)[0]
    assert 'readiness = "Недостатньо даних"' in incomplete_block
    assert "score = None" in incomplete_block


def test_preview_is_non_persistent_for_person_kb():
    source = inspect.getsource(admin_match.match_preview)
    assert '"temporary_profile_saved": False' in source
    assert "mnp_persons.insert" not in source
    assert "mnp_persons.update" not in source
    assert "mnp_person_skills.insert" not in source


def test_skill_editor_resolves_existing_dictionary_and_rejects_duplicates():
    resolver = inspect.getsource(admin_match._resolve_skill)
    save = inspect.getsource(admin_match.save_career_editor)
    assert "mnp_skills" in resolver
    assert "mnp_skill_aliases" in resolver
    assert "Duplicate skill in career requirements" in save
    assert "Unknown skill" in save


def test_required_admin_match_routes_exist():
    expected = {
        ("GET", "/v1/mnp/admin/skills/search"),
        ("GET", "/v1/mnp/admin/careers/completeness"),
        ("GET", "/v1/mnp/admin/careers/{career_id}/editor"),
        ("PUT", "/v1/mnp/admin/careers/{career_id}/editor"),
        ("POST", "/v1/mnp/admin/careers/{career_id}/verify"),
        ("GET", "/v1/mnp/admin/careers/next-review"),
        ("POST", "/v1/mnp/admin/match/preview"),
    }
    actual = {(method, route.path) for route in admin_match.router.routes if isinstance(route, APIRoute) for method in route.methods}
    assert expected <= actual
