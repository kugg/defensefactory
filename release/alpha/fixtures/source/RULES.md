# Fixture component rules

## Claim: verified peer before credential release

The fixture component may release its synthetic credential only after the
selected peer is explicitly verified.

### Contract

`test_component.py` is the deterministic candidate detector for this fixture.
The alpha handoff test does not claim this toy contract represents a production
security boundary.

### Fence

The repaired candidate must make the peer-verification input mandatory and must
reject a false value before returning the credential.
