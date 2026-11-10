#!/usr/bin/env python3
"""Einstiegspunkt: Claude Token Monitor für Linux/GNOME.

  main.py                 Startet die App (Symbol in der oberen Leiste + Fenster)
  main.py --hidden        Startet nur mit Symbol (für Autostart)
  main.py --dump          Textabzug aller Kennzahlen
  main.py --de | --en     Sprache des Abzugs erzwingen
  main.py --login-status / --register-login / --unregister-login
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    args = sys.argv[1:]

    if "--dump" in args:
        from ctm.cli import dump
        dump(args)
        return 0

    if any(a in args for a in ("--login-status", "--register-login", "--unregister-login")):
        from ctm.cli import cli_language
        from ctm.loc import Loc
        from ctm.settings import autostart_enabled, set_autostart
        loc = Loc(cli_language(args))
        if "--register-login" in args or "--unregister-login" in args:
            error = set_autostart("--register-login" in args)
            if error:
                print(f"{loc.s('Fehler', 'Error')}: {error}")
                return 1
        state = loc.login_active if autostart_enabled() else loc.login_not_registered
        print(f"{loc.cli_autostart}: {state}")
        return 0

    from ctm.app import run
    return run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
