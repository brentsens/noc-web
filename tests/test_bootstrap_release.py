import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

import pytest

from scripts.bootstrap.acquire_release import (
    BootstrapError,
    BootstrapStateRecord,
    acquire_verified_release,
    handoff_verified_release,
    download_release_assets,
    read_state_record,
    resolve_installation_state,
    safe_install_root,
    stage_verified_release,
    validate_archive,
    verify_provenance,
    write_state_record,
)
from scripts.bootstrap.handoff import HandoffError
from scripts.bootstrap.release_manifest import ManifestError, ReleaseEntry, load_manifest, validate_manifest
from scripts.bootstrap.windows_preflight import WindowsContext, assess


REPOSITORY = "brentsens/noc-web"
TAG = "v1.0.3"
SIGNER = "brentsens/noc-web/.github/workflows/release.yml"


def _release(archive="noc-web-v1.0.3.tar.gz", digest="0" * 64, **changes):
    values = {
        "repository": REPOSITORY, "tag": TAG, "archive": archive,
        "checksum": "noc-web-v1.0.3.sha256", "sha256": digest, "signer_workflow": SIGNER,
    }
    values.update(changes)
    return ReleaseEntry(**values)


def _manifest(**changes):
    value = {
        "schemaVersion": 1,
        "targetDistribution": "Ubuntu",
        "releaseAssets": {
            "repository": REPOSITORY, "tag": TAG, "archive": "noc-web-v1.0.3.tar.gz",
            "checksum": "noc-web-v1.0.3.sha256",
            "sha256": "a" * 64, "signerWorkflow": SIGNER,
        },
        "brandingAsset": "assets/windows/sesami-noc-operations.png",
        "toolEntries": [],
    }
    value.update(changes)
    return value


def _archive(path: Path, *, unsafe=False, missing=False):
    required = (
        "requirements.txt", "backend/app.py", "scripts/install_runtime.py",
        "scripts/windows/install-shortcut.ps1", "scripts/windows/launch-hidden.vbs.in",
        "systemd/noc-web.service.in",
    )
    with tarfile.open(path, "w:gz") as archive:
        for name in (() if missing else required):
            payload = name.encode()
            member = tarfile.TarInfo(f"noc-web-v1.0.3/{name}")
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))
        if unsafe:
            payload = b"unsafe"
            member = tarfile.TarInfo("../outside")
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))


def _installed_release(root: Path) -> Path:
    for name in (
        "requirements.txt", "backend/app.py", "scripts/install_runtime.py",
        "scripts/windows/install-shortcut.ps1", "scripts/windows/launch-hidden.vbs.in",
        "systemd/noc-web.service.in",
    ):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    return root


def _checksums(path: Path, archive: Path, digest: str | None = None):
    path.write_text(f"{digest or hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n")


def test_manifest_pins_the_approved_noc_web_release_and_rejects_trust_changes():
    release = validate_manifest(_manifest()).application
    assert release == _release(digest="a" * 64)
    assert release.archive_url == (
        "https://github.com/brentsens/noc-web/releases/download/v1.0.3/noc-web-v1.0.3.tar.gz"
    )
    for changed in (
        {"repository": "attacker/noc-web", "signerWorkflow": "attacker/noc-web/.github/workflows/release.yml"},
        {"tag": "main"},
        {"archive": "noc-web-v1.0.3.zip"}, {"signerWorkflow": ".github/workflows/release.yml"},
    ):
        manifest = _manifest()
        manifest["releaseAssets"].update(changed)
        with pytest.raises(ManifestError):
            validate_manifest(manifest)
    with pytest.raises(ManifestError):
        validate_manifest(_manifest(releaseAssets={}))


