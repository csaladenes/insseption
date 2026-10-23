"""Minimal CLI: ``insseption health`` / ``insseption matrix POP105A``."""

from __future__ import annotations

import argparse
import json
import os
import sys

from .client import DEFAULT_BASE_URL, Client, InsseptionError


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="insseption", description="INSSE TEMPO JSON API client")
    p.add_argument(
        "--base-url",
        default=os.environ.get("INSSEPTION_BASE", DEFAULT_BASE_URL),
        help="API base (default %(default)s)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("health")
    sub.add_parser("meta")
    sub.add_parser("news")

    pc = sub.add_parser("context")
    pc.add_argument("code", nargs="?")
    pc.add_argument("--lang", default="en")

    pm = sub.add_parser("matrix")
    pm.add_argument("code")
    pm.add_argument("--lang", default="en")

    pq = sub.add_parser("query")
    pq.add_argument("code")
    pq.add_argument("--lang", default="en")

    args = p.parse_args(argv)
    client = Client(args.base_url)
    try:
        if args.cmd == "health":
            data = client.health()
        elif args.cmd == "meta":
            data = client.meta()
        elif args.cmd == "news":
            data = client.news()
        elif args.cmd == "context":
            data = client.context(args.code, lang=args.lang)
        elif args.cmd == "matrix":
            data = client.matrix(args.code, lang=args.lang)
        elif args.cmd == "query":
            data = client.query(args.code, lang=args.lang)
        else:
            p.error(f"unknown command {args.cmd}")
            return 2
        json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0
    except InsseptionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
