from pathlib import Path

from policy.repo_edit_policy import RepoEditPolicy
from services.repo_edit_orchestrator import EditPlan, PatchHunk, RepoTargetContext


def test_policy_blocks_sensitive_and_ci_without_allow(tmp_path: Path) -> None:
    policy = RepoEditPolicy()
    context = RepoTargetContext(
        owner="acme",
        repo="demo",
        base_branch="main",
        allow_paths=["backend/", ".github/"],
        constraints={"audit_log_path": str(tmp_path / "audit.log")},
    )
    plan = EditPlan(
        files_to_modify=[".github/workflows/deploy.yml", "backend/.env"],
        patch_hunks=[
            PatchHunk(file_path=".github/workflows/deploy.yml", content="name: ci\n"),
            PatchHunk(file_path="backend/.env", content="TOKEN=abc\n"),
        ],
        rationale="test",
    )

    decision = policy.evaluate(plan, context)

    assert not decision.allowed
    assert "needs-human-review" in decision.labels
    assert any("Sensitive/credential-like" in reason for reason in decision.rejection_reasons)


def test_policy_requires_confirmation_for_high_risk(tmp_path: Path) -> None:
    policy = RepoEditPolicy()
    context = RepoTargetContext(
        owner="acme",
        repo="demo",
        base_branch="main",
        allow_paths=["backend/"],
        constraints={"audit_log_path": str(tmp_path / "audit.log")},
    )
    plan = EditPlan(
        files_to_modify=["backend/auth/service.py"],
        patch_hunks=[PatchHunk(file_path="backend/auth/service.py", content="print('ok')\n")],
        rationale="test",
    )

    decision = policy.evaluate(plan, context)

    assert not decision.allowed
    assert decision.requires_confirmation is True
    assert "high-risk" in decision.labels


def test_policy_audit_log_written(tmp_path: Path) -> None:
    policy = RepoEditPolicy()
    log_path = tmp_path / "policy.log"
    context = RepoTargetContext(
        owner="acme",
        repo="demo",
        base_branch="main",
        allow_paths=["backend/"],
        constraints={"audit_log_path": str(log_path), "user_confirmed_high_risk": True},
    )
    plan = EditPlan(
        files_to_modify=["backend/auth/service.py"],
        patch_hunks=[PatchHunk(file_path="backend/auth/service.py", content="print('ok')\n")],
        rationale="test",
    )

    decision = policy.evaluate(plan, context)

    assert decision.allowed
    assert log_path.exists()
    assert '"risk_score"' in log_path.read_text(encoding="utf-8")
