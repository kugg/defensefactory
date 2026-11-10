#!/usr/bin/env python3
"""Sync common resources from the orchestration package; export standalone archives."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def files(package):
    if any(p.is_symlink() for p in package.rglob('*')):
        raise ValueError('Portable packages cannot contain symlinks: ' + str(package))
    return sorted(p for p in package.rglob('*') if p.is_file() and
                  '__pycache__' not in p.parts and p.suffix != '.pyc' and
                  p.name not in ('.DS_Store', 'package-manifest.json'))


def sync(check=False):
    canonical = ROOT / 'skills/defensefactory'
    shared = {p.relative_to(canonical).as_posix(): p.read_bytes() for p in files(canonical)
              if p.relative_to(canonical).parts[0] in ('scripts', 'references')}
    shared['LICENSE'] = (ROOT / 'LICENSE').read_bytes()
    packages = sorted((ROOT / 'skills').glob('defensefactory*'))
    if len(packages) != 9:
        raise ValueError('Expected all nine stage packages')
    drift = []
    for package in packages:
        if package.is_symlink() or not (package / 'SKILL.md').is_file():
            raise ValueError('Invalid stage package: ' + str(package))
        files(package)
        for name, raw in shared.items():
            path = package / name
            if not path.exists() or path.read_bytes() != raw:
                if check:
                    drift.append(str(path.relative_to(ROOT)))
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(raw)
    if drift:
        raise ValueError('Shared resource drift: ' + ', '.join(drift))
    return packages


def export(package, destination):
    payload = {p.relative_to(package).as_posix(): p.read_bytes() for p in files(package)}
    manifest = {name: hashlib.sha256(raw).hexdigest() for name, raw in payload.items()}
    payload['package-manifest.json'] = (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode()
    path = destination / (package.name + '.tar')
    with tarfile.open(path, 'w', format=tarfile.USTAR_FORMAT) as archive:
        for name, raw in sorted(payload.items()):
            info = tarfile.TarInfo(package.name + '/' + name)
            info.size = len(raw)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(raw))
    return {'skill': package.name, 'file': path.name, 'bytes': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    packages = sync(args.check)
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        records = [export(package, args.output) for package in packages]
        (args.output / 'manifest.json').write_text(json.dumps(records, indent=2) + '\n')
    print('Validated ' + str(len(packages)) + ' portable stage packages')


if __name__ == '__main__':
    main()
