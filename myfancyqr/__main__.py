"""Allow ``python -m myfancyqr ...`` as an alias of the CLI."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
