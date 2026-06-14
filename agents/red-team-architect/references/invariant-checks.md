# Invariant Checks

## 1. ADR Compliance
- [ ] New egress points (HTTP clients, AMQP publishers) cite an ADR.
- [ ] New schema fields have ADR amendment or new ADR.
- [ ] Breaking changes have migration plan in ADR.

## 2. Topology Drift
- [ ] AMQP exchanges/queues in code match ansible declarations.
- [ ] Docker networks in compose match service wiring.
- [ ] Vault paths in code match policy definitions.

## 3. Cross-Repo Contract Consistency
- [ ] JSON schemas referenced by multiple repos are identical (hash match).
- [ ] AMQP message contracts match between producer and consumer repos.
- [ ] Service manifest versions align across dependent repos.

## 4. Security Architecture
- [ ] No new service lacks mTLS config.
- [ ] No new container runs as root (UID ≥ 1000).
- [ ] No new network exposes ports beyond required set.
