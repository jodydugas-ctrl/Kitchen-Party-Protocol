"""JSON adapter for the host-selected KPP checkout. Uploaded source is data."""
import hashlib
import json
from pathlib import Path
import runpy
import sys
from tempfile import TemporaryDirectory

ORGAN_SHA256 = "fa05c4b9e864cf150d84abb37989b09ba6c8b1f9784e624bdf8dc7d969b4cfbb"


def organ(root, directory, anchor):
    carrier = root / "specimens" / "AnchorForgeOrgan.anchor"
    if hashlib.sha256(carrier.read_bytes()).hexdigest() != ORGAN_SHA256:
        raise RuntimeError("AnchorForge Organ does not match the supported source pin.")
    module = directory / "anchorforge_organ.py"
    anchor.bridge_python(carrier, module)
    return runpy.run_path(str(module))


def inspect(raw, source, anchor, core, design, handoff, root, directory):
    if raw.startswith(b"# Anchor handoff") or b"<!-- ANCHOR MANIFEST" in raw:
        manifest, files = handoff.unpack(raw)
        return {"kind": manifest["schema"], "files": len(files)}
    if raw.lstrip().startswith(b"{"):
        value = json.loads(raw, object_pairs_hook=handoff.unique)
        schema = value.get("schema")
        if schema == "anchor.design/1":
            return {"kind": schema, "design": design.validate(value)}
        if schema in ("kpp.recipe/3", "kpp.recipe/4"):
            core.validate_recipe(value)
            return {"kind": schema, "id": value["id"], "design": value.get("anchor_design")}
        if schema == "anchorforge.organ-spec/1":
            recipe, review = organ(root, directory, anchor)["propose"](value)
            return {"kind": schema, "design": recipe["anchor_design"], "review": review}
        return {"status": "unsupported", "message": "No native inspector for this JSON schema."}
    if not raw.startswith(b"ANCHOR BLUEPRINT:"):
        return {"status": "unsupported", "message": "Local projection only. Native KPP checks structured design JSON and supported blueprints."}
    return {"kind": "blueprint", "inspection": anchor.inspect_file(source)}


def main():
    root = Path(sys.argv[1])
    sys.path.insert(0, str(root / "src"))
    try:
        from mantleos import anchor_design, anchor_handoff
        from mantleos.kpp import anchor, core
    except ImportError as error:
        raise RuntimeError("Set KPP_ROOT to a supported Kitchen Party Protocol checkout.") from error

    operation = sys.argv[2]
    raw = sys.stdin.buffer.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("Input exceeds the Studio request limit.")
    with TemporaryDirectory(prefix="anchorforge-studio-") as work:
        directory = Path(work)
        source = directory / "source.anchor"
        source.write_bytes(raw)
        if operation == "inspect":
            result = inspect(raw, source, anchor, core, anchor_design, anchor_handoff, root, directory)
        elif operation == "bridge":
            output = directory / "bridge.py"
            anchor.bridge_python(source, output)
            result = {"python": output.read_bytes().decode("utf-8")}
        elif operation == "workspace":
            from mantleos.kpp.build import step
            result = {"workspace": step(Path(sys.argv[3]))}
        elif operation == "propose":
            api = organ(root, directory, anchor)
            recipe, review = api["propose"](api["parse_object"](raw, source))
            result = {"recipe": recipe, "review": review}
        else:
            raise ValueError("Unknown operation.")
    return {"status": "passed", "sourceSha256": hashlib.sha256(raw).hexdigest(), **result}


if __name__ == "__main__":
    try:
        print(json.dumps(main()))
    except (ImportError, OSError, RuntimeError) as error:
        print(json.dumps({"status": "unavailable", "message": str(error)}))
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        print(json.dumps({"status": "rejected", "message": str(error)}))
