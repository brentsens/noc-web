# Windows bootstrap package

Run `generate-icon.ps1` to produce the package ICO solely from the approved
asset. The release pipeline must supply a verified NOC Web archive,
`SHA256SUMS`, its signature, the matching public key, and immutable compatible
tool entries before building a distributable installer. Do not put credentials,
tokens, sessions, cookies, or private download URLs in this directory.

The `nocTools` entry must identify an immutable approved artifact, SHA-256,
compatibility range, and a non-checkout target. It is installed only after
operator confirmation and must expose `tix`, `noc-start`, `noc-status`,
`noc-inv`, and `noc-handover`.
