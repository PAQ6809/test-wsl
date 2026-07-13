from __future__ import annotations

import argparse
import json
import secrets

import uvicorn

from .config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Restoration Studio Personal Worker")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("run")
    sub.add_parser("show-config")
    init = sub.add_parser("configure")
    init.add_argument("--token", default=None)
    init.add_argument("--name", default=None)
    init.add_argument("--reset-pairing", action="store_true")
    args = parser.parse_args()
    cfg = load_config()
    if args.command == "configure":
        if args.token is not None: cfg.worker_token = args.token.strip()
        if args.name: cfg.worker_name = args.name.strip()
        if args.reset_pairing: cfg.pairing_secret = secrets.token_urlsafe(32)
        cfg.save()
        print(f"設定已寫入: {cfg.config_path}")
        print(f"本機配對密碼: {cfg.pairing_secret}")
        return
    if args.command == "show-config":
        print(json.dumps({"config_path": str(cfg.config_path), "worker_name": cfg.worker_name,
                          "edge_url": cfg.edge_url, "bind": f"http://{cfg.bind_host}:{cfg.bind_port}",
                          "pairing_secret": cfg.pairing_secret, "cloud_enabled": bool(cfg.worker_token)},
                         ensure_ascii=False, indent=2))
        return
    uvicorn.run("restoration_worker.server:app", host=cfg.bind_host, port=cfg.bind_port, reload=False,
                access_log=True, log_level="info")


if __name__ == "__main__":
    main()