def test_bundled_manifest_contains_the_approved_noc_web_v103_anchor():
    manifest = load_manifest(
        Path(__file__).parents[1] / "packaging" / "windows" / "bootstrap-manifest.json"
    )
    assert manifest.application == _release(
        digest="ab55b3d776d760db3ea758d80b9fc7218ef3bd33a0723589d73b7f0a2171370f"
    )
    tool = manifest.tool("nocTools")
    assert tool is not None
    assert tool.version == "v1.0.1"
    assert tool.compatibility == "noc-inv-contract=1"
    assert tool.signer_workflow == "brentsens/noc-tools/.github/workflows/noc-release.yml"


def test_acquires_verifies_and_atomically_promotes_an_approved_tarball(tmp_path, monkeypatch):
    archive = tmp_path / "noc-web-v1.0.3.tar.gz"
    checksums = tmp_path / "noc-web-v1.0.3.sha256"
    _archive(archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    _checksums(checksums, archive)
    release = _release(digest=digest)
    payloads = {release.archive_url: archive.read_bytes(), release.checksum_url: checksums.read_bytes()}

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_):
            self.close()

    def opener(url, timeout):
        assert timeout == 30
        return Response(payloads[url])

    calls = []

    def verified(path, actual_release, *, verifier):
        assert path.name == release.archive
        assert actual_release == release
        assert verifier == "gh"
        calls.append(True)

    monkeypatch.setattr("scripts.bootstrap.acquire_release.verify_provenance", verified)
    root = tmp_path / "installed"
    root.mkdir()
    (root / "prior").write_text("preserved")
    record = acquire_verified_release(
        release, install_root=root, record_path=tmp_path / "state" / "record.json", opener=opener,
    )

    assert calls == [True]
    assert record.provenance_verified and record.archive_validated
    assert (root / "backend" / "app.py").is_file()
    assert (tmp_path / "installed.previous" / "prior").read_text() == "preserved"
    assert json.loads((tmp_path / "state" / "record.json").read_text())["release_id"] == TAG


def test_trust_and_download_failures_do_not_extract_or_replace_prior_release(tmp_path, monkeypatch):
    archive = tmp_path / "noc-web-v1.0.3.tar.gz"
    checksums = tmp_path / "noc-web-v1.0.3.sha256"
    _archive(archive)
    _checksums(checksums, archive, "0" * 64)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    release = _release(digest=digest)
    root = tmp_path / "installed"
    root.mkdir()
    (root / "prior").write_text("preserved")
    with pytest.raises(BootstrapError):
        stage_verified_release(
            archive, release=release, install_root=root, record_path=tmp_path / "record",
            checksums=checksums, provenance_verified=True,
        )
    assert (root / "prior").read_text() == "preserved"

    def unavailable(*_, **__):
        raise OSError("network")

    with pytest.raises(BootstrapError):
        download_release_assets(release, tmp_path / "download", opener=unavailable)
    monkeypatch.setattr(
        "scripts.bootstrap.acquire_release.verify_provenance",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(BootstrapError()),
    )
    with pytest.raises(BootstrapError):
        acquire_verified_release(release, install_root=root, record_path=tmp_path / "record", opener=unavailable)
    assert (root / "prior").read_text() == "preserved"


def test_malformed_or_unsafe_archives_and_paths_fail_closed(tmp_path):
    archive = tmp_path / "noc-web-v1.0.3.tar.gz"
    _archive(archive, unsafe=True)
    with pytest.raises(BootstrapError):
        validate_archive(archive)
    _archive(archive, missing=True)
    with pytest.raises(BootstrapError):
        validate_archive(archive)
    with pytest.raises(BootstrapError):
        safe_install_root(tmp_path / ".." / "..")


