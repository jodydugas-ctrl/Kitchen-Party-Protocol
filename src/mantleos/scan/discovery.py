"""Concurrent native/Qt discovery, adapted from the supplied KPP dev patch.

The join binds scanner reads to bounded pre/post inventories. It is evidence
about local bytes, not an atomic filesystem snapshot or source authentication.
"""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import re
import tempfile
import time
import xml.etree.ElementTree as ET

from .common import EXCLUDES, ScanError, digest, outside, sha, write_json
from .scanner import scan, verify_report

MAX_TRAVERSAL = 100_000


def _plain(path):
    # Junctions and other Windows reparse points can redirect traversal too.
    info = path.lstat()
    if path.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
        raise ScanError('Discovery refuses symlinks and reparse points')
    return info


def _directory(value):
    path = Path(value).absolute()
    for component in (path, *path.parents):
        _plain(component)
    if not path.is_dir():
        raise ScanError('Discovery requires a local source directory')
    return path.resolve()


def _time(deadline):
    if time.monotonic() >= deadline:
        raise ScanError('Discovery time budget exceeded')


def _paths(root, deadline):
    """Bound before sorting; prune exclusions instead of traversing them."""
    count = 0
    pending = [root]
    while pending:
        _time(deadline)
        folder = pending.pop()
        _plain(folder)
        entries = []
        with os.scandir(folder) as iterator:
            for entry in iterator:
                count += 1
                if count > MAX_TRAVERSAL:
                    raise ScanError('Discovery traversal budget exceeded; narrow the source root')
                _time(deadline)
                entries.append(Path(entry.path))
        folders = []
        for path in sorted(entries):
            # Excluded directories never enter either scanner's scope.
            if path.name in EXCLUDES or path.name.startswith('.env') or path.name.endswith(('.pyc', '.pyo')):
                continue
            info = _plain(path)
            if not path.resolve().is_relative_to(root):
                raise ScanError('Discovery source escaped its root')
            if path.is_dir():
                folders.append(path)
            elif path.is_file():
                yield path, info
            else:
                raise ScanError('Discovery refuses non-regular source entries')
        pending.extend(reversed(folders))


