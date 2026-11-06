# RB-LEAKED-SECRET: credential committed to source (synthetic)

Applies to: Gitleaks, TruffleHog and Trivy secret findings (weakness CWE-798).
Owner: AppSec with the service team that owns the credential.

1. Treat the credential as exposed. Never paste the value into tickets or chat; use the finding id and fingerprint.
2. The credential owner revokes and rotates it with the issuer.
3. Remove it from the code and from git history through a reviewed change, and load it from a secrets manager.
4. Keep TruffleHog verification off unless the credential owner approves a live validity check.
