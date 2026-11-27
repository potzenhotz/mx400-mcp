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

## What you can learn from the history

The gateway keeps its own history under `/recordings/...`, so you can analyse a whole heating season without a separate logger. Ask in plain language ("How did consumption develop over the year?") or call `read` directly with `sampleRate=P1M` (months), `P1D` (days) or `PT1H` (hours).

| Question | Recording | Why it is useful |
| --- | --- | --- |
| How much electricity did the heat pump use? | `/recordings/heatSources/emon/total/compressor`, `.../total/eheater` | Monthly cost, and how often the electric backup heater kicked in |
| How much heat did it deliver? | `/recordings/heatSources/emon/total/outputProduced` | Divided by electricity: monthly COP and seasonal performance factor (SPF / JAZ) |
| How cold was it? | `/recordings/system/sensors/temperatures/outdoor_t1` | Puts consumption in context; heating limit temperature from a trend line |
| Is the compressor cycling? | `/recordings/heatSources/emon/total/numberOfStarts` | Starts per day; frequent short cycles cost efficiency and wear |
| How long does it run per start? | `/recordings/heatSources/emon/total/workingTime` | Runtime per start; long runs mean the unit modulates well |
| Split by heating / hot water | `/recordings/heatSources/emon/ch/...`, `.../dhw/...` | Shows what hot water costs (only if the heat pump makes it) |
| Compare with your own meter | heat pump meter minus `total/compressor` + `total/eheater` | Reveals other loads on the same meter, e.g. a separate hot-water heat pump |

### Example: one year of an air-to-water heat pump

Read from a real MX400 for Dec 2025 to Nov 2026 (Nov partial):

| Month | Ø outdoor | Electricity | Heat | COP | Starts | Runtime per start |
| --- | --- | --- | --- | --- | --- | --- |
| Dec | 5.1 °C | 730 kWh | 2893 kWh | 3.96 | ~47 | |
| Jan | 2.2 °C | 932 kWh | 3356 kWh | 3.60 | 16 | |
| Feb | 5.5 °C | 608 kWh | 2427 kWh | 3.99 | 55 | |
| Mar | 8.6 °C | 676 kWh | 2621 kWh | 3.88 | 78 | |
| Apr | 11.3 °C | 371 kWh | 1810 kWh | 4.88 | 64 | |
| May | 15.8 °C | 220 kWh | 1119 kWh | 5.09 | 68 | |
| Jun | 21.1 °C | 32 kWh | 104 kWh | (3.3) | 42 | |
| Jul | 20.9 °C | 21 kWh | 11 kWh | (0.5) | 5 | |
| Aug | 21.1 °C | 19 kWh | 7 kWh | (0.4) | 7 | 0.5 h |
| Sep | 17.5 °C | 36 kWh | 128 kWh | (3.6) | 34 | 1.2 h |
| Oct | 12.1 °C | 224 kWh | 1179 kWh | 5.26 | 92 | 3.9 h |
| Nov | 4.6 °C | 673 kWh | 2641 kWh | 3.92 | 23 | 26.9 h |
| **Year** | | **4542 kWh** | **18296 kWh** | **4.03** | **531** | |

What it tells you:
- Seasonal performance factor about 4.0. Summer COPs in brackets mean little: almost no heat is made, so standby and pumps dominate.
- At most 3 starts per day (October); in November the compressor ran 96 % of the time with 23 starts. Cycling is not a problem here.
- The heat pump's own meter showed about 70 to 120 kWh per month more than the gateway, which is the share of a separate hot-water heat pump on the same meter (upper bound, standby included).

### Reading recordings correctly

- Energy and counters: `y` is the value for the period. Temperatures: `y` is a sum and `c` the number of samples, so the mean is `y / c`.
- `c` also tells you whether a period is complete: for recent data it counts hours (a full 30-day month has `c = 720`). Older months are compacted to `c = 1`.
- On the gateway above, counter recordings (`numberOfStarts`) stored the cumulative counter instead of deltas until a firmware update in July 2026, and `workingTime` recordings only start there. Sanity-check old counter history against `/heatSources/numberOfStarts`.

### Monthly import into Excel (Claude Code skill)

[`skills/mx400-monat`](skills/mx400-monat/SKILL.md) fetches the values above for one month and writes them into an Excel sheet via AppleScript (Excel on macOS, workbook path and sheet layout are the author's own; adapt them). Make it available in every project:

```bash
ln -s "$PWD/skills/mx400-monat" ~/.claude/skills/mx400-monat
```

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
