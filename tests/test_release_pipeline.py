from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_release_workflow_is_tag_gated_and_fail_closed():
    workflow = (ROOT / ".github/workflows/release.yml").read_text()
    assert 'tags:' in workflow and '"v*"' in workflow
    assert '^v[0-9]+\\.[0-9]+\\.[0-9]+$' in workflow
    assert 'python -m pytest -q' in workflow
    assert workflow.index('Validate application') < workflow.index('Publish release assets')
    assert workflow.index('Attest final archive') < workflow.index('Publish release assets')
    assert 'id-token: write' in workflow and 'attestations: write' in workflow
    assert 'python -m pip install --requirement requirements-test.txt' in workflow
    assert workflow.index('requirements-test.txt') < workflow.index('python -m pytest -q')
    assert 'pytest==9.1.1' in (ROOT / 'requirements-test.txt').read_text()


def test_release_scripts_define_stable_safe_contract():
    builder = (ROOT / "scripts/release/build-archive.sh").read_text()
    verifier = (ROOT / "scripts/release/verify-release.sh").read_text()
    assert 'noc-web-${tag}.tar.gz' in builder
    assert 'noc-web-${tag}.sha256' in builder
    for excluded in ('.git', '.venv', '.pytest_cache', '.env', '.log'):
        assert excluded in verifier
    for required in ('backend/app.py', 'scripts/install_runtime.py', 'systemd/noc-web.service.in'):
        assert required in verifier
