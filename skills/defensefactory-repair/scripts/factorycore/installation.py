"""Operator preferences and local OpenCode installation; no service or credential calls."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from urllib.parse import urlsplit

STAGES = ('defensefactory', 'defensefactory-intake', 'defensefactory-assess',
          'defensefactory-repair', 'defensefactory-verify', 'defensefactory-integrate',
          'defensefactory-deploy', 'defensefactory-confirm', 'defensefactory-maintain')


def default_config():
    return Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'defensefactory/config.json'


def endpoint(value):
    if not value:
        return ''
    parsed = urlsplit(value)
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname or
            parsed.username or parsed.password or parsed.query or parsed.fragment or
            any(c.isspace() or ord(c) < 32 for c in value)):
        raise ValueError('Use a complete credential-free HTTP(S) MCP URL, without query or fragment')
    parsed.port  # Reject malformed ports too.
    return value


def validate(profile):
    # Optional API hint added after the first installer; existing v1 profiles remain usable.
    profile = {'codeintel_api_url': '', 'codeintel_header_name': 'X-Api-Key', 'codeintel_transport': 'stdio', **profile}
    allowed = {'schema_version', 'model', 'linear_project', 'linear_url', 'codeintel_url',
               'codeintel_api_url', 'codeintel_token_env', 'codeintel_header_name', 'codeintel_transport', 'github_repository', 'launcher', 'skills_directory',
               'output_directory', 'release_directory'}
    if set(profile) != allowed or profile['schema_version'] != 1:
        raise ValueError('Unsupported factory profile fields/version; do not store secrets here')
    if any(not isinstance(value, str) for key, value in profile.items() if key != 'schema_version'):
        raise ValueError('Factory preference values must be strings')
    if not re.fullmatch(r'[^\s/]+/\S+', profile['model']):
        raise ValueError('Model must be a provisioned provider/model identifier')
    if not isinstance(profile['linear_project'], str) or not profile['linear_project'].strip():
        raise ValueError('Linear project name or ID required')
    for key in ('linear_url', 'codeintel_url', 'codeintel_api_url'):
        endpoint(profile[key])
    variable = profile['codeintel_token_env']
    if variable and not re.fullmatch('[A-Z_][A-Z0-9_]*', variable):
        raise ValueError('CodeIntel token setting is an environment variable NAME, never a token')
    if variable and not (profile['codeintel_url'] or profile['codeintel_api_url']):
        raise ValueError('CodeIntel credential variable needs a CodeIntel MCP/API URL')
    if profile['codeintel_transport'] not in ('stdio', 'remote'):
        raise ValueError('CodeIntel transport must be stdio or remote')
    if not re.fullmatch(r'[A-Za-z0-9-]+', profile['codeintel_header_name']):
        raise ValueError('Invalid credential header name')
    repository = profile['github_repository']
    if repository and not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('GitHub repository hint must use owner/repository')
    for key in ('launcher', 'skills_directory', 'output_directory', 'release_directory'):
        if not isinstance(profile[key], str) or not Path(profile[key]).is_absolute():
            raise ValueError('Absolute local path required: ' + key)
    if Path(profile['skills_directory']).name != 'skills':
        raise ValueError('OpenCode skills_directory must end in /skills for native discovery')
    return profile


def load_config(path):
    return validate(json.loads(Path(path).expanduser().read_text()))


def opencode_config(profile):
    """A partial native config; OpenCode merges existing provider/auth settings."""
    profile = validate(profile)
    mcp = {}
    for name in ('linear', 'codeintel'):
        url = profile[name + '_url']
        if url:
            mcp['factory_' + name] = {'type': 'remote', 'url': url, 'enabled': True}
    if profile['codeintel_url'] and profile['codeintel_transport'] == 'stdio':
        mcp['factory_codeintel'] = {'type': 'local', 'enabled': True, 'command': [sys.executable,
            str(Path(profile['release_directory']) / 'defensefactory/scripts/codeintel-stdio.py'),
            '--url', profile['codeintel_url'], '--credential-env', profile['codeintel_token_env'],
            '--header-name', profile['codeintel_header_name']]}
    elif profile['codeintel_url'] and profile['codeintel_token_env']:
        prefix = 'Bearer ' if profile['codeintel_header_name'].lower() == 'authorization' else ''
        mcp['factory_codeintel'].update(oauth=False, headers={
            profile['codeintel_header_name']: prefix + '{env:' + profile['codeintel_token_env'] + '}'})
    return {'$schema': 'https://opencode.ai/config.json', 'model': profile['model'], 'mcp': mcp}


def package_files(source):
    result = {}
    for stage in STAGES:
        root = source / stage
        if not (root / 'SKILL.md').is_file():
            raise ValueError('Complete release required; missing ' + stage)
        for path in sorted(root.rglob('*')):
            if path.is_symlink():
                raise ValueError('Nested package symlink: ' + str(path))
            if '__pycache__' in path.parts or path.suffix == '.pyc' or path.name == '.DS_Store':
                continue
            if path.is_file():
                result[stage + '/' + path.relative_to(root).as_posix()] = path.read_bytes()
    return result


def install(source, config_path, preferences, *, update=False):
    """Preflight all conflicts. Keep old releases and back up settings on update."""
    source, config_path = Path(source).resolve(), Path(config_path).expanduser().absolute()
    if config_path.is_symlink():
        raise ValueError('Configuration must be a regular file, not a symlink')
    files = package_files(source)
    digests = {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()}
    version = hashlib.sha256(json.dumps(digests, sort_keys=True).encode()).hexdigest()
    release = config_path.parent / 'releases' / version
    profile = validate({**preferences, 'schema_version': 1, 'release_directory': str(release)})
    fragment_path = config_path.parent / 'opencode.json'
    if config_path == fragment_path:
        raise ValueError('Choose a factory config filename other than opencode.json')
    expected = {config_path: (json.dumps(profile, indent=2) + '\n').encode(),
                fragment_path: (json.dumps(opencode_config(profile), indent=2) + '\n').encode()}
    changed = []
    for path, raw in expected.items():
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError('Refusing nonregular configuration: ' + str(path))
        if path.exists() and path.read_bytes() != raw:
            if not update:
                raise ValueError('Settings differ; use --update to preserve a backup and replace them')
            changed.append(path)
    destination = Path(profile['skills_directory'])
    links = []
    for stage in STAGES:
        link, target = destination / stage, release / stage
        if link.is_symlink() and link.resolve() == target:
            continue
        if link.exists() or link.is_symlink():
            managed = (link.is_symlink() and link.resolve().parent.parent == release.parent
                       and link.resolve().name == stage and (link.resolve() / 'SKILL.md').is_file())
            if not update or not managed:
                raise ValueError('Refusing existing unmanaged/different skill: ' + str(link))
        links.append((link, target, os.readlink(link) if link.is_symlink() else None))
    if release.exists():
        if package_files(release) != files:
            raise ValueError('Existing release bytes changed; preserve and investigate: ' + str(release))
    config_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if changed:
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
        backup = config_path.parent / 'history' / stamp
        backup.mkdir(parents=True, mode=0o700)
        for path in changed:
            shutil.copy2(path, backup / path.name)
    if not release.exists():
        release.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=release.parent) as temp:
            staged = Path(temp) / 'release'
            for name, raw in files.items():
                path = staged / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
            staged.rename(release)
    destination.mkdir(parents=True, exist_ok=True)
    applied = []
    old_settings = {path: path.read_bytes() if path.exists() else None for path in expected}
    try:
        for link, target, old in links:
            if old is not None:
                link.unlink()
            applied.append((link, old))
            link.symlink_to(target, target_is_directory=True)
        for path, raw in expected.items():
            if old_settings[path] != raw:
                atomic_write(path, raw)
    except OSError:
        for link, old in reversed(applied):
            if link.is_symlink():
                link.unlink()
            if old is not None:
                link.symlink_to(old, target_is_directory=True)
        for path, raw in old_settings.items():
            if raw is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path, raw)
        raise
    return {'configuration': str(config_path), 'opencode_config': str(fragment_path),
            'opencode_config_directory': str(destination.parent),
            'release': str(release), 'skills_linked': len(links),
            'settings_updated': bool(changed), 'connections_verified': False,
            'scope': 'Local installation only; no authentication, indexing, model call or ticket mutation.'}


def atomic_write(path, raw):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(raw)
            handle.flush()
            os.chmod(temporary, 0o600)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
