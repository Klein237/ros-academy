#!/usr/bin/env python3
"""Fabrique un jeton de connexion de test (en attendant le service Comptes)."""

import argparse
import os
import sys
import time

import jwt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sub", required=True)
    parser.add_argument("--plan", default="free")
    parser.add_argument("--ttl", type=int, default=300)
    args = parser.parse_args()
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        sys.exit("JWT_SECRET manquant")
    now = int(time.time())
    claims = {"sub": args.sub, "plan": args.plan, "aud": "ros-lab", "iat": now, "exp": now + args.ttl}
    print(jwt.encode(claims, secret, algorithm="HS256"))


if __name__ == "__main__":
    main()
