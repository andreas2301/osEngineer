# Live System Map

| Service | Container | Metrics Port | Compose File | Restart Cmd |
|---------|-----------|--------------|--------------|-------------|
| Strategist | ola-strategist | 9091 | docker-compose.yml | `docker compose restart strategist` |
| Supervisor | ola-supervisor | 8080/metrics | docker-compose.yml | `docker compose restart supervisor` |
| Guardian | ola-guardian | — | docker-compose.yml | `docker compose restart guardian` |
| Metronome | ola-metronome | 9091 | docker-compose.yml | `docker compose restart metronome` |
| Persist | ola-persist | 9091 | docker-compose.yml | `docker compose restart persist` |
| Accountant | ola-accountant | 9091 | docker-compose.yml | `docker compose restart accountant` |
| Witness | ola-witness | 9091 | docker-compose.yml | `docker compose restart witness` |
| Registry | ola-registry | 9091 | docker-compose.yml | `docker compose restart registry` |
| Fleet broker | rabbitmq-fleet | 15672 | docker-compose.yml | `docker compose restart rabbitmq-fleet` |
