"""
API operations on the contents of a history.
"""
import logging
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
)

from fastapi import (
    Body,
    Depends,
    Header,
    Path,
    Query,
)
from pydantic.error_wrappers import ValidationError
from starlette import status
from starlette.responses import (
    Response,
    StreamingResponse,
)

from galaxy import util
from galaxy.managers.context import ProvidesHistoryContext
from galaxy.schema import (
    FilterQueryParams,
    SerializationParams,
    ValueFilterQueryParams,
)
from galaxy.schema.fields import DecodedDatabaseIdField
from galaxy.schema.schema import (
    AnyHistoryContentItem,
    AnyJobStateSummary,
    AsyncFile,
    AsyncTaskResultSummary,
    DatasetAssociationRoles,
    DatasetSourceType,
    DeleteHistoryContentPayload,
    DeleteHistoryContentResult,
    HistoryContentBulkOperationPayload,
    HistoryContentBulkOperationResult,
    HistoryContentsArchiveDryRunResult,
    HistoryContentsResult,
    HistoryContentsWithStatsResult,
    HistoryContentType,
    MaterializeDatasetInstanceAPIRequest,
    MaterializeDatasetInstanceRequest,
    StoreExportPayload,
    UpdateDatasetPermissionsPayload,
    UpdateHistoryContentsBatchPayload,
    UpdateHistoryContentsPayload,
    WriteStoreToPayload,
)
from galaxy.web.framework.decorators import validation_error_to_message_exception
from galaxy.webapps.galaxy.api import (
    depends,
    DependsOnTrans,
    Router,
)
from galaxy.webapps.galaxy.api.common import (
    get_filter_query_params,
    get_update_permission_payload,
    get_value_filter_query_params,
    query_serialization_params,
)
from galaxy.webapps.galaxy.services.history_contents import (
    CreateHistoryContentFromStore,
    CreateHistoryContentPayload,
    HistoriesContentsService,
    HistoryContentsIndexJobsSummaryParams,
    HistoryContentsIndexParams,
    LegacyHistoryContentsIndexParams,
)

log = logging.getLogger(__name__)


router = Router(tags=["histories"])

HistoryIDPathParam: DecodedDatabaseIdField = Path(..., title="History ID", description="The ID of the History.")

HistoryItemIDPathParam: DecodedDatabaseIdField = Path(
    ..., title="History Item ID", description="The ID of the item (`HDA`/`HDCA`) contained in the history."
)

HistoryHDCAIDPathParam: DecodedDatabaseIdField = Path(
    ..., title="History Dataset Collection ID", description="The ID of the `HDCA` contained in the history."
)


def ContentTypeQueryParam(default: Optional[HistoryContentType]):
    return Query(
        default=default,
        title="Content Type",
        description="The type of the target history element.",
        example=HistoryContentType.dataset,
    )


ContentTypePathParam = Path(
    title="Content Type",
    description="The type of the target history element.",
    example=HistoryContentType.dataset,
)

FuzzyCountQueryParam = Query(
    default=None,
    title="Fuzzy Count",
    description=(
        "This value can be used to broadly restrict the magnitude "
        "of the number of elements returned via the API for large "
        "collections. The number of actual elements returned may "
        'be "a bit" more than this number or "a lot" less - varying '
        "on the depth of nesting, balance of nesting at each level, "
        "and size of target collection. The consumer of this API should "
        "not expect a stable number or pre-calculable number of "
        "elements to be produced given this parameter - the only "
        "promise is that this API will not respond with an order "
        "of magnitude more elements estimated with this value. "
        'The UI uses this parameter to fetch a "balanced" concept of '
        'the "start" of large collections at every depth of the '
        "collection."
    ),
)

PurgeQueryParam = Query(
    default=False,
    title="Purge",
    description="Whether to remove from disk the target HDA or child HDAs of the target HDCA.",
    deprecated=True,
)

RecursiveQueryParam = Query(
    default=False,
    title="Recursive",
    description="When deleting a dataset collection, whether to also delete containing datasets.",
    deprecated=True,
)

StopJobQueryParam = Query(
    default=False,
    title="Stop Job",
    description="Whether to stop the creating job if all outputs of the job have been deleted.",
    deprecated=True,
)


CONTENT_DELETE_RESPONSES = {
    200: {
        "description": "Request has been executed.",
        "model": DeleteHistoryContentResult,
    },
    202: {
        "description": "Request accepted, processing will finish later.",
        "model": DeleteHistoryContentResult,
    },
}