def _read(path, info, limit):
    if info.st_size > limit:
        raise ScanError('Discovery file byte budget exceeded; narrow the source root')
    with path.open('rb') as stream:
        data = stream.read(limit + 1)
    after = _plain(path)
    if len(data) > limit or (info.st_size, info.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or len(data) != info.st_size:
        raise ScanError('Source changed or exceeded byte budget during discovery read')
    return data


def snapshot(root, *, deadline, max_files, max_bytes, max_file_bytes):
    files, total = {}, 0
    for path, info in _paths(root, deadline):
        if len(files) >= max_files or total + info.st_size > max_bytes:
            raise ScanError('Discovery source budget exceeded; narrow the source root')
        data = _read(path, info, max_file_bytes)
        total += len(data)
        files[path.relative_to(root).as_posix()] = sha(data)
    return dict(sorted(files.items()))


def scan_qt(source, identity, *, deadline):
    """KPP-compatible .ui declaration inventory; never import Qt or run handlers.

    Declaration extraction derives from KPP's MIT-licensed gui.scan_qt. Discovery
    supplies stricter bounded traversal/reads and shares MantleOS exclusions.
    """
    root = Path(source)
    files, entries = {}, []
    total = 0
    for path, info in _paths(root, deadline):
        if path.suffix != '.ui':
            continue
        if len(files) >= 256 or total + info.st_size > 16_000_000:
            raise ScanError('Qt source inventory budget exceeded')
        content = _read(path, info, 2_000_000)
        total += len(content)
        decoded = content.decode('utf-16' if content.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
        if re.search(r'<!\s*(DOCTYPE|ENTITY)', decoded, re.I):
            raise ScanError('Qt XML DTD/entity declarations are unsupported')
        try:
            tree = ET.fromstring(decoded)
        except ET.ParseError as exc:
            raise ScanError('Malformed Qt UI XML') from exc
        if tree.tag != 'ui':
            raise ScanError('Unsupported Qt UI root')
        relative = path.relative_to(root).as_posix()
        files[relative] = sha(content)
        count = visited = 0

        def walk(node, parent, depth):
            nonlocal count, visited
            _time(deadline)
            visited += 1
            if depth > 64 or visited > 50_000:
                raise ScanError('Qt XML structure budget exceeded')
            named = node.get('name') or node.tag
            locator = parent + '/' + named
            kind = {'widget': 'widget', 'action': 'action', 'actiongroup': 'action-group',
                    'addaction': 'action-placement', 'connection': 'connection', 'tabstop': 'tab-order'}.get(node.tag)
            if kind:
                props = {p.get('name'): ''.join(p.itertext()).strip() for p in node.findall('property')}
                count += 1
                entries.append({'id': relative + '#' + str(count), 'file': relative,
                                'path': locator, 'kind': kind, 'class': node.get('class', ''),
                                'label': props.get('text') or props.get('title') or props.get('windowTitle') or node.text and node.text.strip() or named,
                                'shortcut': props.get('shortcut', ''), 'properties': props,
                                'declaration': {c.tag: (c.text or '').strip() for c in node if c.tag in ('sender', 'signal', 'receiver', 'slot')},
                                'observation': 'static', 'confidence': 'declaration-only',
                                'disposition': 'required', 'depth': 1, 'anchor_ids': []})
                if len(entries) > 10_000:
                    raise ScanError('Qt declarations exceed scan entry limit')
            for child in node:
                walk(child, locator, depth + 1)

        walk(tree, '', 0)
    if not files or not entries:
        raise ScanError('Qt discovery requires .ui files with supported declarations')
    # Match KPP inventory locator/text bounds without importing its separate
    # recipe/acceptance runtime. Refuse oversized labels rather than truncating.
    for path in files:
        if '\\' in path or ':' in path or any(p in ('.', '..') for p in path.split('/')):
            raise ScanError('Qt evidence needs safe relative paths')
    for entry in entries:
        if any(not isinstance(entry[key], str) or not entry[key].strip() or len(entry[key]) > 2048
               for key in ('id', 'path', 'label')):
            raise ScanError('Qt declaration locator/label exceeds supported bounds')
    entries.sort(key=lambda entry: (entry['file'], int(entry['id'].rsplit('#', 1)[1])))
    return {'schema': 'kpp.gui-inventory/2',
            'source': {'identity': identity, 'revision': digest(files), 'files': files},
            'entries': entries,
            'uninspected': ['Reference runtime, conditional visibility, platform differences and dynamic menus',
                            'Action handlers, keyboard/pointer behavior, accessibility and drag/drop',
                            'Screenshot geometry/theme and visual conformance']}


def collect(source, workspace, identity, *, gui_root=None, execution='parallel',
            max_files=1000, max_bytes=16_000_000, max_file_bytes=512_000,
            max_seconds=60, max_nodes=100_000):
    """Join independent scanners; workspace is disposable and external to source."""
    root = _directory(source)
    gui = _directory(gui_root if gui_root is not None else source)
    if not gui.is_relative_to(root):
        raise ScanError('GUI root must be inside the same source tree')
    outside(workspace, root)
    if not isinstance(identity, str) or not identity.strip() or len(identity) > 2048:
        raise ScanError('Discovery requires a nonempty source identity label')
    if execution not in ('parallel', 'serial'):
        raise ScanError('Unsupported discovery execution mode')
    limits = {'max_files': (max_files, 1000), 'max_bytes': (max_bytes, 64_000_000),
              'max_file_bytes': (max_file_bytes, 2_000_000), 'max_seconds': (max_seconds, 3600),
              'max_nodes': (max_nodes, 500_000)}
    if any(type(v) is not int or not 1 <= v <= cap for v, cap in limits.values()):
        raise ScanError('Invalid discovery budget')
    started = time.monotonic()
    deadline = started + max_seconds
    snapshot_options = dict(deadline=deadline, max_files=max_files, max_bytes=max_bytes, max_file_bytes=max_file_bytes)
    before = snapshot(root, **snapshot_options)
    prefix = gui.relative_to(root).as_posix()
    prefix = '' if prefix == '.' else prefix + '/'
    if not any(p.startswith(prefix) and p.endswith('.ui') for p in before):
        raise ScanError('No Qt .ui files under GUI root; use a supported GUI scanner')
    timings = {}

    def code_worker():
        start = time.monotonic()
        result = scan(root, workspace, max_files=max_files, max_bytes=max_bytes,
                      max_file_bytes=max_file_bytes, max_seconds=max_seconds, max_nodes=max_nodes)
        timings['code_seconds'] = time.monotonic() - start
        return result

    def gui_worker():
        start = time.monotonic()
        result = scan_qt(gui, identity, deadline=deadline)
        timings['gui_seconds'] = time.monotonic() - start
        return result

    if execution == 'parallel':
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix='mantle-discovery') as pool:
            jobs = [('code', pool.submit(code_worker)), ('gui', pool.submit(gui_worker))]
            results, errors = [], []
            for name, job in jobs:
                try:
                    results.append(job.result())
                except Exception as exc:
                    errors.append((name, exc))
            if errors:
                name, exc = errors[0]
                raise ScanError(f'{name} scanner failed; no merged evidence: {exc}') from exc
            code, inventory = results
    else:
        code, inventory = code_worker(), gui_worker()
    verify_report(code)
    after = snapshot(root, **snapshot_options)
    if before != after:
        raise ScanError('Source changed during discovery; no merged evidence')
    if not code['graph']['scope']['inventory_exhausted_within_exclusions']:
        raise ScanError('Code inventory truncated; no merged evidence')
    observed = {item['path']: item['sha256'] for item in code['graph']['files']}
    if observed != before:
        raise ScanError('Code scanner read unpinned or changed source bytes')
    ui_files = {prefix + path: checksum for path, checksum in inventory['source']['files'].items()}
    expected_ui = {p: checksum for p, checksum in before.items() if p.startswith(prefix) and p.endswith('.ui')}
    if ui_files != expected_ui:
        raise ScanError('GUI scanner read unpinned or changed source bytes')
    timings['seconds'] = time.monotonic() - started
    report = {'schema': 'mantle.parallel-discovery/1',
              'source': {'root': str(root), 'identity': identity, 'snapshot_revision': digest(before), 'files': before},
              'execution': execution + '-read-only', 'run': timings,
              'scans': {'code': {'schema': code['schema'], 'graph_digest': code['graph_digest'], 'coverage_gaps': code['graph']['gaps']},
                        'gui': {'schema': inventory['schema'], 'entries': len(inventory['entries']), 'uninspected': inventory['uninspected']}},
              'cross_links': {'qt_ui_files': sorted(ui_files), 'code_files': sorted(observed), 'reference_snapshot_consistent': True},
              'specimen_executed': False,
              'limitations': ['Static evidence only; no automatic Recipe or Anchor approval',
                              'C/C++ files are inventoried, not semantically parsed or connected to Qt actions',
                              'Qt declarations do not prove runtime behavior or visual conformance',
                              'Pre/post hashes detect observed drift, not transient changes reverted between reads or source authenticity',
                              'Two local scanner threads; native per-file extraction remains sequential; no distributed workers']}
    return {'report': report, 'code': code, 'gui': inventory}


def discover(source, output, identity, **options):
    """Publish a complete three-file bundle by staging outside the source tree."""
    root = _directory(source)
    target = Path(output).absolute()
    outside(target, root)
    if target.exists() or target.is_symlink():
        raise ScanError('Discovery output must be a new directory')
    target.parent.mkdir(parents=True, exist_ok=True)
    _directory(target.parent)
    with tempfile.TemporaryDirectory(prefix='.discovery-', dir=target.parent) as temporary:
        work = Path(temporary)
        result = collect(root, work / 'worker', identity, **options)
        stage = work / 'bundle'
        stage.mkdir()
        artifacts = {'code-scan.json': result['code'], 'gui-inventory.json': result['gui']}
        for name, value in artifacts.items():
            write_json(stage / name, value)
        report = {**result['report'], 'artifacts': {name: {'sha256': sha((stage / name).read_bytes()),
                                                       'canonical_sha256': digest(value)} for name, value in artifacts.items()}}
        write_json(stage / 'discovery.json', report)
        if target.exists():
            raise ScanError('Discovery output appeared during scan; refusing replacement')
        stage.rename(target)
    return report
