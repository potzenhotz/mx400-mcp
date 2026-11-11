# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=2,<3", "httpx>=0.27"]
# ///
"""Read-only MCP server for the Buderus MX400 / Bosch K 40 RF local API.

API reference: https://github.com/bosch-home-comfort/api-docs (docs/k-40-rf.md, openapi/k-40-rf.yaml)

Usage:
  uv run --script server.py pair <host> <login> <password>   # one-time, prints token
  K40_HOST=<host> K40_TOKEN=<token> uv run --script server.py # MCP server on stdio
"""

import asyncio
import os
import sys

import httpx

AUTH_PORT, DATA_PORT = 9442, 9443

# Most useful values for a heat pump with one heating and one DHW circuit; missing ones are skipped.
SNAPSHOT_PATHS = [
    "/system/sensors/temperatures/outdoor_t1",
    "/heatSources/actualSupplyTemperature",
    "/heatSources/currentSupplySetpoint",
    "/heatSources/returnTemperature",
    "/heatSources/actualModulation",
    "/heatSources/actualHeatDemand",
    "/heatSources/compressor/powerElecActual",
    "/heatSources/eHeater/powerElecActual",
    "/heatSources/systemPressure",
    "/heatSources/numberOfStarts",
    "/heatSources/workingTime/totalSystem",
    "/heatSources/emStatus",
    "/heatSources/emon/totalConsumption",
    "/heatSources/emon/chConsumption",
    "/heatSources/emon/dhwConsumption",
    "/heatSources/dhw/cylinderTemperature",
    "/heatSources/hs1/heatPumpType",
    "/heatSources/hs1/supplyFlowCondenserTemp",
    "/heatSources/hs1/returnFlowTemp",
    "/heatSources/hs1/refrigerant/compressorActualSpeed",
    "/heatSources/hs1/oduFanSpeed",
    "/heatingCircuits/hc1/overallStatus",
    "/heatingCircuits/hc1/currentSuWiMode",
    "/heatingCircuits/hc1/roomtemperature",
    "/heatingCircuits/hc1/currentRoomSetpoint",
    "/heatingCircuits/hc1/pumpStatus",
    "/dhwCircuits/dhw1/actualTemp",
    "/dhwCircuits/dhw1/currentSetpoint",
    "/dhwCircuits/dhw1/currentTemperatureLevel",
    "/dhwCircuits/dhw1/overallStatus",
    "/notifications",
]


def client(host: str, port: int, token: str | None = None) -> httpx.AsyncClient:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    # Gateway cert is self-signed and names a device id, not the host (documented limitation).
    return httpx.AsyncClient(base_url=f"https://{host}:{port}", headers=headers, verify=False, timeout=15)


def compact(data: dict) -> object:
    """Shrink a resource to value + unit; keep everything else (lists, recordings) as is."""
    if "value" in data and not isinstance(data["value"], (list, dict)):
        unit = data.get("unitOfMeasure")
        return f"{data['value']} {unit}" if unit else data["value"]
    return {k: v for k, v in data.items() if k not in ("id", "writeable")}


async def get(http: httpx.AsyncClient, path: str) -> object:
    if not path.startswith("/"):
        raise ValueError("path must start with '/'")
    r = await http.get(path)
    if r.status_code == 404:
        return None
    if r.status_code in (401, 403):
        raise RuntimeError("Token rejected by gateway (re-run pairing).")
    r.raise_for_status()
    return compact(r.json())


def run_mcp() -> None:
    from mcp.server.mcpserver import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError

    host, token = os.environ.get("K40_HOST"), os.environ.get("K40_TOKEN")
    if not host or not token:
        sys.exit("Set K40_HOST and K40_TOKEN (get a token with: server.py pair <host> <login> <password>)")

    mcp = MCPServer("mx400")

    @mcp.tool()
    async def snapshot() -> dict:
        """Current key values of the heat pump: temperatures, power, energy, modes, DHW, notifications."""
        async with client(host, DATA_PORT, token) as http:
            values = await asyncio.gather(*(get(http, p) for p in SNAPSHOT_PATHS), return_exceptions=True)
        if all(isinstance(v, Exception) for v in values):
            raise ToolError(f"Gateway not readable: {values[0]!r}")
        return {p: (f"error: {v}" if isinstance(v, Exception) else v)
                for p, v in zip(SNAPSHOT_PATHS, values) if v is not None}

    @mcp.tool()
    async def read(path: str) -> object:
        """Read any resource of the gateway's local API (read-only), e.g. '/dhwCircuits/dhw1/actualTemp'.

        Top-level areas: /system, /heatSources (hs1..hs6, emon, refrigerant, dhw), /heatingCircuits/hc1..hc4,
        /dhwCircuits/dhw1..dhw2, /zones/zone1..16, /devices/device1..32, /solarCircuits/sc1, /ventilation/zone1,
        /gateway, /notifications, /signals.
        History: /recordings/<resource>?sampleRate=<rate>&startDate=YYYY-MM-DD&endDate=YYYY-MM-DD
        (e.g. /recordings/heatSources/emon/total/compressor?sampleRate=all&startDate=2026-10-01).
        Full list: https://github.com/bosch-home-comfort/api-docs/blob/main/openapi/k-40-rf.yaml
        Returns "not available on this system" if the resource does not exist here.
        """
        try:
            async with client(host, DATA_PORT, token) as http:
                value = await get(http, path)
        except Exception as e:
            raise ToolError(repr(e)) from e  # surface the reason instead of a generic error
        return "not available on this system" if value is None else value

    mcp.run()


async def pair(host: str, login: str, password: str) -> None:
    async with client(host, AUTH_PORT) as http:
        r = await http.post("/auth/token", data={
            "grant_type": "password",
            "username": login.strip(),
            "password": password.replace("-", "").strip(),  # gateway wants the label password without hyphens
            "client_name": "claude-code-mcp",
        })
    if r.status_code == 412:
        sys.exit("412: press WLAN + Wireless buttons together for 1s (LEDs blink blue), then retry within 5 min.")
    if r.status_code == 507:
        sys.exit("507: token database full, revoke an unused token first.")
    if r.status_code != 200:
        sys.exit(f"{r.status_code}: {r.text}")
    print(r.json()["access_token"])


if __name__ == "__main__":
    if sys.argv[1:2] == ["pair"]:
        if len(sys.argv) != 5:
            sys.exit("usage: server.py pair <host> <login> <password>")
        asyncio.run(pair(*sys.argv[2:5]))
    elif sys.argv[1:2] == ["selftest"]:
        assert compact({"id": "/x", "writeable": 0, "value": 21.5, "unitOfMeasure": "C"}) == "21.5 C"
        assert compact({"id": "/x", "value": "on"}) == "on"
        assert compact({"id": "/n", "type": "errorList", "values": []}) == {"type": "errorList", "values": []}
        print("ok")
    else:
        run_mcp()