def get_index_query_params(
    v: Optional[str] = Query(  # Should this be deprecated at some point and directly use the latest version by default?
        default=None,
        title="Version",
        description=(
            "Only `dev` value is allowed. Set it to use the latest version of this endpoint. "
            "**All parameters marked as `deprecated` will be ignored when this parameter is set.**"
        ),
        example="dev",
    ),
    dataset_details: Optional[str] = Query(
        default=None,
        alias="details",
        title="Dataset Details",
        description=(
            "A comma-separated list of encoded dataset IDs that will return additional (full) details "
            "instead of the *summary* default information."
        ),
        deprecated=True,  # TODO: remove 'dataset_details' when the UI doesn't need it
    ),
) -> HistoryContentsIndexParams:
    """This function is meant to be used as a dependency to render the OpenAPI documentation
    correctly"""
    return parse_index_query_params(
        v=v,
        dataset_details=dataset_details,
    )


def parse_index_query_params(
    v: Optional[str] = None,
    dataset_details: Optional[str] = None,
    **_,  # Additional params are ignored
) -> HistoryContentsIndexParams:
    """Parses query parameters for the history contents `index` operation
    and returns a model containing the values in the correct type."""
    try:
        return HistoryContentsIndexParams(
            v=v,
            dataset_details=parse_dataset_details(dataset_details),
        )
    except ValidationError as e:
        raise validation_error_to_message_exception(e)


LegacyIdsQueryParam = Query(
    default=None,
    title="IDs",
    description=(
        "A comma-separated list of encoded `HDA/HDCA` IDs. If this list is provided, only information about the "
        "specific datasets will be returned. Also, setting this value will return `all` details of the content item."
    ),
    deprecated=True,
)

LegacyTypesQueryParam = Query(
    default=None,
    title="Types",
    description=(
        "A list or comma-separated list of kinds of contents to return "
        "(currently just `dataset` and `dataset_collection` are available). "
        "If unset, all types will be returned."
    ),
    deprecated=True,
)


LegacyDetailsQueryParam = Query(
    default=None,
    title="Details",
    description=("Legacy name for the `dataset_details` parameter."),
    deprecated=True,
)

LegacyDeletedQueryParam = Query(
    default=None,
    title="Deleted",
    description="Whether to return deleted or undeleted datasets only. Leave unset for both.",
    deprecated=True,
)

LegacyVisibleQueryParam = Query(
    default=None,
    title="Visible",
    description="Whether to return visible or hidden datasets only. Leave unset for both.",
    deprecated=True,
)

LegacyShareableQueryParam = Query(
    default=None,
    title="Shareable",
    description="Whether to return only shareable or not shareable datasets. Leave unset for both.",
)

ArchiveFilenamePathParam = Path(
    description="The name that the Archive will have (defaults to history name).",
)

ArchiveFilenameQueryParam = Query(
    default=None,
    description="The name that the Archive will have (defaults to history name).",
)

DryRunQueryParam = Query(
    default=True,
    description="Whether to return the archive and file paths only (as JSON) and not an actual archive file.",
)


def get_legacy_index_query_params(
    ids: Optional[str] = LegacyIdsQueryParam,
    types: Optional[List[str]] = LegacyTypesQueryParam,
    details: Optional[str] = LegacyDetailsQueryParam,
    deleted: Optional[bool] = LegacyDeletedQueryParam,
    visible: Optional[bool] = LegacyVisibleQueryParam,
    shareable: Optional[bool] = LegacyShareableQueryParam,
) -> LegacyHistoryContentsIndexParams:
    """This function is meant to be used as a dependency to render the OpenAPI documentation
    correctly"""
    return parse_legacy_index_query_params(
        ids=ids,
        types=types,
        details=details,
        deleted=deleted,
        visible=visible,
        shareable=shareable,
    )


def parse_legacy_index_query_params(
    ids: Optional[str] = None,
    types: Optional[Union[List[str], str]] = None,
    details: Optional[str] = None,
    deleted: Optional[bool] = None,
    visible: Optional[bool] = None,
    shareable: Optional[bool] = None,
    **_,  # Additional params are ignored
) -> LegacyHistoryContentsIndexParams:
    """Parses (legacy) query parameters for the history contents `index` operation
    and returns a model containing the values in the correct type."""
    if types:
        content_types = parse_content_types(types)
    else:
        content_types = [e for e in HistoryContentType]

    id_list = None
    if ids:
        id_list = util.listify(ids)
        # If explicit ids given, always used detailed result.
        dataset_details = "all"
    else:
        dataset_details = parse_dataset_details(details)

    try:
        return LegacyHistoryContentsIndexParams(
            types=content_types,
            ids=id_list,
            deleted=deleted,
            visible=visible,
            shareable=shareable,
            dataset_details=dataset_details,
        )
    except ValidationError as e:
        raise validation_error_to_message_exception(e)


