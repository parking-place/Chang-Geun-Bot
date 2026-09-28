#!/usr/bin/env python3
"""Send one user-supplied GPT validation key to DiscordBotLXC via SSH stdin.

Run locally only for credential provisioning. The key is never an argv value,
printed, logged, or placed in public source. Product execution stays on LXC.
"""

from __future__ import annotations

import argparse
import re
import shlex
import subprocess
from pathlib import Path

REMOTE_CODE = r"""
import os
import pwd
import re
import sys
from pathlib import Path

path = Path('/var/lib/changgeun-jev-api/secrets/openai-validation.env')
if path.exists() or path.is_symlink():
    raise SystemExit('validation credential already exists')
data = sys.stdin.buffer.read(512)
if not re.fullmatch(rb'OPENAI_API_KEY=sk-[A-Za-z0-9_-]{20,}\n', data):
    raise SystemExit('invalid validation credential format')
temporary = path.with_name(path.name + '.tmp')
fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
try:
    os.fchown(fd, pwd.getpwnam('changgeun-gateway').pw_uid,
              pwd.getpwnam('changgeun-gateway').pw_gid)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
except BaseException:
    temporary.unlink(missing_ok=True)
    raise
print('GPT validation credential provisioned for gateway account')
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh-config", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--host", choices=("DiscordBotLXC",), required=True)
    args = parser.parse_args()
    if args.source.stat().st_mode & 0o077:
        parser.error("source credential file must be owner-only")
    matches = re.findall(r"\bsk-[A-Za-z0-9_-]{20,}", args.source.read_text())
    if len(matches) != 1:
        parser.error("exactly one API key is required")
    payload = ("OPENAI_API_KEY=" + matches[0] + "\n").encode()
    subprocess.run(
        ["ssh", "-F", str(args.ssh_config.resolve()), args.host,
         "python3 -c " + shlex.quote(REMOTE_CODE)],
        input=payload, check=True,
    )


if __name__ == "__main__":
    main()