def test_attestation_verification_requires_repository_tag_and_signer(monkeypatch, tmp_path):
    archive = tmp_path / "noc-web-v1.0.3.tar.gz"
    archive.write_bytes(b"fixture")
    command = []

    def run(actual, **kwargs):
        command.extend(actual)
        assert kwargs["shell"] is False
        assert kwargs["timeout"] == 60
        return subprocess.CompletedProcess(actual, 0)

    monkeypatch.setattr("scripts.bootstrap.acquire_release.subprocess.run", run)
    verify_provenance(archive, _release())
    assert command == [
        "gh", "attestation", "verify", str(archive), "--repo", REPOSITORY,
        "--signer-workflow", SIGNER, "--source-ref", "refs/tags/v1.0.3",
    ]

    monkeypatch.setattr(
        "scripts.bootstrap.acquire_release.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1),
    )
    with pytest.raises(BootstrapError):
        verify_provenance(archive, _release())


def test_attestation_verifier_has_bounded_controlled_environment(monkeypatch, tmp_path):
    archive = tmp_path / "noc-web-v1.0.3.tar.gz"
    archive.write_bytes(b"fixture")
    invocation = {}

    def run(actual, **kwargs):
        invocation.update(command=actual, **kwargs)
        return subprocess.CompletedProcess(actual, 0)

    monkeypatch.setattr("scripts.bootstrap.acquire_release.subprocess.run", run)
    verify_provenance(archive, _release())

    assert invocation["shell"] is False
    assert invocation["timeout"] == 60
    assert invocation["env"]["PATH"] == "/usr/local/bin:/usr/bin:/bin"
    assert set(invocation["env"]) == {"PATH", "HOME"}
    with pytest.raises(BootstrapError):
        verify_provenance(archive, _release(), verifier="/untrusted/gh")


def test_feature011_handoff_failure_restores_the_prior_verified_release(tmp_path, monkeypatch):
    root = _installed_release(tmp_path / "installed")
    previous = _installed_release(tmp_path / "installed.previous")
    (root / "release-marker").write_text("new")
    (previous / "release-marker").write_text("previous")
    monkeypatch.setattr(
        "scripts.bootstrap.acquire_release.create_verified_venv_and_install",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(HandoffError("failure")),
    )

    with pytest.raises(BootstrapError, match="FEATURE011_HANDOFF_FAILED"):
        handoff_verified_release(root, distribution="Ubuntu")

    assert (root / "release-marker").read_text() == "previous"


def _state(release, root, *, state="ready", result="READY", **changes):
    values = {
        "schema_version": 1,
        "release_id": release.tag,
        "release_version": release.tag[1:],
        "repository": release.repository,
        "install_root": str(root),
        "archive_sha256": release.sha256,
        "state": state,
        "last_result": result,
        "updated_at": "2026-11-01T00:00:00Z",
    }
    values.update(changes)
    return BootstrapStateRecord(**values)


