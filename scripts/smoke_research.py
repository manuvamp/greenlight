"""Build (and cache) the rule sheet for one migration. Usage: smoke_research.py pydantic 1 2"""

import sys

from greenlight.config import load_env

load_env()

from greenlight.events import EventLog, console_printer  # noqa: E402
from greenlight.llm import LLM, record_to_dict  # noqa: E402
from greenlight.research import Researcher  # noqa: E402

lib, fr, to = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
ev = EventLog("smoke-research")
ev.subscribe(console_printer)
llm = LLM()
llm.on_call(lambda rec: ev.emit("llm", **record_to_dict(rec)))
sheet = Researcher(llm, ev, run=f"research-{lib}-{fr}-{to}").rule_sheet(lib, fr, to)
print(f"\n{len(sheet.rules)} rules from {len(sheet.sources)} sources")
print(sheet.compact()[:6000])
print("\nwith grep:", sum(1 for r in sheet.rules if r.grep))
