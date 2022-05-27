import axios from "axios";
import { rethrowSimple } from "utils/simple-error";
import { getAppRoot } from "onload/loadConfig";
import { fromSimple, toSimple } from "./model";

/** Workflow data request helper **/
export async function getVersions(id) {
    try {
        const { data } = await axios.get(`${getAppRoot()}api/workflows/${id}/versions`);
        return data;
    } catch (e) {
        rethrowSimple(e);
    }
}

export async function getModule(request_data) {
    try {
        const { data } = await axios.post(`${getAppRoot()}api/workflows/build_module`, request_data);
        return data;
    } catch (e) {
        rethrowSimple(e);
    }
}

export async function refactor(id, actions, dryRun = false) {
    try {
        const requestData = {
            actions: actions,
            style: "editor",
            dry_run: dryRun,
        };
        const { data } = await axios.put(`${getAppRoot()}api/workflows/${id}/refactor`, requestData);
        return data;
    } catch (e) {
        rethrowSimple(e);
    }
}

export async function loadWorkflow(workflow, id, version, appendData) {
    try {
        const versionQuery = Number.isInteger(version) ? `version=${version}` : "";
        const { data } = await axios.get(`${getAppRoot()}workflow/load_workflow?_=true&id=${id}&${versionQuery}`);
        fromSimple(workflow, data, appendData);
        return data;
    } catch (e) {
        console.debug(e);
        rethrowSimple(e);
    }
}

export async function saveWorkflow(workflow) {
    if (workflow.hasChanges) {
        try {
            const requestData = { workflow: toSimple(workflow), from_tool_form: true };
            const { data } = await axios.put(`${getAppRoot()}api/workflows/${workflow.id}`, requestData);
            workflow.name = data.name;
            workflow.hasChanges = false;
            workflow.stored = true;
            workflow.version = data.version;
            workflow.annotation = data.annotation;
            return data;
        } catch (e) {
            rethrowSimple(e);
        }
    }
    return {};
}

export async function getDatatypeMapping() {
    try {
        const { data } = await axios.get(`${getAppRoot()}api/datatypes/mapping`);
        return data;
    } catch (e) {
        rethrowSimple(e);
    }
}

export async function getToolPredictions(requestData) {
    try {
        const { data } = await axios.post(`${getAppRoot()}api/workflows/get_tool_predictions`, requestData);
        return data;
    } catch (e) {
        rethrowSimple(e);
    }
}
