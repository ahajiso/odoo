# Agent instructions

This file is for coding agents other than Claude Code (Codex, CI bots...). The single
source of project instructions is CLAUDE.md; read it first, then:

- docs/DEFINITIONS.md: business definitions (revisable design document);
- docs/manual/maintenance-manuel-odoo.md and docs/manual/definitions-manuel.md: manual
  update procedure, required for every Odoo change;
- lartdubati_manual/tools/README.md: manual tools (refresh.py, check.py).

Working method (detail in CLAUDE.md, Rules): Claude Code develops and proposes; the
auditing agent (ChatGPT) reviews and criticises, with the code, the database or the
sources as evidence; the owner decides disagreements and runs everything on the server.

Do not duplicate rules here: change CLAUDE.md instead.
