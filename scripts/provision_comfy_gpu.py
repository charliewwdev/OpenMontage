#!/usr/bin/env python3
"""Provision a ComfyUI GPU instance and save COMFYUI_SERVER_URL to secrets store.

NOT stored in studio/.env — secrets live in studio/projects/.studio_secrets.json
(and Postgres when PROJECTS_ROOT has DATABASE_URL).

Provider: Vast.ai (GPUHOME Token 工厂 key 不能租机；智川云租机走控制台或后续专用 API)。
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROJECTS = REPO / "studio" / "projects"
STATE = PROJECTS / ".comfy_provision.json"


def _run_json(cmd: list[str]) -> object:
    raw = subprocess.check_output(cmd, text=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return ast.literal_eval(raw)


def search_offer() -> dict:
    # Prefer modern NVIDIA with enough RAM/disk for Comfy + H3 weights download later
    query = (
        "gpu_ram>=24 num_gpus=1 verified=True rentable=True "
        "direct_port_count>=1 disk_space>=120 inet_down>=200"
    )
    offers = _run_json(
        ["vastai", "search", "offers", query, "-o", "dph_total", "--raw"]
    )
    if not isinstance(offers, list) or not offers:
        raise SystemExit(f"no offers for query: {query}")
    # Prefer 4090/5090/L40/A6000-class names
    prefer = ("4090", "5090", "L40", "A6000", "6000", "A100", "H100")
    ranked = sorted(
        offers,
        key=lambda o: (
            0 if any(p in str(o.get("gpu_name") or "") for p in prefer) else 1,
            float(o.get("dph_total") or 99),
            -float(o.get("reliability") or 0),
        ),
    )
    pick = ranked[0]
    print(
        "PICK",
        pick.get("id"),
        pick.get("gpu_name"),
        f"{pick.get('gpu_ram')}MB",
        f"${float(pick.get('dph_total') or 0):.3f}/h",
        pick.get("geolocation"),
        flush=True,
    )
    return pick


def create_instance(offer_id: int) -> int:
    # vastai ComfyUI template image; H3 weights may need post-boot download
    data = _run_json(
        [
            "vastai",
            "create",
            "instance",
            str(offer_id),
            "--image",
            "vastai/comfy:@vastai-automatic-tag",
            "--disk",
            "160",
            "--ssh",
            "--direct",
            "--raw",
        ]
    )
    if not isinstance(data, dict) or not data.get("success"):
        raise SystemExit(f"create failed: {data}")
    iid = int(data["new_contract"])
    print("INSTANCE", iid, flush=True)
    return iid


def wait_running(iid: int, timeout_s: int = 900) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        inst = _run_json(["vastai", "show", "instance", str(iid), "--raw"])
        if isinstance(inst, list):
            inst = inst[0] if inst else {}
        status = (inst.get("actual_status") or inst.get("status") or "").lower()
        print("status", status, "ports", inst.get("ports") or inst.get("public_ipaddr"), flush=True)
        if status == "running":
            return inst
        time.sleep(12)
    raise SystemExit(f"instance {iid} not running within {timeout_s}s")


def resolve_comfy_url(inst: dict) -> str:
    """Map public IP + host port for container 8188 (ComfyUI default)."""
    ports = inst.get("ports") or {}
    # ports often: {"8188/tcp": [{"HostIp":"0.0.0.0","HostPort":"12345"}], ...}
    host_port = None
    if isinstance(ports, dict):
        for key in ("8188/tcp", "3000/tcp", "18188/tcp", "8188", "3000", "80/tcp"):
            if key in ports:
                entry = ports[key]
                if isinstance(entry, list) and entry:
                    host_port = entry[0].get("HostPort") or entry[0].get("host_port")
                elif isinstance(entry, dict):
                    host_port = entry.get("HostPort")
                break
    ip = inst.get("public_ipaddr") or inst.get("ssh_host")
    if not ip:
        raise SystemExit(f"no public ip on instance: {inst}")
    if not host_port:
        # fallback: vastai sometimes puts port in ssh_port-related mapping
        raise SystemExit(f"no 8188 host port mapping yet: ports={ports}")
    return f"http://{ip}:{host_port}"


def wait_comfy(url: str, timeout_s: int = 600) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            with urllib.request.urlopen(url.rstrip("/") + "/system_stats", timeout=15) as r:
                if r.status == 200:
                    print("COMFY_OK", url, flush=True)
                    return
        except Exception as e:
            print("wait comfy", type(e).__name__, flush=True)
        time.sleep(10)
    raise SystemExit(f"ComfyUI not ready at {url}")


def save_to_secrets(url: str) -> None:
    sys.path.insert(0, str(REPO / "studio" / "server"))
    from settings_store import init_secrets, save_secrets, get_secret

    PROJECTS.mkdir(parents=True, exist_ok=True)
    init_secrets(PROJECTS)
    status = save_secrets(
        PROJECTS,
        {
            "COMFYUI_SERVER_URL": url,
            "COMFYUI_VIDEO_SERVER_URL": url,
            "COMFYUI_IMAGE_SERVER_URL": url,
            "COMFYUI_VIDEO_MODEL": "minimax-h3",
        },
        user_id="",
    )
    init_secrets(PROJECTS)
    got = get_secret("COMFYUI_SERVER_URL")
    print("SECRETS_SAVED", got, "status_keys", list(status.keys())[:8], flush=True)
    if got.rstrip("/") != url.rstrip("/"):
        raise SystemExit(f"secret mismatch: {got} != {url}")


def main() -> None:
    offer = search_offer()
    iid = create_instance(int(offer["id"]))
    inst = wait_running(iid)
    url = resolve_comfy_url(inst)
    print("URL", url, flush=True)
    wait_comfy(url)
    save_to_secrets(url)
    STATE.write_text(
        json.dumps(
            {
                "provider": "vastai",
                "instance_id": iid,
                "offer_id": offer.get("id"),
                "gpu": offer.get("gpu_name"),
                "dph": offer.get("dph_total"),
                "comfy_url": url,
                "note": "H3 weights may still need download on first job if image is plain Comfy",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("DONE", STATE, flush=True)


if __name__ == "__main__":
    main()
