#!/usr/bin/env python3
"""Interactive OpenCode factory setup. No secrets, network calls or global config edits."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE if (HERE / 'factorycore').is_dir() else HERE.parent))
from factorycore.installation import default_config, install, load_config


def source_default():
    root = HERE.parent / 'skills'
    return root if (root / 'defensefactory').is_dir() else HERE.parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=source_default(), help='Directory containing all nine skill packages')
    parser.add_argument('--config', type=Path, default=default_config())
    parser.add_argument('--model')
    parser.add_argument('--linear-project')
    parser.add_argument('--linear-url', help='Full Linear MCP endpoint; empty keeps the existing native connection')
    parser.add_argument('--codeintel-url', help='Full CodeIntel MCP endpoint; empty records no additional endpoint')
    parser.add_argument('--codeintel-api-url', help='Optional CodeIntel host indexing API base URL, separate from MCP')
    parser.add_argument('--codeintel-transport', choices=('stdio', 'remote'))
    parser.add_argument('--codeintel-header-name', help='Credential header; CodeIntel workspace APIs normally use X-Api-Key')
    parser.add_argument('--codeintel-token-env', help='Optional bearer-token environment variable NAME')
    parser.add_argument('--github-repository', help='Optional owner/repository hint; ticket remains authoritative')
    parser.add_argument('--launcher', help='Executable path or command; provision models/auth/OTel separately')
    parser.add_argument('--skills-directory', type=Path)
    parser.add_argument('--output-directory', type=Path)
    parser.add_argument('--yes', action='store_true', help='Noninteractive; requires model and Linear project')
    parser.add_argument('--update', action='store_true', help='Back up changed settings and upgrade only managed skill links')
    args = parser.parse_args()
    try:
        previous = load_config(args.config) if args.config.is_file() else {}
    except (ValueError, OSError) as exc:
        parser.error(str(exc))

    def choose(key, label, default='', required=False):
        value = getattr(args, key)
        if value is None:
            value = previous.get(key, default)
            if not args.yes:
                value = input(label + (' [' + str(value) + ']' if value else '') + ': ').strip() or value
        value = str(value)
        if required and not value:
            raise ValueError(label + ' required')
        return value

    try:
        model = choose('model', 'Preferred provisioned provider/model', required=True)
        project = choose('linear_project', 'Linear project name or ID', required=True)
        linear = choose('linear_url', 'Linear MCP URL (blank uses your existing connection)')
        codeintel = choose('codeintel_url', 'Complete CodeIntel MCP URL (not the web UI URL)')
        index_api = choose('codeintel_api_url', 'CodeIntel host indexing API base URL (optional, separate from MCP)')
        transport = choose('codeintel_transport', 'CodeIntel transport: stdio (POST-only/tools compatibility) or remote', 'stdio') if codeintel else previous.get('codeintel_transport', 'stdio')
        header = choose('codeintel_header_name', 'CodeIntel credential header name', 'X-Api-Key') if codeintel or index_api else previous.get('codeintel_header_name', 'X-Api-Key')
        token = choose('codeintel_token_env', 'CodeIntel credential ENVIRONMENT VARIABLE NAME (optional; never paste the key)')
        repository = choose('github_repository', 'Default GitHub owner/repository hint (optional)')
        launcher = choose('launcher', 'OpenCode executable or OTel wrapper',
                          shutil.which('opencode-otel') or shutil.which('opencode') or 'opencode')
        executable = shutil.which(os.path.expanduser(launcher))
        if not executable:
            raise ValueError('Install the launcher or supply its executable path: ' + launcher)
        skills = choose('skills_directory', 'OpenCode skills directory',
                        Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'opencode/skills')
        output = choose('output_directory', 'Trial output directory',
                        Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'defensefactory/trials')
        preferences = {'model': model, 'linear_project': project, 'linear_url': linear,
                       'codeintel_url': codeintel, 'codeintel_api_url': index_api, 'codeintel_token_env': token,
                       'codeintel_transport': transport, 'codeintel_header_name': header,
                       'github_repository': repository, 'launcher': str(Path(executable).resolve()),
                       'skills_directory': str(Path(skills).expanduser().resolve()),
                       'output_directory': str(Path(output).expanduser().resolve())}
        if not args.yes:
            print(json.dumps(preferences, indent=2))
            if input('Install these local settings and skills? [y/N]: ').strip().lower() not in ('y', 'yes'):
                print('Cancelled; nothing installed.')
                return 0
        result = install(args.source, args.config, preferences, update=args.update)
        print(json.dumps(result, indent=2))
        print('Use the installed opencode-trial.py runner, or set OPENCODE_CONFIG, OPENCODE_CONFIG_DIR and DEFENSEFACTORY_CONFIG to the paths above.')
        print('Authenticate existing provider/MCP connections separately, then verify the actual model and tool inventory in a fresh session.')
    except (ValueError, OSError, EOFError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
