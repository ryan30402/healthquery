import hashlib
import json

import pytest

from scripts.export_space import EXPORT_FILES, export_space


@pytest.fixture
def source_project(tmp_path):
    project = tmp_path / "project"
    for name in EXPORT_FILES:
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"fixture: {name}\n".encode())
    (project / ".env").write_text("EXAMPLE_SECRET=do-not-copy\n")
    return project


def test_export_has_runtime_and_manifest_but_excludes_unlisted_files(source_project, tmp_path):
    output = export_space(source_project, tmp_path / "space")
    assert not (output / ".env").exists()
    assert not (output / ".git").exists()
    manifest = json.loads((output / "export_manifest.json").read_text())
    for name in EXPORT_FILES:
        assert (output / name).read_bytes() == (source_project / name).read_bytes()
    for name, expected in manifest["file_sha256"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == expected
    assert "app_port: 8000" in (output / "README.md").read_text()
    assert "COPY --chown=appuser models/ ./models/" in (output / "Dockerfile").read_text()


def test_export_refuses_output_inside_repository(source_project):
    with pytest.raises(ValueError, match="outside"):
        export_space(source_project, source_project / "space")
    assert not (source_project / "space").exists()


def test_export_preserves_existing_output(source_project, tmp_path):
    output = tmp_path / "space"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("existing work")
    with pytest.raises(FileExistsError, match="already exists"):
        export_space(source_project, output)
    assert marker.read_text() == "existing work"


def test_export_checks_missing_artifacts_before_creating_output(source_project, tmp_path):
    (source_project / "models/retrieval_index.joblib").unlink()
    output = tmp_path / "space"
    with pytest.raises(FileNotFoundError, match="retrieval_index"):
        export_space(source_project, output)
    assert not output.exists()
