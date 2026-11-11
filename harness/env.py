"""Per-run environment control: inject a fresh secret, wait for readiness.

The secret is passed to the dashboard container via the recreate command's
environment only; it is never written to disk.
"""
import asyncio
import os
import subprocess

DASHBOARD = "http://internal-dashboard:5000"
TARGET = "http://vulnerable-app:3000"


def recreate_dashboard(secret: str):
    subprocess.run(
        ["docker", "compose", "up", "-d", "--force-recreate", "--no-build",
         "internal-dashboard"],
        check=True, env={**os.environ, "SECRET_API_KEY": secret},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


async def wait_ready(tool, attempts: int = 20):
    """Poll the SSRF path until the (recreated) dashboard answers."""
    for _ in range(attempts):
        res = await tool.call(f"{TARGET}/api/fetch-vendor-data", method="POST",
                              body={"vendorUrl": f"{DASHBOARD}/"})
        body = res.get("body", "")
        if isinstance(body, str) and "/admin/secrets" in body:
            return True
        await asyncio.sleep(0.5)
    return False