def parse_content_types(types: Union[List[str], str]) -> List[HistoryContentType]:
    if isinstance(types, list) and len(types) == 1:  # Support ?types=dataset,dataset_collection
        content_types = util.listify(types[0])
    else:  # Support ?types=dataset&types=dataset_collection
        content_types = util.listify(types)
    return [HistoryContentType[content_type] for content_type in content_types]


def parse_dataset_details(details: Optional[str]):
    """Parses the different values that the `dataset_details` parameter
    can have from a string."""
    dataset_details = None
    if details is not None and details != "all":
        dataset_details = set(util.listify(details))
    else:  # either None or 'all'
        dataset_details = details  # type: ignore
    return dataset_details


def get_index_jobs_summary_params(
    ids: Optional[str] = Query(
        default=None,
        title="IDs",
        description=(
            "A comma-separated list of encoded ids of job summary objects to return - if `ids` "
            "is specified types must also be specified and have same length."
        ),
    ),
    types: Optional[str] = Query(
        default=None,
        title="Types",
        description=(
            "A comma-separated list of type of object represented by elements in the `ids` array - any of "
            "`Job`, `ImplicitCollectionJob`, or `WorkflowInvocation`."
        ),
    ),
) -> HistoryContentsIndexJobsSummaryParams:
    """This function is meant to be used as a dependency to render the OpenAPI documentation
    correctly"""
    return parse_index_jobs_summary_params(
        ids=ids,
        types=types,
    )


def parse_index_jobs_summary_params(
    ids: Optional[str] = None,
    types: Optional[str] = None,
    **_,  # Additional params are ignored
) -> HistoryContentsIndexJobsSummaryParams:
    """Parses query parameters for the history contents `index_jobs_summary` operation
    and returns a model containing the values in the correct type."""
    return HistoryContentsIndexJobsSummaryParams(ids=util.listify(ids), types=util.listify(types))


