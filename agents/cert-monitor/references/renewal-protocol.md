# Renewal Protocol

1. Run `cert-renew-executors.sh` (or service-specific script).
2. Verify new cert with `openssl x509 -in cert.pem -text -noout | grep Not`.
3. Restart affected service.
4. Verify service health (`docker ps`, metrics endpoint).
5. Document in `CERT_STATUS_REPORT.md`.
