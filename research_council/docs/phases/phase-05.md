# Phase 5 implementation report

Implemented compliant Crossref/OpenAlex metadata search and resolution, four citation directions
(Crossref explicitly reports unsupported forward citations), local PDF/TXT/Markdown parsing,
bounded retries, scout tool adapters and conservative DOI/title/author/year deduplication.
Scouts retain query/source IDs and isolate failures. Formatter, Ruff, mypy and pytest pass
(25 tests). Metadata-only records do not imply source retrieval. No live literature search ran.