def _stage_release(tmp_path, release):
    archive = tmp_path / release.archive
    checksums = tmp_path / release.checksum
    _archive(archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    release = _release(digest=digest)
    _checksums(checksums, archive)
    root = tmp_path / "installed"
    state = tmp_path / "state" / "installation-state.json"
    stage_verified_release(
        archive, release=release, install_root=root, record_path=tmp_path / "record.json",
        checksums=checksums, provenance_verified=True, state_path=state,
    )
    return release, archive, checksums, root, state


def test_state_record_classifies_current_older_and_incompatible_installations(tmp_path):
    release, _, _, root, state = _stage_release(tmp_path, _release())
    assert read_state_record(state).state == "ready"
    assert resolve_installation_state(state, release, install_root=root).classification == "current"

    older = _state(release, root, release_id="v1.0.2", release_version="1.0.2",
                   archive_sha256="1" * 64)
    write_state_record(state, older)
    assert resolve_installation_state(state, release, install_root=root).classification == "older"

    incompatible = _state(release, root, release_id="v1.0.4", release_version="1.0.4",
                          archive_sha256="2" * 64)
    write_state_record(state, incompatible)
    assert resolve_installation_state(state, release, install_root=root).classification == "incompatible"


def test_state_record_classifies_interrupted_failed_and_corrupt_without_touching_install(tmp_path):
    release, _, _, root, state = _stage_release(tmp_path, _release())
    operator_data = root / "operator-data"
    operator_data.write_text("preserved")

    write_state_record(state, _state(release, root, state="handoff", result="HANDOFF_PENDING"))
    assert resolve_installation_state(state, release, install_root=root).classification == "interrupted"

    write_state_record(state, _state(release, root, state="failed", result="HANDOFF_FAILED"))
    assert resolve_installation_state(state, release, install_root=root).classification == "failed"

    state.write_text('{"repository": "brentsens/noc-web"}')
    assert resolve_installation_state(state, release, install_root=root).classification == "corrupt"
    assert operator_data.read_text() == "preserved"


@pytest.mark.parametrize(
    "missing",
    ("scripts/install_runtime.py", "scripts/windows/launch-hidden.vbs.in"),
)
def test_missing_runtime_or_launcher_is_corrupt_without_mutating_operator_data(tmp_path, missing):
    release, _, _, root, state = _stage_release(tmp_path, _release())
    (root / missing).unlink()
    (root / "data").mkdir()
    authentication = root / "data" / "authentication.json"
    authentication.write_text("operator authentication")

    resolution = resolve_installation_state(state, release, install_root=root)

    assert resolution.classification == "corrupt"
    assert authentication.read_text() == "operator authentication"


def test_declined_newer_release_confirmation_does_not_mutate_or_report_ready(tmp_path):
    release, _, _, root, state = _stage_release(tmp_path, _release())
    (root / "data").mkdir()
    (root / "data" / "authentication.json").write_text("operator authentication")
    before = {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    before_state = state.read_bytes()
    context = WindowsContext(
        wsl_available=True,
        distributions=("Ubuntu",),
        requested_distribution="Ubuntu",
        windows_user="operator",
        profile_path=r"C:\Users\operator",
        desktop_path=r"C:\Users\operator\Desktop",
        linux_user="operator",
        linux_uid=1000,
        systemd_available=True,
        permission_available=True,
        confirmed=False,
        source_verified=True,
    )

    assert assess(context) == "CONFIRMATION_DECLINED"
    assert state.read_bytes() == before_state
    assert {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    } == before


def test_repeated_current_release_preserves_valid_install_and_operator_data(tmp_path):
    release, archive, checksums, root, state = _stage_release(tmp_path, _release())
    operator_data = root / "operator-data"
    operator_data.write_text("preserved")
    authentication = root / "data" / "authentication.json"
    authentication.parent.mkdir()
    authentication.write_text("operator authentication")

    stage_verified_release(
        archive, release=release, install_root=root, record_path=tmp_path / "record.json",
        checksums=checksums, provenance_verified=True, state_path=state,
    )

    assert resolve_installation_state(state, release, install_root=root).classification == "current"
    assert operator_data.read_text() == "preserved"
    assert authentication.read_text() == "operator authentication"
    assert not (tmp_path / "installed.previous").exists()


def test_interrupted_same_release_recovers_without_replacing_valid_content(tmp_path):
    release, archive, checksums, root, state = _stage_release(tmp_path, _release())
    operator_data = root / "data"
    operator_data.mkdir()
    (operator_data / "noc.json").write_text("preserved")
    write_state_record(state, _state(release, root, state="handoff", result="HANDOFF_PENDING"))
    record_path = tmp_path / "recovered-record.json"

    stage_verified_release(
        archive, release=release, install_root=root, record_path=record_path,
        checksums=checksums, provenance_verified=True, state_path=state,
    )

    assert read_state_record(state).state == "ready"
    assert json.loads(record_path.read_text())["release_id"] == release.tag
    assert (operator_data / "noc.json").read_text() == "preserved"
    assert not (tmp_path / "installed.previous").exists()


def test_same_release_repair_replaces_missing_app_content_but_preserves_feature011_content(tmp_path):
    release, archive, checksums, root, state = _stage_release(tmp_path, _release())
    (root / "backend" / "app.py").unlink()
    (root / "data").mkdir()
    (root / "data" / "noc.json").write_text("preserved")
    (root / "data" / "authentication.json").write_text("operator authentication")
    (root / "runtime.json").write_text("runtime")
    (root / ".venv").mkdir()
    (root / ".venv" / "marker").write_text("venv")

    stage_verified_release(
        archive, release=release, install_root=root, record_path=tmp_path / "record.json",
        checksums=checksums, provenance_verified=True, state_path=state,
    )

    assert (root / "backend" / "app.py").is_file()
    assert (root / "data" / "noc.json").read_text() == "preserved"
    assert (root / "data" / "authentication.json").read_text() == "operator authentication"
    assert (root / "runtime.json").read_text() == "runtime"
    assert (root / ".venv" / "marker").read_text() == "venv"
    assert (tmp_path / "installed.previous" / "data" / "noc.json").read_text() == "preserved"


def test_approved_newer_release_replaces_only_application_content_once(tmp_path):
    current, _, _, root, state = _stage_release(tmp_path, _release())
    (root / "backend" / "app.py").write_text("old application")
    (root / "data").mkdir()
    (root / "data" / "authentication.json").write_text("operator authentication")
    (root / "runtime.json").write_text("runtime")
    (root / ".venv").mkdir()
    (root / ".venv" / "marker").write_text("venv")
    archive = tmp_path / "noc-web-v1.0.4.tar.gz"
    checksums = tmp_path / "noc-web-v1.0.4.sha256"
    _archive(archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    _checksums(checksums, archive)
    newer = ReleaseEntry(
        repository=current.repository,
        tag="v1.0.4",
        archive=archive.name,
        checksum=checksums.name,
        sha256=digest,
        signer_workflow=current.signer_workflow,
    )

    assert resolve_installation_state(state, newer, install_root=root).classification == "older"
    stage_verified_release(
        archive,
        release=newer,
        install_root=root,
        record_path=tmp_path / "record.json",
        checksums=checksums,
        provenance_verified=True,
        state_path=state,
    )

    assert (root / "backend" / "app.py").read_text() == "backend/app.py"
    assert (root / "data" / "authentication.json").read_text() == "operator authentication"
    assert (root / "runtime.json").read_text() == "runtime"
    assert (root / ".venv" / "marker").read_text() == "venv"
    assert len(list(tmp_path.glob("installed.previous"))) == 1
    assert read_state_record(state).release_id == "v1.0.4"


def test_failed_repair_preserves_existing_release_and_redacts_malformed_state(tmp_path, monkeypatch):
    release, archive, checksums, root, state = _stage_release(tmp_path, _release())
    (root / "data").mkdir()
    (root / "data" / "authentication.json").write_text("operator authentication")
    (root / "runtime.json").write_text("runtime")
    (root / ".venv").mkdir()
    (root / ".venv" / "marker").write_text("venv")
    state.write_text('{"token":"operator-secret"}')
    monkeypatch.setattr(
        "scripts.bootstrap.acquire_release._extract_verified_archive",
        lambda *_: (_ for _ in ()).throw(BootstrapError()),
    )

    with pytest.raises(BootstrapError) as error:
        stage_verified_release(
            archive,
            release=release,
            install_root=root,
            record_path=tmp_path / "record.json",
            checksums=checksums,
            provenance_verified=True,
            state_path=state,
        )

    assert str(error.value) == "SOURCE_VERIFICATION_FAILED"
    assert "operator-secret" not in str(error.value)
    assert (root / "backend" / "app.py").is_file()
    assert (root / "data" / "authentication.json").read_text() == "operator authentication"
    assert (root / "runtime.json").read_text() == "runtime"
    assert (root / ".venv" / "marker").read_text() == "venv"
    assert read_state_record(state).state == "staging"
