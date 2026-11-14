"""Deliberately incomplete synthetic component used only by alpha fixtures."""


def release_credential(credential, peer_verified=False):
    # The active fixture starts with a violated claim. Repair evidence is passed
    # between stages; the release harness itself never calls a real provider.
    return credential
