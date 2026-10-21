# Migration entry point

Packaged migration revisions live in src/research_council/storage/migrations so installed wheels
can initialize a workspace. Use `research-council init` or the `migrate(engine)` application API.
Revision 0001 is a self-contained snapshot; future changes require a new revision.
