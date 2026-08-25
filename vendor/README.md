# vendor/

Drop-in location for the `aurvia-pramana` wheel when building the image
with real Pramana credential verification enabled (ADR-0015 vendored-wheel
bridge).

The prototype defaults to `KAVACH_SDK_BRIDGE_MODE=fake` and does **not**
require a Pramana wheel. To enable `pramana` mode:

1. Build or obtain `aurvia_pramana-<version>-py3-none-any.whl`.
   (From the Pramana repo: `pip wheel sdk/python -w /tmp/w --no-deps`.)
2. Copy it here: `vendor/aurvia_pramana-<version>-py3-none-any.whl`.
3. Uncomment the Pramana install lines in the `Dockerfile`.
4. Set `KAVACH_SDK_BRIDGE_MODE=pramana` in `.env` and rebuild.

Wheels are binary artifacts and are intentionally not committed to the
repository; this directory is a placeholder.
