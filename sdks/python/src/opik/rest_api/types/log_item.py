# This file was auto-generated by Fern from our API Definition.

from ..core.pydantic_utilities import UniversalBaseModel
import typing
import datetime as dt
from .log_item_level import LogItemLevel
from ..core.pydantic_utilities import IS_PYDANTIC_V2
import pydantic


class LogItem(UniversalBaseModel):
    timestamp: typing.Optional[dt.datetime] = None
    rule_id: typing.Optional[str] = None
    level: typing.Optional[LogItemLevel] = None
    message: typing.Optional[str] = None
    markers: typing.Optional[typing.Dict[str, str]] = None

    if IS_PYDANTIC_V2:
        model_config: typing.ClassVar[pydantic.ConfigDict] = pydantic.ConfigDict(
            extra="allow", frozen=True
        )  # type: ignore # Pydantic v2
    else:

        class Config:
            frozen = True
            smart_union = True
            extra = pydantic.Extra.allow
