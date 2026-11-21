"""Verify generated JSON schemas and the proposed Protobuf contract.

Development tools: pip install jsonschema grpcio-tools.
No upstream runtime is imported or executed.
"""
from pathlib import Path
import importlib.util
import json
import sys

import grpc_tools
from grpc_tools import protoc
from google.protobuf import json_format
from jsonschema import Draft202012Validator

from archpat.models import ArchitectureGraph
from archpat.exporters import PROTO

root = Path(__file__).resolve().parents[1]
out = root / "build/protobuf"
out.mkdir(parents=True, exist_ok=True)
contract = root / "contracts/archpat/v1/architecture.proto"
if contract.read_text() != PROTO:
    raise SystemExit("Bundled .proto differs from the generator's contract")
code = protoc.main(["protoc", f"-I{root / 'contracts'}", f"-I{Path(grpc_tools.__file__).parent / '_proto'}",
                    f"--python_out={out}", f"--descriptor_set_out={out / 'architecture.pb'}",
                    "--include_imports", str(contract)])
if code:
    raise SystemExit(code)
generated = out / "archpat/v1/architecture_pb2.py"
spec = importlib.util.spec_from_file_location("archpat_contract_pb2", generated)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
verified = []
for profile in ["local", "worker", "services"]:
    base = root / "examples/generated" / profile
    graph = json.loads((base / "architecture.json").read_text())
    for stem, value in [("graph", graph), ("story", graph["story"])]:
        schema = json.loads((root / "contracts" / f"{stem}.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(value)
    message = json_format.ParseDict(graph, module.ArchitectureProposal())
    raw = message.SerializeToString()
    restored = module.ArchitectureProposal.FromString(raw)
    back = json_format.MessageToDict(restored, preserving_proto_field_name=True,
                                     always_print_fields_with_no_presence=True)
    if ArchitectureGraph.model_validate(back).model_dump(mode="json") != graph:
        raise SystemExit(f"Protobuf model round-trip failed for {profile}")
    verified.append({"profile": profile, "schema": "passed", "protobuf_roundtrip": "passed",
                     "protobuf_bytes": len(raw)})
result = {"schema_compilation": "passed", "profiles": verified,
          "contract": "ArchPat IR only; not upstream schema conformance"}
(root / "evidence/contracts.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))

