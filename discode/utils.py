
from __future__ import annotations

import asyncio
import functools

from typing import (
    Any,
    Union,
    Iterable,
    Callable,
    final,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from .flags import Permissions

@final
class _UNDEFINED:
    __slots__ = tuple()

    if TYPE_CHECKING:
        __repr__: Callable[str]
        __str__: Callable[str]
        __int__: Callable[int]
        __eq__: Callable[bool]
        __bool__: Callable[bool]

    __repr__ = lambda self: "..."

    __str__ = lambda self: "UNDEFINED"

    __int__ = lambda self: 0

    __eq__ = lambda self, other: isinstance(other, self.__class__)

    __bool__ = lambda self: False


UNDEFINED: Any = _UNDEFINED()


def invite_url(
    client_id,
    *,
    permissions: Union[Permissions, int]=UNDEFINED,
    scopes: Iterable[str]=UNDEFINED,
    redirect_uri: str=UNDEFINED,
) -> str:
    r"""Generates an invite url based on the given parameters for the client.
    """
    ret = f"https://discord.com/oauth2/authorize?client_id={client_id}"
    ret += "&scope=" + "".join(scopes or ("bot",))
    if permissions:
        ret += f"&permissions={int(permissions)}"
    return ret

def decorator(func: Callable):
    func._is_decorator = True
    return func

@decorator
def async_function(sync_function: Callable):
    r"""Decorator to make synchronous function asynchronous. Useful with modules like Pillow, which have a synchronous backend but are extremely useful in image manipulation.

    Usage of this decorator is equivalant to:

    .. code-block:: py

        # inside coroutine:
        await asyncio.get_event_loop.run_in_executor(
            None,
            functools.partial(sync_function, *args, **kwargs)
        )

    Example
    --------

    .. code-block:: py

        @discode.utils.async_function
        def sync_function(msg: discode.Message):
            do_synchronous_operations_with_message(msg)


        @client.on_event("message_create")
        async def on_message(msg):
            await sync_function(msg)

    """

    @functools.wraps(sync_function)
    async def wrapper(*args, **kwargs):
        r"""Internal wrapper to run code asynchronously.
        """
        partial = functools.partial(sync_function, *args, **kwargs)
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, partial)
    return wrapper


def escape_markdown(text: str):
    r"""Get rid of Discord markdown highlighting from given text.

    Parameters
    ----------

    text: :class:`str`
        The text to get freed from markdown highlighting in Discord.

    Returns
    -------

    :class:`str`
        Text passed in text parameter freed from Discord markdown highlighting. 
    """
    return text.replace("*", "\*").replace("_", "\_").replace("`", "\`").replace("|", "\|").replace("~", "\~").replace(">", "\>")


