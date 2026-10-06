class OpportunityNotFoundError(LookupError):
    pass


class CollectionRoundNotFoundError(LookupError):
    pass


class ProfileNotFoundError(LookupError):
    pass


class AmbiguousProfileError(ValueError):
    pass
