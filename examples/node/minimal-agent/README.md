# Minimal Node agent (`@aurvia/kavach`)

A ~100-line Node agent that drives the full Kavach accountability loop against a
running `/v1` API, mirroring the Python customer-service harness:

1. an operator issues a bounded, signed **mandate** for the agent;
2. the agent requests a **decision** for a high-value transfer, presenting the
   mandate → policy escalates to a human (**step-up**);
3. the operator **resolves** the step-up → allow;
4. the operator **exports** the signed, tamper-evident evidence trail.

## Run it

The one-command path (boots a local API, builds + links the SDK, runs this agent):

```bash
./scripts/smoke-sdk-node.sh
```

Against an already-running API:

```bash
cd examples/node/minimal-agent
npm install
KAVACH_BASE_URL=http://127.0.0.1:8000 \
KAVACH_OPERATOR_TOKEN=operator-dev-token \
npm start
```

## Configuration

| Variable                | Default                  | Purpose                          |
| ----------------------- | ------------------------ | -------------------------------- |
| `KAVACH_BASE_URL`       | `http://127.0.0.1:8000`  | Base URL of the Kavach API       |
| `KAVACH_TENANT`         | `bank-1`                 | Tenant header                    |
| `KAVACH_OPERATOR_TOKEN` | `operator-dev-token`     | Operator bearer token            |
