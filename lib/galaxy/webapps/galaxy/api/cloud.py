"""
API operations on Cloud-based storages, such as Amazon Simple Storage Service (S3).
"""

import logging

from fastapi import (
    Body,
    Response,
    status,
)
from pydantic import Required

from galaxy.managers.cloud import CloudManager
from galaxy.managers.context import ProvidesHistoryContext
from galaxy.managers.datasets import DatasetSerializer
from galaxy.schema.cloud import (
    CloudDatasets,
    CloudDatasetsResponse,
    CloudObjects,
    DatasetSummaryList,
    StatusCode,
)
from galaxy.webapps.galaxy.api import (
    depends,
    Router,
)
from . import DependsOnTrans

log = logging.getLogger(__name__)

router = Router(tags=["cloud"])


@router.cbv
class FastAPICloudController:
    cloud_manager: CloudManager = depends(CloudManager)
    datasets_serializer: DatasetSerializer = depends(DatasetSerializer)

    @router.get(
        "/api/cloud/storage",
        summary="Lists cloud-based buckets (e.g., S3 bucket, Azure blob) user has defined. Is not yet implemented",
        deprecated=True,
    )
    def index(
        self,
        response: Response,
    ):
        # TODO: This can be implemented leveraging PluggedMedia objects (part of the user-based object store project)
        response.status_code = status.HTTP_501_NOT_IMPLEMENTED
        return StatusCode(detail="Not yet implemented.", status=501)

    @router.post(
        "/api/cloud/storage/get",
        summary="Gets given objects from a given cloud-based bucket to a Galaxy history.",
        deprecated=True,
    )
    def get(
        self,
        payload: CloudObjects = Body(default=Required),
        trans: ProvidesHistoryContext = DependsOnTrans,
    ) -> DatasetSummaryList:
        datasets = self.cloud_manager.get(
            trans=trans,
            history_id=payload.history_id,
            bucket_name=payload.bucket,
            objects=payload.objects,
            authz_id=payload.authz_id,
            input_args=payload.input_args,
        )
        rtv = []
        for dataset in datasets:
            rtv.append(self.datasets_serializer.serialize_to_view(dataset, view="summary"))
        return DatasetSummaryList.construct(__root__=rtv)

    @router.post(
        "/api/cloud/storage/send",
        summary="Sends given dataset(s) in a given history to a given cloud-based bucket.",
        deprecated=True,
    )
    def send(
        self,
        payload: CloudDatasets = Body(default=Required),
        trans: ProvidesHistoryContext = DependsOnTrans,
    ) -> CloudDatasetsResponse:
        log.info(
            msg="Received api/send request for `{}` datasets using authnz with id `{}`, and history `{}`."
            "".format(
                "all the dataset in the given history" if not payload.dataset_ids else len(payload.dataset_ids),
                payload.authz_id,
                payload.history_id,
            )
        )

        sent, failed = self.cloud_manager.send(
            trans=trans,
            history_id=payload.history_id,
            bucket_name=payload.bucket,
            authz_id=payload.authz_id,
            dataset_ids=payload.dataset_ids,
            overwrite_existing=payload.overwrite_existing,
        )
        return CloudDatasetsResponse(sent_dataset_labels=sent, failed_dataset_labels=failed, bucket_name=payload.bucket)
