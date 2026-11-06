# RB-CONTAINER-HARDENING: container runs as root or lacks a healthcheck (synthetic)

Applies to: Trivy misconfig DS-0002 and DS-0026, Semgrep dockerfile missing-user.
Owner: Platform.

1. Add a non root USER to the Dockerfile and make sure the app directory is readable by it.
2. Add a HEALTHCHECK that calls the service health endpoint.
3. Rebuild the image and run the compose smoke test.
