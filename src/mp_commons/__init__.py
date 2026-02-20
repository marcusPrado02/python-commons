"""
mp_commons – Platform shared library.

Import path convention::

    from mp_commons.kernel.errors import DomainError
    from mp_commons.kernel.ddd import AggregateRoot, DomainEvent
    from mp_commons.application.cqrs import Command, CommandHandler
    from mp_commons.adapters.fastapi import FastAPIExceptionMapper
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
