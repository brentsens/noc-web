# Windows bootstrap package

Feature 012 provides two installation frontends over the same trusted-release
engine:

1. **WSL-native baseline** — `scripts/install-sesami.sh` inside a verified
   package tree. Supported unsigned-install fallback when Windows application
   control blocks an EXE.
2. **Windows EXE wizard** — `SESAMI-NOC-Operations-Setup.exe` built from this
   directory. Keep the Inno Setup source and build scripts. The EXE may require
   Authenticode signing or Smart App Control / application-control approval on
   managed Windows systems.

On Windows, install Inno Setup 6, then run:
`powershell -ExecutionPolicy Bypass -File .\packaging\windows\generate-icon.ps1`
and `powershell -ExecutionPolicy Bypass -File .\packaging\windows\build-installer.ps1`.
The output is `dist\windows\SESAMI-NOC-Operations-Setup.exe`. Run Pester
packaging tests before building, inspect the signed/hashed artifact, then run
the documented fresh-workstation acceptance procedure on an isolated machine.

## Immutable release inputs

The package policy pins NOC Web `brentsens/noc-web` `v1.0.3` and noc-tools
`brentsens/noc-tools` `v1.0.1`. Before any archive is extracted, bootstrap
checks the pinned SHA-256, the published checksum asset, and GitHub artifact
attestation with the fully qualified approved workflow identity. The package
uses GitHub SLSA provenance; `release-public-key.txt` is retained only for
legacy package compatibility and is not a trust input. Rotate a release by
changing the immutable tag, asset name, digest, and signer workflow together,
then rebuilding and independently verifying the installer.

Publish noc-tools as a release archive containing `tix`, `noc-start`,
`noc-status`, `noc-inv`, and `noc-handover`; `noc-inv --contract-version`
must print `noc-inv-contract=1`. Its manifest target must remain a managed
non-checkout location and installation requires explicit operator confirmation.
Never add credentials, tokens, cookies, sessions, authentication files, or
private download URLs to package inputs, records, or release assets.

Run the non-destructive Windows package regression suite with **Pester 6.2.0**:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\windows\run-pester-regression.ps1
```

The runner stages only the Pester test, the three Windows scripts it inspects,
and the bootstrap manifest in a unique native local Windows temporary
directory. It saves the caller's location, changes to that native stage before
importing Pester and invoking the test by its absolute native path, then
restores the original location and removes the directory even when the test
fails. It reports total, passed, failed, skipped, and not-run counts, and
errors when no tests are discovered or any test fails. The suite mocks `Start-Process`,
`Invoke-WebRequest`, COM shortcut access, and filesystem access. It does not
invoke WSL, create a shortcut, install tools, read runtime data, or start a
service. Perform the live clean-workstation procedure in
`specs/012-fresh-workstation-bootstrap/quickstart.md` separately.
Run `generate-icon.ps1` to produce the package ICO solely from the approved asset. The release pipeline must supply a verified NOC Web archive,
its checksum asset, GitHub attestation, and immutable compatible tool entries
before building a distributable installer.

The `nocTools` entry must identify an immutable approved artifact, SHA-256,
compatibility range, and a non-checkout target. It is installed only after
operator confirmation and must expose `tix`, `noc-start`, `noc-status`,
`noc-inv`, and `noc-handover`.
