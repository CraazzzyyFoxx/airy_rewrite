from __future__ import annotations

import inspect
import pathlib
import typing as t

import lightbulb

__all__ = ("AiryPlugin",
           )

if t.TYPE_CHECKING:
    from airy.models.bot import Airy


class AiryPlugin(lightbulb.Plugin):
    def __init_subclass__(cls):
        super().__init_subclass__()
        cls.category: str = pathlib.Path(inspect.getfile(cls)).parent.stem

    def __init__(self, name, category: t.Optional[str] = None):
        super().__init__(name=name)

    @property
    def bot(self) -> Airy:
        return self._app  # type: ignore
