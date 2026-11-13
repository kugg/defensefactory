#!/usr/bin/env python3
"""Create or verify a component RULES.md claim-definition mirror."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from factorycore.component_claims import RULES_START,RULES_END,render_rules,validate_catalog,validate_rules
from factorycore.core import GateError


def replace_block(existing,catalog):
    if existing.count(RULES_START)!=1 or existing.count(RULES_END)!=1:
        raise GateError('Existing RULES.md is not factory-managed; merge the component-RULES.md template without overwriting project rules')
    if '## Exact claim shape' not in existing:
        raise GateError('Existing RULES.md reserved block lacks the exact-shape contract; merge the current template first')
    definition=json.dumps(catalog,indent=2,sort_keys=True)
    before,tail=existing.split(RULES_START,1);_,after=tail.split(RULES_END,1)
    return before+RULES_START+'\n```json\n'+definition+'\n```\n'+RULES_END+after


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--claims',type=Path,required=True,help='Component claims.json')
    parser.add_argument('--rules',type=Path,required=True,help='Adjacent RULES.md')
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check',action='store_true',help='Verify exact synchronized definitions')
    mode.add_argument('--write',action='store_true',help='Create or update only the reserved definition block')
    args=parser.parse_args()
    try:
        catalog=validate_catalog(json.loads(args.claims.read_text()))
        if args.check:
            raw=args.rules.read_bytes();validate_rules(raw,catalog)
            result='synchronized'
        else:
            require_adjacent=args.claims.resolve().parent==args.rules.resolve().parent and args.rules.name=='RULES.md'
            if not require_adjacent:raise GateError('RULES.md must be adjacent to claims.json at the owning component root')
            text=replace_block(args.rules.read_text(),catalog) if args.rules.exists() else render_rules(catalog)
            args.rules.write_text(text);validate_rules(args.rules.read_bytes(),catalog);raw=args.rules.read_bytes();result='written'
        print(json.dumps({'result':result,'claims':str(args.claims),'rules':str(args.rules),
                          'rules_sha256':hashlib.sha256(raw).hexdigest(),
                          'authority':'Developer-owned component definition; digest is output evidence, not authored policy.'},sort_keys=True))
    except (OSError,ValueError,json.JSONDecodeError,GateError) as error:
        print(json.dumps({'result':'inconclusive','error':str(error)},sort_keys=True))
        raise SystemExit(2)


if __name__=='__main__':main()

