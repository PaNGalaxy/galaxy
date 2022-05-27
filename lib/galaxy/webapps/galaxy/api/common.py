"""This module contains utility functions shared across the api package."""
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Set,
)

from fastapi import (
    Query,
    Request,
)

from galaxy.schema import (
    FilterQueryParams,
    SerializationParams,
)
from galaxy.schema.schema import UpdateDatasetPermissionsPayload

SerializationViewQueryParam: Optional[str] = Query(
    None,
    title='View',
    description='View to be passed to the serializer',
)

SerializationKeysQueryParam: Optional[str] = Query(
    None,
    title='Keys',
    description='Comma-separated list of keys to be passed to the serializer',
)

SerializationDefaultViewQueryParam: Optional[str] = Query(
    None,
    title='Default View',
    description='The item view that will be used in case no particular view was specified.',
)


def parse_serialization_params(
    view: Optional[str] = None,
    keys: Optional[str] = None,
    default_view: Optional[str] = None,
    **_,  # Additional params are ignored
) -> SerializationParams:
    key_list = None
    if keys:
        key_list = keys.split(',')
    return SerializationParams(view=view, keys=key_list, default_view=default_view)


def query_serialization_params(
    view: Optional[str] = SerializationViewQueryParam,
    keys: Optional[str] = SerializationKeysQueryParam,
    default_view: Optional[str] = SerializationDefaultViewQueryParam,
) -> SerializationParams:
    return parse_serialization_params(view=view, keys=keys, default_view=default_view)


def get_filter_query_params(
    q: Optional[List[str]] = Query(
        default=None,
        title="Filter Query",
        description="Generally a property name to filter by followed by an (often optional) hyphen and operator string.",
        example="create_time-gt",
    ),
    qv: Optional[List[str]] = Query(
        default=None,
        title="Filter Value",
        description="The value to filter by.",
        example="2015-01-29",
    ),
    offset: Optional[int] = Query(
        default=0,
        ge=0,
        title="Offset",
        description="Starts at the beginning skip the first ( offset - 1 ) items and begin returning at the Nth item",
    ),
    limit: Optional[int] = Query(
        default=None,
        ge=1,
        title="Limit",
        description="The maximum number of items to return.",
    ),
    order: Optional[str] = Query(
        default=None,
        title="Order",
        description=(
            "String containing one of the valid ordering attributes followed (optionally) "
            "by '-asc' or '-dsc' for ascending and descending order respectively. "
            "Orders can be stacked as a comma-separated list of values."
        ),
        example="name-dsc,create_time",
    ),
) -> FilterQueryParams:
    """
    This function is meant to be used as a Dependency.
    See https://fastapi.tiangolo.com/tutorial/dependencies/#first-steps
    """
    return FilterQueryParams(
        q=q,
        qv=qv,
        offset=offset,
        limit=limit,
        order=order,
    )


def get_update_permission_payload(payload: Dict[str, Any]) -> UpdateDatasetPermissionsPayload:
    """Converts the generic payload dictionary into a UpdateDatasetPermissionsPayload model with custom parsing.
    This is an attempt on supporting multiple aliases for the permissions params."""
    # There are several allowed names for the same role list parameter, i.e.: `access`, `access_ids`, `access_ids[]`
    # The `access_ids[]` name is not pydantic friendly, so this will be modelled as an alias but we can only set one alias
    # TODO: Maybe we should choose only one way/naming and deprecate the others?
    payload["access_ids"] = payload.get("access_ids[]") or payload.get("access")
    payload["manage_ids"] = payload.get("manage_ids[]") or payload.get("manage")
    payload["modify_ids"] = payload.get("modify_ids[]") or payload.get("modify")
    update_payload = UpdateDatasetPermissionsPayload(**payload)
    return update_payload


def get_query_parameters_from_request_excluding(request: Request, exclude: Set[str]) -> dict:
    """Gets all the request query parameters excluding the given parameters names in `exclude` set.

    This is useful when an endpoint uses arbitrary or dynamic query parameters that
    cannot be anticipated or documented beforehand. The `exclude` set can be used to avoid
    including those parameters that are already handled by the endpoint.
    """
    extra_params = request.query_params._dict
    for param_name in exclude:
        extra_params.pop(param_name, None)
    return extra_params
