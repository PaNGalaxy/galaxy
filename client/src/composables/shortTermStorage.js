import { ref, readonly } from "vue";
import axios from "axios";
import { withPrefix } from "utils/redirect";
import { rethrowSimple } from "utils/simple-error";

export const DEFAULT_EXPORT_PARAMS = {
    modelStoreFormat: "rocrate.zip",
    includeFiles: true,
    includeDeleted: false,
    includeHidden: false,
};

const DEFAULT_POLL_DELAY = 1000;
const DEFAULT_OPTIONS = { exportParams: DEFAULT_EXPORT_PARAMS, pollDelayInMs: DEFAULT_POLL_DELAY };

/**
 * Composable to simplify and reuse the logic for downloading objects using Galaxy's Short Term Storage system.
 */
export function useShortTermStorage() {
    let timeout = null;
    let pollDelay = DEFAULT_POLL_DELAY;

    const isPreparing = ref(false);

    async function prepareHistoryDownload(historyId, options = DEFAULT_OPTIONS) {
        return prepareObjectDownload(historyId, "histories", options, false);
    }

    async function downloadHistory(historyId, options = DEFAULT_OPTIONS) {
        return prepareObjectDownload(historyId, "histories", options, true);
    }

    async function prepareWorkflowInvocationDownload(invocationId, options = DEFAULT_OPTIONS) {
        return prepareObjectDownload(invocationId, "invocations", options, false);
    }

    async function downloadWorkflowInvocation(invocationId, options = DEFAULT_OPTIONS) {
        return prepareObjectDownload(invocationId, "invocations", options, true);
    }

    function getDownloadObjectUrl(storageRequestId) {
        const url = withPrefix(`/api/short_term_storage/${storageRequestId}`);
        return url;
    }

    function downloadObjectByRequestId(storageRequestId) {
        const url = getDownloadObjectUrl(storageRequestId);
        window.location.assign(url);
    }

    async function prepareObjectDownload(object_id, object_api, options = DEFAULT_OPTIONS, downloadWhenReady = true) {
        const finalOptions = Object.assign(DEFAULT_OPTIONS, options);
        resetTimeout();
        isPreparing.value = true;
        pollDelay = finalOptions.pollDelayInMs;
        const url = withPrefix(`/api/${object_api}/${object_id}/prepare_store_download`);
        const exportParams = {
            model_store_format: finalOptions.exportParams.modelStoreFormat,
            include_files: finalOptions.exportParams.includeFiles,
            include_deleted: finalOptions.exportParams.includeDeleted,
            include_hidden: finalOptions.exportParams.includeHidden,
        };

        const response = await axios.post(url, exportParams).catch(handleError);
        handleInitialize(response, downloadWhenReady);
    }

    function handleInitialize(response, downloadWhenReady) {
        const storageRequestId = response.data.storage_request_id;
        pollStorageRequestId(storageRequestId, downloadWhenReady);
    }

    function pollStorageRequestId(storageRequestId, downloadWhenReady) {
        const url = withPrefix(`/api/short_term_storage/${storageRequestId}/ready`);
        axios
            .get(url)
            .then((r) => {
                handlePollResponse(r, storageRequestId, downloadWhenReady);
            })
            .catch(handleError);
    }

    function handlePollResponse(response, storageRequestId, downloadWhenReady) {
        const ready = response.data;
        if (ready) {
            isPreparing.value = false;
            if (downloadWhenReady) {
                downloadObjectByRequestId(storageRequestId);
            }
        } else {
            pollAfterDelay(storageRequestId);
        }
    }

    function handleError(err) {
        rethrowSimple(err);
        isPreparing.value = false;
    }

    function pollAfterDelay(storageRequestId) {
        resetTimeout();
        timeout = setTimeout(() => {
            pollStorageRequestId(storageRequestId);
        }, pollDelay);
    }

    function resetTimeout() {
        if (timeout) {
            clearTimeout(timeout);
            timeout = null;
        }
    }

    return {
        /**
         * Starts preparing a history download file in the short term storage.
         * @param {String} historyId The ID of the history to be prepared for download
         * @param {Object} options Options for the download preparation
         */
        prepareHistoryDownload,
        /**
         * Prepares a history download file in the short term storage and starts the download when ready.
         * @param {String} historyId The ID of the history to be downloaded
         * @param {Object} options Options for the download preparation
         */
        downloadHistory,
        /**
         * Starts preparing a workflow invocation download file in the short term storage.
         * @param {String} invocationId The ID of the workflow invocation to be prepared for download
         * @param {Object} options Options for the download preparation
         */
        prepareWorkflowInvocationDownload,
        /**
         * Starts preparing a workflow invocation download file in the short term storage and starts the download when ready.
         * @param {String} invocationId The ID of the workflow invocation to be downloaded
         * @param {Object} options Options for the download preparation
         */
        downloadWorkflowInvocation,
        /**
         * Starts a direct download of the object associated with the given `storageRequestId`.
         * For the download to succeed, the associated `storageRequestId` must be `ready` and not in failure state.
         * @param {String} storageRequestId The storage request ID associated to the object to be downloaded
         */
        downloadObjectByRequestId,
        /**
         * Whether the download is still being prepared.
         */
        isPreparing: readonly(isPreparing),
        /**
         * Given a storageRequestId it returns the download URL for that object.
         * @param {String} storageRequestId The storage request ID associated to the object to be downloaded
         */
        getDownloadObjectUrl,
    };
}