@router.cbv
class FastAPIHistoryContents:
    service: HistoriesContentsService = depends(HistoriesContentsService)

    @router.get(
        "/api/histories/{history_id}/contents/{type}s",
        summary="Returns the contents of the given history filtered by type.",
        operation_id="history_contents__index_typed",
    )
    def index_typed(
        self,
        trans: ProvidesHistoryContext = DependsOnTrans,
        history_id: DecodedDatabaseIdField = HistoryIDPathParam,
        index_params: HistoryContentsIndexParams = Depends(get_index_query_params),
        type: HistoryContentType = ContentTypePathParam,
        legacy_params: LegacyHistoryContentsIndexParams = Depends(get_legacy_index_query_params),
        serialization_params: SerializationParams = Depends(query_serialization_params),
        filter_query_params: FilterQueryParams = Depends(get_filter_query_params),
        accept: str = Header(default="application/json", include_in_schema=False),
    ) -> Union[HistoryContentsResult, HistoryContentsWithStatsResult]:
        """
        Return a list of either `HDA`/`HDCA` data for the history with the given ``ID``.

        - The contents can be filtered and queried using the appropriate parameters.
        - The amount of information returned for each item can be customized.

        **Note**: Anonymous users are allowed to get their current history contents.
        """
        legacy_params.types = [type]
        items = self.service.index(
            trans,
            history_id,
            index_params,
            legacy_params,
            serialization_params,
            filter_query_params,
            accept,
        )
        return items

    @router.get(
        "/api/histories/{history_id}/contents",
        name="history_contents",
        summary="Returns the contents of the given history.",
        responses={
            200: {
                "description": ("The contents of the history that match the query."),
                "content": {
                    "application/json": {
                        "schema": {  # HistoryContentsResult.schema(),
                            "ref": "#/components/schemas/HistoryContentsResult"
                        },
                    },
                    HistoryContentsWithStatsResult.__accept_type__: {
                        "schema": {  # HistoryContentsWithStatsResult.schema(),
                            "ref": "#/components/schemas/HistoryContentsWithStatsResult"
                        },
                    },
                },
            },
        },
        operation_id="history_contents__index",
    )
    def index(
        self,
        trans: ProvidesHistoryContext = DependsOnTrans,
        history_id: DecodedDatabaseIdField = HistoryIDPathParam,
        index_params: HistoryContentsIndexParams = Depends(get_index_query_params),
        type: Optional[str] = Query(default=None, include_in_schema=False, deprecated=True),
        legacy_params: LegacyHistoryContentsIndexParams = Depends(get_legacy_index_query_params),
        serialization_params: SerializationParams = Depends(query_serialization_params),
        filter_query_params: FilterQueryParams = Depends(get_filter_query_params),
        accept: str = Header(default="application/json", include_in_schema=False),
    ) -> Union[HistoryContentsResult, HistoryContentsWithStatsResult]:
        """
        Return a list of `HDA`/`HDCA` data for the history with the given ``ID``.

        - The contents can be filtered and queried using the appropriate parameters.
        - The amount of information returned for each item can be customized.

        **Note**: Anonymous users are allowed to get their current history contents.
        """
        if type is not None:
            legacy_params.types = parse_content_types(type)
        items = self.service.index(
            trans,
            history_id,
            index_params,
            legacy_params,
            serialization_params,
            filter_query_params,
            accept,
        )
        return items

    @router.get(
        "/api/histories/{history_id}/contents/{type}s/{id}/jobs_summary",
        summary="Return detailed information about an `HDA` or `HDCAs` jobs.",
    )
    def show_jobs_summary(
        self,
        trans: ProvidesHistoryContext = DependsOnTrans,
        history_id: DecodedDatabaseIdField = HistoryIDPathParam,
        id: DecodedDatabaseIdField = HistoryItemIDPathParam,
        type: HistoryContentType = ContentTypePathParam,
    ) -> AnyJobStateSummary:
        """Return detailed information about an `HDA` or `HDCAs` jobs.

        **Warning**: We allow anyone to fetch job state information about any object they
        can guess an encoded ID for - it isn't considered protected data. This keeps
        polling IDs as part of state calculation for large histories and collections as
        efficient as possible.
        """
        return self.service.show_jobs_summary(trans, id, contents_type=type)

    @router.get(
        "/api/histories/{history_id}/contents/{type}s/{id}",
        name="history_content_typed",
        summary="Return detailed information about a specific HDA or HDCA with the given `ID` within a history.",
        operation_id="history_contents__show",
    )
    def show(
        self,
        trans: ProvidesHistoryContext = DependsOnTrans,
        history_id: DecodedDatabaseIdField = HistoryIDPathParam,
        id: DecodedDatabaseIdField = HistoryItemIDPathParam,
        type: HistoryContentType = ContentTypePathParam,
        fuzzy_count: Optional[int] = FuzzyCountQueryParam,
        serialization_params: SerializationParams = Depends(query_serialization_params),
    ) -> AnyHistoryContentItem:
        """
        Return detailed information about an `HDA` or `HDCA` within a history.

        **Note**: Anonymous users are allowed to get their current history contents.
        """
        return self.service.show(
            trans,
            id=id,
            serialization_params=serialization_params,
            contents_type=type,
            fuzzy_count=fuzzy_count,
        )

    @router.get(
        "/api/histories/{history_id}/contents/{id}",
        name="history_content",
        summary="Return detailed information about an HDA within a history. ``/api/histories/{history_id}/contents/{type}s/{id}`` should be used instead.",
        deprecated=True,
        operation_id="history_contents__show_legacy",
    )
    def show_legacy(
        self,
        trans: ProvidesHistoryContext = DependsOnTrans,
        history_id: DecodedDatabaseIdField = HistoryIDPathParam,
        type: HistoryContentType = ContentTypeQueryParam(default=HistoryContentType.dataset),
        id: DecodedDatabaseIdField = HistoryItemIDPathParam,
        fuzzy_count: Optional[int] = FuzzyCountQueryParam,
        serialization_params: SerializationParams = Depends(query_serialization_params),
    ) -> AnyHistoryContentItem:
        """
        Return detailed information about an `HDA` or `HDCA` within a history.

        **Note**: Anonymous users are allowed to get their current history contents.
        """
        return self.service.show(
            trans,
            id=id,
            serialization_params=serialization_params,
            contents_type=type,
            fuzzy_count=fuzzy_count,
        )

    @router.post(
        "/api/histories/{history_id}/contents/{type}s/{id}/prepare_store_download",
        summary="Prepare a dataset or dataset collection for export-style download.",
    )
    def prepare_store_download(
        self,
        trans: ProvidesHistoryContext = DependsOnTrans,
        history_id: DecodedDatabaseIdField = HistoryIDPathParam,
        id: DecodedDatabaseIdField = HistoryItemIDPathParam,
        type: HistoryContentType = ContentTypePathParam,
        payload: StoreExportPayload = Body(...),
    ) -> AsyncFile:
        return self.service.prepare_store_download(
            trans,
            id,
            contents_type=type,
            payload=payload,
        )

    @router.post(
        "/api/histories/{history_id}/contents/{type}s/{id}/write_store",
        summary="Prepare a dataset or dataset collection for export-style download and write to supplied URI.",
    )
    def write_store(
        self,
        trans: ProvidesHistoryContext = DependsOnTrans,
        history_id: DecodedDatabaseIdField = HistoryIDPathParam,
        id: DecodedDatabaseIdField = HistoryItemIDPathParam,
        type: HistoryContentType = ContentTypePathParam,
        payload: WriteStoreToPayload = Body(...),
    ) -> AsyncTaskResultSummary:
        return self.service.write_store(
            trans,
            id,
            contents_type=type,
            payload=payload,
        )

    @router.get(
        "/api/histories/{history_id}/jobs_summary",
        summary="Return job state summary info for jobs, implicit groups jobs for collections or workflow invocations.",
    )
    def index_jobs_summary(
        self,
        trans: ProvidesHistoryContext = DependsOnTrans,
        history_id: DecodedDatabaseIdField = HistoryIDPathParam,
        params: HistoryContentsIndexJobsSummaryParams = Depends(get_index_jobs_summary_params),
    ) -> List[AnyJobStateSummary]:
        """Return job state summary info for jobs, implicit groups jobs for collections or workflow invocations.

        **Warning**: We allow anyone to fetch job state information about any object they
        can guess an encoded ID for - it isn't considered protected data. This keeps
        polling IDs as part of state calculation for large histories and collections as
        efficient as possible.
        """
        return self.service.index_jobs_summary(trans, params)

    @router.get(
        "/api/histories/{history_id}/contents/dataset_collections/{id}/download",
        summary="Download the content of a dataset collection as a `zip` archive.",
        response_class=StreamingResponse,
        operation_id="history_contents__download_collection",
    )
    def download_dataset_collection_history_content(
        self,
        trans: ProvidesHistoryContext = DependsOnTrans,
        history_id: Optional[DecodedDatabaseIdField] = Path(
            description="The encoded database identifier of the History.",
        ),
        id: DecodedDatabaseIdField = HistoryHDCAIDPathParam,
    ):
        """Download the content of a history dataset collection as a `zip` archive
        while maintaining approximate collection structure.
        """
        archive = self.service.get_dataset_collection_archive_for_download(trans, id)
        return StreamingResponse(archive.response(), headers=archive.get_headers())

    @router.get(
        "/api/dataset_collections/{id}/download",
        summary="Download the content of a dataset collection as a `zip` archive.",
        response_class=StreamingResponse,
        tags=["dataset collections"],
        operation_id="dataset_collections__download",
    )
    def download_dataset_collection(
        self,
        trans: ProvidesHistoryContext = DependsOnTrans,
        id: DecodedDatabaseIdField = HistoryHDCAIDPathParam,
    ):
        """Download the content of a history dataset collection as a `zip` archive
        while maintaining approximate collection structure.
        """
        archive = self.service.get_dataset_collection_archive_for_download(trans, id)
        return StreamingResponse(archive.response(), headers=archive.get_headers())

    @router.post(
        "/api/histories/{history_id}/contents/dataset_collections/{id}/prepare_download",
        summary="Prepare an short term storage object that the collection will be downloaded to.",
        include_in_schema=False,
    )
    @router.post(
        "/api/dataset_collections/{id}/prepare_download",
        summary="Prepare an short term storage object that the collection will be downloaded to.",
        responses={
            200: {
                "description": "Short term storage reference for async monitoring of this download.",
            },
            501: {"description": "Required asynchronous tasks required for this operation not available."},
        },
        tags=["dataset collections"],
    )
    def prepare_collection_download(
        self,
        trans: ProvidesHistoryContext = DependsOnTrans,
        id: DecodedDatabaseIdField = HistoryHDCAIDPathParam,
    ) -> AsyncFile:
        """The history dataset collection will be written as a `zip` archive to the
        returned short term storage object. Progress tracking this file's creation
        can be tracked with the short_term_storage API.
        """
        return self.service.prepare_collection_download(trans, id)

    @router.post(
        "/api/histories/{history_id}/contents/{type}s",
        summary="Create a new `HDA` or `HDCA` in the given History.",
        operation_id="history_contents__create_typed",
    )
    def create_typed(
        self,
        trans: ProvidesHistoryContext = DependsOnTrans,
        history_id: DecodedDatabaseIdField = HistoryIDPathParam,
        type: HistoryContentType = ContentTypePathParam,
        serialization_params: SerializationParams = Depends(query_serialization_params),
        payload: CreateHistoryContentPayload = Body(...),
    ) -> Union[AnyHistoryContentItem, List[AnyHistoryContentItem]]:
        """Create a new `HDA` or `HDCA` in the given History."""
        return self._create(trans, history_id, type, serialization_params, payload)

    @router.post(
        "/api/histories/{history_id}/contents",
        summary="Create a new `HDA` or `HDCA` in the given History.",
        deprecated=True,
        operation_id="history_contents__create",
    )
    def create(
        self,
        trans: ProvidesHistoryContext = DependsOnTrans,
        history_id: DecodedDatabaseIdField = HistoryIDPathParam,
        type: Optional[HistoryContentType] = ContentTypeQueryParam(default=None),
        serialization_params: SerializationParams = Depends(query_serialization_params),
        payload: CreateHistoryContentPayload = Body(...),
    ) -> Union[AnyHistoryContentItem, List[AnyHistoryContentItem]]:
        """Create a new `HDA` or `HDCA` in the given History."""
        return self._create(trans, history_id, type, serialization_params, payload)

    def _create(
        self,
        trans: ProvidesHistoryContext,
        history_id: DecodedDatabaseIdField,
        type: Optional[HistoryContentType],
        serialization_params: SerializationParams,
        payload: CreateHistoryContentPayload,
    ) -> Union[AnyHistoryContentItem, List[AnyHistoryContentItem]]:
        """Create a new `HDA` or `HDCA` in the given History."""
        payload.type = type or payload.type
        return self.service.create(trans, history_id, payload, serialization_params)

    @router.put(
        "/api/histories/{history_id}/contents/{dataset_id}/permissions",
        summary="Set permissions of the given history dataset to the given role ids.",
    )
    def update_permissions(
        self,
        trans: ProvidesHistoryContext = DependsOnTrans,
        history_id: DecodedDatabaseIdField = HistoryIDPathParam,
        dataset_id: DecodedDatabaseIdField = HistoryItemIDPathParam,
        # Using a generic Dict here as an attempt on supporting multiple aliases for the permissions params.
        payload: Dict[str, Any] = Body(
            default=...,
            example=UpdateDatasetPermissionsPayload(),
        ),
    ) -> DatasetAssociationRoles:
        """Set permissions of the given history dataset to the given role ids."""
        update_payload = get_update_permission_payload(payload)
        return self.service.update_permissions(trans, dataset_id, update_payload)

    @router.put(
        "/api/histories/{history_id}/contents",
        summary="Batch update specific properties of a set items contained in the given History.",
    )
    def update_batch(
        self,
        trans: ProvidesHistoryContext = DependsOnTrans,
        history_id: DecodedDatabaseIdField = HistoryIDPathParam,
        serialization_params: SerializationParams = Depends(query_serialization_params),
        payload: UpdateHistoryContentsBatchPayload = Body(...),
    ) -> HistoryContentsResult:
        """Batch update specific properties of a set items contained in the given History.

        If you provide an invalid/unknown property key the request will not fail, but no changes
        will be made to the items.
        """
        result = self.service.update_batch(trans, history_id, payload, serialization_params)
        return HistoryContentsResult.construct(__root__=result)

    @router.put(
        "/api/histories/{history_id}/contents/bulk",
        summary="Executes an operation on a set of items contained in the given History.",
    )
    def bulk_operation(
        self,
        trans: ProvidesHistoryContext = DependsOnTrans,
        history_id: DecodedDatabaseIdField = HistoryIDPathParam,
        filter_query_params: ValueFilterQueryParams = Depends(get_value_filter_query_params),
        payload: HistoryContentBulkOperationPayload = Body(...),
    ) -> HistoryContentBulkOperationResult:
        """Executes an operation on a set of items contained in the given History.

        The items to be processed can be explicitly set or determined by a dynamic query.
        """
        return self.service.bulk_operation(trans, history_id, filter_query_params, payload)

    @router.put(
        "/api/histories/{history_id}/contents/{id}/validate",
        summary="Validates the metadata associated with a dataset within a History.",
    )
    def validate(
        self,
        trans: ProvidesHistoryContext = DependsOnTrans,
        history_id: DecodedDatabaseIdField = HistoryIDPathParam,
        id: DecodedDatabaseIdField = HistoryItemIDPathParam,
    ) -> dict:  # TODO: define a response?
        """Validates the metadata associated with a dataset within a History."""
        return self.service.validate(trans, history_id, id)

    @router.put(
        "/api/histories/{history_id}/contents/{type}s/{id}",
        summary="Updates the values for the history content item with the given ``ID`` and path specified type.",
        operation_id="history_contents__update_typed",
    )
    def update_typed(
        self,
        trans: ProvidesHistoryContext = DependsOnTrans,
        history_id: DecodedDatabaseIdField = HistoryIDPathParam,
        id: DecodedDatabaseIdField = HistoryItemIDPathParam,
        type: HistoryContentType = ContentTypePathParam,
        serialization_params: SerializationParams = Depends(query_serialization_params),
        payload: UpdateHistoryContentsPayload = Body(...),
    ) -> AnyHistoryContentItem:
        """Updates the values for the history content item with the given ``ID``."""
        return self.service.update(
            trans, history_id, id, payload.dict(exclude_unset=True), serialization_params, contents_type=type
        )

    @router.put(
        "/api/histories/{history_id}/contents/{id}",
        summary="Updates the values for the history content item with the given ``ID`` and query specified type. ``/api/histories/{history_id}/contents/{type}s/{id}`` should be used instead.",
        deprecated=True,
        operation_id="history_contents__update_legacy",
    )
    def update_legacy(
        self,
        trans: ProvidesHistoryContext = DependsOnTrans,
        history_id: DecodedDatabaseIdField = HistoryIDPathParam,
        id: DecodedDatabaseIdField = HistoryItemIDPathParam,
        type: HistoryContentType = ContentTypeQueryParam(default=HistoryContentType.dataset),
        serialization_params: SerializationParams = Depends(query_serialization_params),
        payload: UpdateHistoryContentsPayload = Body(...),
    ) -> AnyHistoryContentItem:
        """Updates the values for the history content item with the given ``ID``."""
        return self.service.update(
            trans, history_id, id, payload.dict(exclude_unset=True), serialization_params, contents_type=type
        )

    @router.delete(
        "/api/histories/{history_id}/contents/{type}s/{id}",
        summary="Delete the history content with the given ``ID`` and path specified type.",
        responses=CONTENT_DELETE_RESPONSES,
        operation_id="history_contents__delete_typed",
    )
    def delete_typed(
        self,
        response: Response,
        trans: ProvidesHistoryContext = DependsOnTrans,
        history_id: str = Path(..., description="History ID or any string."),
        id: DecodedDatabaseIdField = HistoryItemIDPathParam,
        type: HistoryContentType = ContentTypePathParam,
        serialization_params: SerializationParams = Depends(query_serialization_params),
        purge: Optional[bool] = PurgeQueryParam,
        recursive: Optional[bool] = RecursiveQueryParam,
        stop_job: Optional[bool] = StopJobQueryParam,
        payload: DeleteHistoryContentPayload = Body(None),
    ):
        """
        Delete the history content with the given ``ID`` and path specified type.

        **Note**: Currently does not stop any active jobs for which this dataset is an output.
        """
        return self._delete(
            response,
            trans,
            id,
            type,
            serialization_params,
            purge,
            recursive,
            stop_job,
            payload,
        )

    @router.delete(
        "/api/histories/{history_id}/contents/{id}",
        summary="Delete the history dataset with the given ``ID``.",
        responses=CONTENT_DELETE_RESPONSES,
        operation_id="history_contents__delete_legacy",
    )
    def delete_legacy(
        self,
        response: Response,
        trans: ProvidesHistoryContext = DependsOnTrans,
        history_id: DecodedDatabaseIdField = HistoryIDPathParam,
        id: DecodedDatabaseIdField = HistoryItemIDPathParam,
        type: HistoryContentType = ContentTypeQueryParam(default=HistoryContentType.dataset),
        serialization_params: SerializationParams = Depends(query_serialization_params),
        purge: Optional[bool] = PurgeQueryParam,
        recursive: Optional[bool] = RecursiveQueryParam,
        stop_job: Optional[bool] = StopJobQueryParam,
        payload: DeleteHistoryContentPayload = Body(None),
    ):
        """
        Delete the history content with the given ``ID`` and query specified type (defaults to dataset).

        **Note**: Currently does not stop any active jobs for which this dataset is an output.
        """
        return self._delete(
            response,
            trans,
            id,
            type,
            serialization_params,
            purge,
            recursive,
            stop_job,
            payload,
        )

    def _delete(
        self,
        response: Response,
        trans: ProvidesHistoryContext,
        id: DecodedDatabaseIdField,
        type: HistoryContentType,
        serialization_params: SerializationParams,
        purge: Optional[bool],
        recursive: Optional[bool],
        stop_job: Optional[bool],
        payload: DeleteHistoryContentPayload,
    ):
        # TODO: should we just use the default payload and deprecate the query params?
        if payload is None:
            payload = DeleteHistoryContentPayload()
        payload.purge = payload.purge or purge is True
        payload.recursive = payload.recursive or recursive is True
        payload.stop_job = payload.stop_job or stop_job is True
        rval = self.service.delete(
            trans,
            id=id,
            serialization_params=serialization_params,
            contents_type=type,
            payload=payload,
        )
        async_result = rval.pop("async_result", None)
        if async_result:
            response.status_code = status.HTTP_202_ACCEPTED
        return rval

    @router.get(
        "/api/histories/{history_id}/contents/archive/{filename}.{format}",
        summary="Build and return a compressed archive of the selected history contents.",
        operation_id="history_contents__archive_named",
    )
    def archive_named(
        self,
        trans: ProvidesHistoryContext = DependsOnTrans,
        history_id: DecodedDatabaseIdField = HistoryIDPathParam,
        filename: str = ArchiveFilenamePathParam,
        format: str = Path(
            description="Output format of the archive.",
            deprecated=True,  # Looks like is not really used?
        ),
        dry_run: Optional[bool] = DryRunQueryParam,
        filter_query_params: FilterQueryParams = Depends(get_filter_query_params),
    ):
        """Build and return a compressed archive of the selected history contents.

        **Note**: this is a volatile endpoint and settings and behavior may change."""
        archive = self.service.archive(trans, history_id, filter_query_params, filename, dry_run)
        if isinstance(archive, HistoryContentsArchiveDryRunResult):
            return archive
        return StreamingResponse(archive.response(), headers=archive.get_headers())

    @router.get(
        "/api/histories/{history_id}/contents/archive",
        summary="Build and return a compressed archive of the selected history contents.",
        operation_id="history_contents__archive",
    )
    def archive(
        self,
        trans: ProvidesHistoryContext = DependsOnTrans,
        history_id: DecodedDatabaseIdField = HistoryIDPathParam,
        filename: Optional[str] = ArchiveFilenameQueryParam,
        dry_run: Optional[bool] = DryRunQueryParam,
        filter_query_params: FilterQueryParams = Depends(get_filter_query_params),
    ):
        """Build and return a compressed archive of the selected history contents.

        **Note**: this is a volatile endpoint and settings and behavior may change."""
        archive = self.service.archive(trans, history_id, filter_query_params, filename, dry_run)
        if isinstance(archive, HistoryContentsArchiveDryRunResult):
            return archive
        return StreamingResponse(archive.response(), headers=archive.get_headers())

    @router.post("/api/histories/{history_id}/contents_from_store", summary="Create contents from store.")
    def create_from_store(
        self,
        trans: ProvidesHistoryContext = DependsOnTrans,
        history_id: DecodedDatabaseIdField = HistoryIDPathParam,
        serialization_params: SerializationParams = Depends(query_serialization_params),
        create_payload: CreateHistoryContentFromStore = Body(...),
    ) -> List[AnyHistoryContentItem]:
        """
        Create history contents from model store.
        Input can be a tarfile created with build_objects script distributed
        with galaxy-data, from an exported history with files stripped out,
        or hand-crafted JSON dictionary.
        """
        return self.service.create_from_store(trans, history_id, create_payload, serialization_params)

    @router.post(
        "/api/histories/{history_id}/contents/datasets/{id}/materialize",
        summary="Materialize a deferred dataset into real, usable dataset.",
    )
    def materialize_dataset(
        self,
        trans: ProvidesHistoryContext = DependsOnTrans,
        history_id: DecodedDatabaseIdField = HistoryIDPathParam,
        id: DecodedDatabaseIdField = HistoryItemIDPathParam,
    ) -> AsyncTaskResultSummary:
        materialize_request = MaterializeDatasetInstanceRequest.construct(
            history_id=history_id,
            source=DatasetSourceType.hda,
            content=id,
        )
        rval = self.service.materialize(trans, materialize_request)
        return rval

    @router.post(
        "/api/histories/{history_id}/materialize",
        summary="Materialize a deferred library or HDA dataset into real, usable dataset in specified history.",
    )
    def materialize_to_history(
        self,
        trans: ProvidesHistoryContext = DependsOnTrans,
        history_id: DecodedDatabaseIdField = HistoryIDPathParam,
        materialize_api_payload: MaterializeDatasetInstanceAPIRequest = Body(...),
    ) -> AsyncTaskResultSummary:
        materialize_request: MaterializeDatasetInstanceRequest = MaterializeDatasetInstanceRequest.construct(
            history_id=history_id, **materialize_api_payload.dict()
        )
        rval = self.service.materialize(trans, materialize_request)
        return rval
