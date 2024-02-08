import axios from "axios";
import { getAppRoot } from "onload/loadConfig";
import { SingleQueryProvider } from "components/providers/SingleQueryProvider";
import { rethrowSimple } from "utils/simple-error";
import { stateIsTerminal } from "./utils";
import { cleanPaginationParameters } from "./utils";

async function jobDetails({ jobId }) {
    const url = `${getAppRoot()}api/jobs/${jobId}?full=True`;
    try {
        const { data } = await axios.get(url);
        return data;
    } catch (e) {
        rethrowSimple(e);
    }
}

async function jobConsoleOutput({ jobId, stdout_position = 0, stdout_length = 0, stderr_position = 0, stderr_length = 0 }) {
    const url = `${getAppRoot()}api/jobs/${jobId}/console_output?stdout_position=${stdout_position}&stdout_length=${stdout_length}&stderr_position=${stderr_position}&stderr_length=${stderr_length}`;
    try {
        const { data } = await axios.get(url);
        return data;
    } catch (e) {
        rethrowSimple(e);
    }
}

async function jobProblems({ jobId }) {
    const url = `${getAppRoot()}api/jobs/${jobId}/common_problems`;
    try {
        const { data } = await axios.get(url);
        return data;
    } catch (e) {
        rethrowSimple(e);
    }
}

export const JobDetailsProvider = SingleQueryProvider(jobDetails, stateIsTerminal);
export const JobConsoleOutputProvider = SingleQueryProvider(jobConsoleOutput, stateIsTerminal);
export const JobProblemProvider = SingleQueryProvider(jobProblems, stateIsTerminal);

export function jobsProvider(ctx, callback, extraParams = {}) {
    const { root, ...requestParams } = ctx;
    const apiUrl = `${root}api/jobs`;
    const cleanParams = cleanPaginationParameters(requestParams);
    const promise = axios.get(apiUrl, { params: { ...cleanParams, ...extraParams } });

    // Must return a promise that resolves to an array of items
    return promise.then((data) => {
        // Pluck the array of items off our axios response
        const items = data.data;
        callback && callback(data);
        // Must return an array of items or an empty array if an error occurred
        return items || [];
    });
}
