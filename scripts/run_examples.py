"""Run four explicit requirement profiles without invoking an LLM or upstream runtime."""
from pathlib import Path
import json
from archpat import StorySpec, synthesize
from archpat.indexing import parse_toon
from archpat.exporters import write_bundle

root = Path(__file__).resolve().parents[1]
base = json.loads((root / "examples/story-local.json").read_text())
inventories = [parse_toon(root / "examples/indexes" / name)
               for name in ("uritime.toon.yaml", "forge.toon.yaml")]
profiles = {
    "local": {},
    "worker": {"isolate_projection": True},
    "services": {"independent_command_query_scaling": True, "max_processes": 6},
    "infeasible": {"ram_budget_mb": 64, "reserved_ram_mb": 0},
}
summary = []
for name, changes in profiles.items():
    data = json.loads(json.dumps(base))
    data["constraints"].update(changes)
    story = StorySpec.model_validate(data)
    result = synthesize(story, inventories)
    write_bundle(result, root / "examples/generated" / name, overwrite=True)
    summary.append({"profile": name, "status": result.status, "selected": result.selected_id,
                    "input_sha256": result.input_sha256, "candidate_count": len(result.candidates)})
output = root / "examples/generated/summary.json"
output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(summary, ensure_ascii=False, indent=2))

