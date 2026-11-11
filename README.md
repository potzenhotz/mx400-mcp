# mx400-mcp

Read-only [MCP](https://modelcontextprotocol.io) server for the **Buderus MX400** / **Bosch Connect-Key K 40 RF** internet gateway (also IVT, Vulcano, Worcester K 40 RF). It talks to the gateway's official local API, with no cloud involved, and lets Claude Code (or any MCP client) read your heat pump or heating system.

Single file, no install step: [`uv`](https://docs.astral.sh/uv/) pulls the dependencies from the script header.

## Requirements

- Gateway firmware `15.00.01` or newer (the local API only exists from this version on)
- Gateway and computer on the same local network
- `uv`
- Physical access to the gateway and the `Login` / `Pass` from its label (one-time pairing)

## Setup

1. **Find the gateway.** Use the IP from your router's device list, or browse mDNS:
   ```bash
   dns-sd -B _hvac-open-api._tcp local.   # macOS
   ```
   Give it a fixed IP in your router so the config does not break later.

2. **Pair once and get a token.** Press the **WLAN** and **Wireless** buttons together for about 1 second (the LEDs blink blue), then within 5 minutes run:
   ```bash
   uv run -q --script server.py pair <host> <Login> <Pass>
   ```
   The command prints an access token. It does not expire: treat it like a password.

3. **Register with Claude Code:**
   ```bash
   claude mcp add mx400 --scope user \
     -e K40_HOST=<host> -e K40_TOKEN=<token> \
     -- uv run -q --script /absolute/path/to/server.py
   ```
   Restart Claude Code, then ask something like "How much power is the compressor drawing right now?"

## Tools

| Tool | What it does |
| --- | --- |
| `snapshot` | About 30 key values in one call: outdoor, supply and return temperatures, modulation, electrical power, energy counters, heating circuit and DHW state, notifications. Values your system does not have are skipped. |
| `read(path)` | Any resource of the local API, for example `/dhwCircuits/dhw1/actualTemp`. Also history: `/recordings/heatSources/emon/total/compressor?sampleRate=P1D&startDate=2026-11-01`. |

All endpoints are listed in the [OpenAPI spec](https://github.com/bosch-home-comfort/api-docs/blob/main/openapi/k-40-rf.yaml).

## Notes

- **Read-only.** The gateway's local API currently grants read access only; this server cannot change any settings.
- **TLS verification is off.** The gateway uses a self-signed certificate that names a device ID instead of its host, which [Bosch documents as a known limitation](https://github.com/bosch-home-comfort/api-docs/blob/main/docs/k-40-rf.md#known-limitation-https-certificate-verification). The connection is still encrypted, so only use this on a network you trust.
- **Token storage.** `claude mcp add` stores the token in plain text in `~/.claude.json`.
- **Revoking.** To remove the token from the gateway, see [List and revoke tokens](https://github.com/bosch-home-comfort/api-docs/blob/main/docs/k-40-rf.md#list-and-revoke-tokens). The gateway holds only a limited number of tokens and returns HTTP `507` when full.
- **Self-check:** `uv run -q --script server.py selftest`

## Credits

- API documentation: [Bosch Home Comfort Group api-docs](https://github.com/bosch-home-comfort/api-docs) (Bosch Thermotechnik GmbH)
- Endpoint selection inspired by [smoki3/ha_bosch_k40rf](https://github.com/smoki3/ha_bosch_k40rf)

This is an unofficial community project, not affiliated with or endorsed by Bosch or Buderus. Bosch and Buderus are trademarks of their respective owners.
