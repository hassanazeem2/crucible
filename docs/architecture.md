# Architecture

## Experiment Contract

Each run has four explicit stages:

1. **Action:** the attacker records intent, sequence, and ATT&CK technique.
2. **Observation:** sensors write source-native JSONL streams.
3. **Normalization:** adapters map those records into stable OCSF-shaped events.
4. **Evaluation:** rules produce alerts; the report joins all records by time.

Recordings are immutable inputs to replay. Changing a rule does not require
running the attack again.

## Raw Streams

| Stream | Producer | Example evidence |
|---|---|---|
| `actions.jsonl` | Attacker | action name, sequence, ATT&CK ID |
| `authentication.jsonl` | Victim | username, method, outcome |
| `application.jsonl` | Victim | HTTP method, path, status |
| `endpoint.jsonl` | Victim | process name, parent, command line |
| `network.jsonl` | Attacker sensor | endpoints, protocol, path, status |
| `capture.pcap` | PCAP sidecar | packet-level traffic in Docker runs |

## OCSF Mapping

The MVP uses the following OCSF class UIDs:

- `1007`: Process Activity
- `3002`: Authentication
- `4001`: Network Activity
- `4002`: HTTP Activity

Every normalized event preserves the source record under
`metadata.original_event`. This makes transforms auditable and allows adapters
to improve without discarding evidence.

## Reproducibility

- Scenario order and timestamps use a deterministic logical clock.
- JSONL output is sorted and serialized with stable key ordering.
- Rules and expected detections are version-controlled inputs.
- Benign fixtures act as a negative control.
- Replay consumes recorded OCSF events rather than live services.

## Trust Boundaries

The range is educational, not an internet-facing security product.

- No endpoint invokes a shell or evaluates user input.
- The Compose network is internal and publishes no host ports.
- Application containers are read-only and drop privilege escalation.
- Packet capture alone receives `NET_RAW` and `NET_ADMIN`.
- Scenario credentials are fixed lab data and must never be reused elsewhere.

## Production Growth Path

The boundaries are intentionally replaceable:

- Replace JSONL sensors with eBPF, auditd, Sysmon, Zeek, or OpenTelemetry.
- Validate normalized records against the official OCSF schema.
- Replace the focused evaluator with pySigma backend compilation.
- Publish events to Kafka and measure ingestion/queue latency separately.
- Add repeated trials, confidence intervals, and labeled background traffic.
- Compare multiple detection systems from the same immutable recording.

