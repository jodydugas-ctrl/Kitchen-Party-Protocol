"""Generic Cartridge packing and verification helpers."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
from itertools import islice
import json
import os
from pathlib import Path
import stat
import tempfile
from threading import local
import zipfile

from .primer import verify_lock
from .anchor_blueprint import validate_blueprint, render_runner_guide
from .birth import validate_birth
from .systems import validate_systems_contract, interface_index

MANIFEST_SCHEMA = "mantle.manifest/1"

SECRET_EXACT = {".env", "credentials.json", "secrets.json", "service-account.json", "id_rsa", "id_ed25519",
                "oauth-token.bin", "oauth-client.json", "sessions.sqlite", "sessions.sqlite-wal", "sessions.sqlite-shm"}
MAX_ARCHIVE_FILES = 10000
MAX_ARCHIVE_UNCOMPRESSED = 512 * 1024 * 1024


def _scan_tree(root: Path, *, check_violations: bool):
    root = Path(root)
    violations: list[tuple[tuple[str, ...], str]] = []
    files: list[tuple[tuple[str, ...], Path, str]] = []

    def walk(dirpath: Path, prefix: str, in_pycache: bool) -> None:
        with os.scandir(dirpath) as it:
            entries = sorted(it, key=lambda e: e.name)
        for entry in entries:
            name = entry.name
            rel = f"{prefix}/{name}" if prefix else name
            parts_key = tuple(rel.split("/"))
            if prefix == "" and name == ".git":
                if check_violations and entry.is_symlink():
                    violations.append((parts_key, rel + ":symlink"))
                continue
            if entry.is_symlink():
                if check_violations:
                    violations.append((parts_key, rel + ":symlink"))
                continue
            if check_violations and parts_key[0].lower() in {"nest", ".nest"}:
                violations.append((parts_key, rel + ":NEST-not-portable"))
                if entry.is_dir(follow_symlinks=False):
                    walk(Path(entry.path), rel, in_pycache or name == "__pycache__")
                continue
            if entry.is_dir(follow_symlinks=False):
                next_pycache = in_pycache or name == "__pycache__"
                if next_pycache and not check_violations:
                    continue
                walk(Path(entry.path), rel, next_pycache)
            elif entry.is_file(follow_symlinks=False):
                if check_violations:
                    lowered = name.lower()
                    if lowered in SECRET_EXACT or lowered.startswith(".env."):
                        violations.append((parts_key, rel + ":secret-named-file"))
                if not in_pycache and not rel.endswith(".pyc"):
                    files.append((parts_key, Path(entry.path), rel))

    if root.exists():
        walk(root, "", False)
    if check_violations and violations:
        violations.sort(key=lambda item: item[0])
        raise ValueError("Body contains non-portable/secret material: " + ", ".join(msg for _, msg in violations[:20]))
    files.sort(key=lambda item: item[0])
    return [(path, rel) for _, path, rel in files]


def validate_portable_tree(root: str | Path):
    _scan_tree(Path(root), check_violations=True)
    return {"schema": "mantle.portable-tree/1", "result": "PASS"}

REQUIRED = [
    "CARTRIDGE.json", "ANATOMY.json", "BIO-SOFTWARE.json", "BIRTH.json", "BODY-STATE.json",
    "SYSTEMS.json", "ANCHOR-CODE.json", "COGNITIVE-SEED.json", "ENGRAM.jsonl",
    "PRIMER/PERSONA.md", "PRIMER/COMMANDMENTS.md", "PRIMER/PRIMER.lock.json",
]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def tracked_paths(root: str | Path):
    excluded = {"MANIFEST.json", ".DS_Store"}
    for p, rel in _scan_tree(Path(root), check_violations=False):
        if rel in excluded:
            continue
        yield p, rel


def _validated_tracked(root: Path) -> list[tuple[Path, str]]:
    excluded = {"MANIFEST.json", ".DS_Store"}
    return [(p, rel) for p, rel in _scan_tree(root, check_violations=True) if rel not in excluded]


def write_manifest(root: str | Path) -> dict:
    root = Path(root)
    pairs = _validated_tracked(root)
    actual = {rel: p for p, rel in pairs}
    files = []
    with closing(_manifest_fingerprints(actual)) as fingerprints:
        for rel, digest, size in fingerprints:
            mode = "0755" if os.access(actual[rel], os.X_OK) else "0644"
            files.append({"path": rel, "sha256": digest, "bytes": size, "mode": mode})
    value = {"schema": MANIFEST_SCHEMA, "files": files}
    (root / "MANIFEST.json").write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return value


def _manifest_fingerprint(item, buffer):
    rel, path = item
    digest = hashlib.sha256()
    size = 0
    view = memoryview(buffer)
    # Read every byte without allocating the complete cold object. Four readers
    # use at most four MiB of application read buffers, regardless of file size.
    with path.open('rb') as stream:
        while count := stream.readinto(buffer):
            digest.update(view[:count])
            size += count
    return rel, digest.hexdigest(), size


def _manifest_fingerprints(actual):
    if not actual:
        return
    scratch = local()
    def fingerprint(item):
        if not hasattr(scratch, 'buffer'):
            scratch.buffer = bytearray(1024 * 1024)
        return _manifest_fingerprint(item, scratch.buffer)
    items = iter(actual.items())
    if len(actual) < 64:
        yield from map(fingerprint, items)
        return
    # A bounded read queue, not Engram workers or executable callbacks. map
    # returns results in inventory order, preserving deterministic diagnostics.
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix='manifest-read') as pool:
        while batch := list(islice(items, 16)):
            yield from pool.map(fingerprint, batch)


def verify_manifest(root: str | Path) -> dict:
    root = Path(root)
    actual = {rel: p for p, rel in _validated_tracked(root)}
    manifest = load_json(root / "MANIFEST.json")
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("Unsupported manifest schema")
    expected = {item["path"]: item for item in manifest.get("files", [])}
    if len(expected) != len(manifest.get("files", [])):
        raise ValueError("Duplicate manifest path")
    if set(expected) != set(actual):
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        raise ValueError(f"Manifest inventory mismatch missing={missing} extra={extra}")
    with closing(_manifest_fingerprints(actual)) as fingerprints:
        for rel, fingerprint, size in fingerprints:
            item = expected[rel]
            if fingerprint != item.get("sha256") or size != item.get("bytes"):
                raise ValueError(f"Manifest mismatch: {rel}")
    return manifest


def verify(root: str | Path) -> dict:
    root = Path(root)
    for rel in REQUIRED:
        if not (root / rel).is_file():
            raise ValueError(f"Required Cartridge member missing: {rel}")
    cartridge = load_json(root / "CARTRIDGE.json")
    cell = load_json(root / "ANATOMY.json")
    bio = load_json(root / "BIO-SOFTWARE.json")
    for value, schema in ((cartridge, "mantle.cartridge/1"), (cell, "mantle.anatomy/1"), (bio, "bio-software/3")):
        if value.get("schema") != schema:
            raise ValueError("Unsupported cartridge declaration version: " + str(value.get("schema")))
    birth_value = load_json(root / "BIRTH.json")
    birth = validate_birth(birth_value)
    systems = validate_systems_contract(load_json(root / "SYSTEMS.json"))
    if cartridge.get("kind") != "portable-bio-software-body" or cartridge.get("format") != "vcw/1":
        raise ValueError("Invalid Cartridge Body declaration")
    if cell.get("kind") != "cartridge-anatomy":
        raise ValueError("Invalid cartridge anatomy")
    if cartridge.get("anatomy", {}).get("anatomy_id") != cell.get("anatomy_id"):
        raise ValueError("Cartridge/anatomy identity mismatch")
    if cartridge.get("bio_software", {}).get("id") != bio.get("id") or birth["id"] != bio.get("id"):
        raise ValueError("Cartridge/Birth/Bio-Software identity mismatch")
    birth_decl = cartridge.get("birth", {})
    if birth_decl.get("file") != "BIRTH.json" or birth_decl.get("schema") != "mantle.bio-software-birth/1" or birth_decl.get("sha256") != birth["birth_sha256"]:
        raise ValueError("Cartridge birth contract declaration mismatch")
    if bio.get("birth_contract", {}).get("sha256") != birth["birth_sha256"]:
        raise ValueError("Bio-Software birth contract binding mismatch")
    if bio.get("name") != birth["name"] or bio.get("version") != birth.get("version") or bio.get("kind") != birth["kind"]:
        raise ValueError("Bio-Software fields diverge from BIRTH.json")
    if bio.get("persona", {}).get("name") != birth["primer"]["persona_name"]:
        raise ValueError("Bio-Software Persona name diverges from BIRTH.json")
    expected_persona = birth["primer"]["persona"].strip() + "\n"
    expected_commandments = birth["primer"]["commandments"].strip() + "\n"
    if (root / "PRIMER/PERSONA.md").read_text(encoding="utf-8") != expected_persona:
        raise ValueError("PRIMER/PERSONA.md diverges from BIRTH.json")
    if (root / "PRIMER/COMMANDMENTS.md").read_text(encoding="utf-8") != expected_commandments:
        raise ValueError("PRIMER/COMMANDMENTS.md diverges from BIRTH.json")
    if cartridge.get("distribution") != birth["distribution"]:
        raise ValueError("Cartridge distribution role diverges from BIRTH.json")
    # New Bodies and upgraded packaged agents must carry the refined Anchor Register.
    # Only the current communication contract is admitted.
    from .anchor_language import CAPABILITY, validate_register
    anchor_decl = cell.get('anchor_code', {})
    if anchor_decl.get('schema') == CAPABILITY:
        if anchor_decl.get('file') != 'ANCHOR-CODE.json' or anchor_decl.get('register') != 'ANCHOR-REGISTER.json':
            raise ValueError('Invalid default Anchor Code binding')
        if load_json(root/'ANCHOR-CODE.json').get('schema') != CAPABILITY:
            raise ValueError('Anchor Code declaration mismatch')
        register = validate_register(load_json(root/'ANCHOR-REGISTER.json'))
        if register.get('project') != bio.get('id') or bio.get('default_language') != 'anchor.coding.conversation/1.1':
            raise ValueError('Bio-Application Anchor Coding default mismatch')
    else:
        raise ValueError('Unknown Anchor communication contract')
    interfaces = interface_index(systems)
    portable_bound = {name for name, spec in interfaces.items() if spec.get("binding") == "BOUND"}
    from .organs import system_registry
    system_registry(root).verify_bindings()
    from .engram import read
    read(root/'ENGRAM.jsonl')
    ids = {s.get("id") for s in systems.get("systems", [])}
    required_systems = set(bio.get("required_systems", []))
    if not required_systems <= ids:
        raise ValueError("Required Body system missing")
    blueprint_decl = cartridge.get("anchor_blueprint")
    if blueprint_decl is not None:
        if blueprint_decl.get("file") != "ANCHOR-BLUEPRINT.json" or blueprint_decl.get("schema") != "anchor.blueprint/3":
            raise ValueError("Invalid Anchor Blueprint declaration")
        if not (root / "ANCHOR-BLUEPRINT.json").is_file() or not (root / "RUNNER-GUIDE.md").is_file():
            raise ValueError("Declared Anchor Blueprint or runner guide missing")
        blueprint_value = load_json(root / "ANCHOR-BLUEPRINT.json")
        blueprint = validate_blueprint(blueprint_value, require_ready=True)
        if blueprint_decl.get("sha256") != blueprint["blueprint_sha256"]:
            raise ValueError("Cartridge Anchor Blueprint digest mismatch")
        if (root / "RUNNER-GUIDE.md").read_text(encoding="utf-8") != render_runner_guide(blueprint_value):
            raise ValueError("Runner guide is not the canonical rendering of the Anchor Blueprint")
        binding = birth.get("blueprint")
        expected_binding = {"schema": blueprint["schema"], "id": blueprint["id"], "sha256": blueprint["blueprint_sha256"]}
        if binding != expected_binding:
            raise ValueError("BIRTH.json is not bound to the carried Anchor Blueprint")
        bio_binding = bio.get("anchor_blueprint", {})
        if {k: bio_binding.get(k) for k in ("schema", "id", "sha256")} != expected_binding:
            raise ValueError("Bio-Software Anchor Blueprint binding mismatch")
        declared_interfaces = {
            interface["name"]
            for contract in blueprint["systems"]
            for interface in contract["interfaces"]
        }
        body_interfaces = {
            interface.get("name")
            for system in systems.get("systems", [])
            for interface in system.get("interfaces", [])
        }
        if not declared_interfaces <= body_interfaces:
            raise ValueError("Anchor Blueprint interface missing from Body systems")
    elif birth.get("blueprint") is not None:
        raise ValueError("BIRTH.json declares a Blueprint binding but Cartridge does not carry it")
    from .attachments import validate as validate_attachments
    validate_attachments(root)
    verify_lock(root)
    manifest = verify_manifest(root)
    return {
        "schema": "mantle.verify/1",
        "result": "PASS",
        "cartridge_id": cartridge.get("cartridge_id"),
        "bio_software": bio.get("id"),
        "persona": birth["primer"]["persona_name"],
        "systems": len(ids),
        "interfaces": len(interfaces),
        "bound_interfaces": sorted(portable_bound),
        "host_bound_interfaces": sorted(name for name, spec in interfaces.items() if spec.get("binding") == "HOST_BOUND"),
        "unavailable_interfaces": sorted(name for name, spec in interfaces.items() if spec.get("binding") == "UNAVAILABLE"),
        "tracked_files": len(manifest["files"]),
        "primer_locked": True,
        "birth_contract": True,
        "distribution_role": birth["distribution"]["role"],
        "mutable": birth["distribution"]["mutable"],
        "anchor_blueprint": bool(blueprint_decl),
    }


def pack(root: str | Path, output: str | Path):
    root, output = Path(root).resolve(), Path(output).resolve()
    verify(root)
    if output.exists() or output.is_relative_to(root):
        raise ValueError("Output already exists or is inside Body")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as z:
        for p, rel in _scan_tree(root, check_violations=False):
            info = zipfile.ZipInfo(rel)
            info.date_time = (2026, 1, 1, 0, 0, 0)
            mode = 0o755 if os.access(p, os.X_OK) else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            z.writestr(info, p.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
    return {"output": str(output), "sha256": sha(output.read_bytes()), "bytes": output.stat().st_size}


def unpack(archive: str | Path, output: str | Path):
    archive, output = Path(archive), Path(output)
    if output.exists():
        raise ValueError("Restore output already exists")
    output.mkdir(parents=True)
    try:
        with zipfile.ZipFile(archive) as z:
            infos = z.infolist()
            if len(infos) > MAX_ARCHIVE_FILES:
                raise ValueError("Cartridge archive contains too many members")
            if sum(i.file_size for i in infos) > MAX_ARCHIVE_UNCOMPRESSED:
                raise ValueError("Cartridge archive exceeds uncompressed size limit")
            seen = set()
            created_dirs = {output}
            for info in infos:
                rel = Path(info.filename)
                normalized = rel.as_posix().rstrip("/").casefold()
                if normalized in seen:
                    raise ValueError("Duplicate Cartridge archive member: " + normalized)
                seen.add(normalized)
                if rel.is_absolute() or ".." in rel.parts or "\\" in info.filename or ":" in info.filename or any(part.endswith(("."," ")) for part in rel.parts):
                    raise ValueError("Unsafe archive path")
                mode = (info.external_attr >> 16) & 0o170000
                if mode == stat.S_IFLNK:
                    raise ValueError("Symlinks are not allowed in a Cartridge")
                dest = output / rel
                parent = dest.parent
                if parent not in created_dirs:
                    parent.mkdir(parents=True, exist_ok=True)
                    created_dirs.add(parent)
                if not info.is_dir():
                    dest.write_bytes(z.read(info))
                    perms = (info.external_attr >> 16) & 0o777
                    if perms and (os.name != "nt" or not (perms & 0o200)):
                        dest.chmod(perms)
        return verify(output)
    except Exception:
        import shutil
        shutil.rmtree(output, ignore_errors=True)
        raise
