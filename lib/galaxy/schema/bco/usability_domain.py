# generated by datamodel-codegen:
#   filename:  https://opensource.ieee.org/2791-object/ieee-2791-schema/-/raw/master/usability_domain.json
#   timestamp: 2022-09-13T23:51:56+00:00

from __future__ import annotations

from typing import List

from pydantic import (
    Field,
    RootModel,
)


class UsabilityDomain(RootModel):
    root: List[str] = Field(
        ...,
        description="Author-defined usability domain of the IEEE-2791 Object. This field is to aid in search-ability and provide a specific description of the function of the object.",
        title="Usability Domain",
    )
