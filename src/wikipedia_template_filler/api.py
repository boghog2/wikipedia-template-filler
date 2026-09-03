"""Public API for Wikipedia template filling."""


def fill(source_type: str, identifier: str, **options: object) -> str:
    """Return wiki template markup for *identifier* from *source_type*.

    The implementation will be ported source-by-source from the maintained
    Perl behavior. Golden fixtures from the Perl project should drive the
    expected output as this function grows.
    """
    raise NotImplementedError(
        f"{source_type!r} lookup is not implemented yet for {identifier!r}"
    )
