# Example component architectural rules

Grammar: `defensefactory/rules/v1`
Component: `example-component`
Type: `service`
Owners: @component-maintainers

This concise Markdown file is the component's only authored claim and boundary
source. Replace the example identities and text; keep executable contracts in
ordinary developer-owned files referenced below. Run `claim-rules.py check`
before review. Hashes, run results and ticket state belong in receipts.

## Claim `EXAMPLE-COMPONENT-BOUNDARY`

The component crosses its privileged boundary only through the intended control.

### Boundaries

- Applies to every configured, fallback and recovery path that crosses the boundary.
- Deployment assumptions and excluded interfaces must be stated here.

### Invalidated by

- `CONTROL-BYPASS`: A path crosses the boundary without the intended control.

### Contracts

- `EXAMPLE-BOUNDARY-TEST`: `contracts/example-boundary-test.contract.json`

### Preserves

- Legitimate callers continue to cross the boundary through the intended control.

### Enforcement

- Confirmed violation: block
- Candidate awaiting evaluation: review
- Missing mandatory coverage: block
