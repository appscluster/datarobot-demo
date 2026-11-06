# RB-DEPENDENCY-CVE: vulnerable dependency (synthetic)

Applies to: Trivy vulnerability findings in lock files and images.
Owner: the team that owns the manifest (frontend or backend).

1. Check whether the vulnerable package ships at runtime or only in the dev toolchain.
2. Upgrade to the lowest fixed version on the same major line in a reviewed pull request.
3. Rerun the dependency check and the test suite before merging.
4. If no fix exists, record the exposure and a review date on the finding.
