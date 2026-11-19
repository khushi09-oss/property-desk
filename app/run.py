"""Local entrypoint; reads only the approved key, never other local settings."""

import os

import uvicorn

from app.knowledge import ROOT


def main() -> None:
    if not os.environ.get("OPENROUTER_API_KEY"):
        for name in (".env", ".env.local"):
            path = ROOT / name
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                field, separator, value = line.partition("=")
                if separator and field.strip() == "OPENROUTER_API_KEY":
                    os.environ["OPENROUTER_API_KEY"] = value.strip().strip("\"'")
    uvicorn.run("app.main:app", host="127.0.0.1", port=18770, access_log=False)


if __name__ == "__main__":
    main()
