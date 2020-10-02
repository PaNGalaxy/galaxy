<template>
    <span>
        <MarkdownSelector
            v-if="selectedShow"
            :initial-value="argumentType"
            :argument-name="argumentName"
            :labels="labels"
            :label-title="selectedLabelTitle"
            @onOk="onOk"
            @onCancel="onCancel"
        />
        <DataDialog v-if="dataShow" :history="dataHistoryId" format="id" @onOk="onData" @onCancel="onCancel" />
        <DatasetCollectionDialog
            v-if="dataCollectionShow"
            :history="dataHistoryId"
            format="id"
            @onOk="onDataCollection"
            @onCancel="onCancel"
        />
        <BasicSelectionDialog
            v-if="jobShow"
            :get-data="getJobs"
            :is-encoded="true"
            title="Job"
            label-key="id"
            @onOk="onJob"
            @onCancel="onCancel"
        />
        <BasicSelectionDialog
            v-if="invocationShow"
            :get-data="getInvocations"
            :is-encoded="true"
            title="Invocation"
            label-key="id"
            @onOk="onInvocation"
            @onCancel="onCancel"
        />
        <BasicSelectionDialog
            v-if="workflowShow"
            :get-data="getWorkflows"
            title="Workflow"
            leaf-icon="fa fa-sitemap fa-rotate-270"
            label-key="name"
            @onOk="onWorkflow"
            @onCancel="onCancel"
        />
    </span>
</template>

<script>
import axios from "axios";
import Vue from "vue";
import BootstrapVue from "bootstrap-vue";
import { getAppRoot } from "onload/loadConfig";
import { getCurrentGalaxyHistory } from "utils/data";
import MarkdownSelector from "./MarkdownSelector";
import DataDialog from "components/DataDialog/DataDialog";
import DatasetCollectionDialog from "components/SelectionDialog/DatasetCollectionDialog";
import BasicSelectionDialog from "components/SelectionDialog/BasicSelectionDialog";

Vue.use(BootstrapVue);

export default {
    components: {
        MarkdownSelector,
        BasicSelectionDialog,
        DatasetCollectionDialog,
        DataDialog,
    },
    props: {
        argumentName: {
            type: String,
            default: null,
        },
        argumentType: {
            type: String,
            default: null,
        },
        labels: {
            type: Array,
            default: null,
        },
        useLabels: {
            type: Boolean,
            default: false,
        },
    },
    data() {
        return {
            selectorConfig: {
                job_id: {
                    labelTitle: "Step",
                },
                invocation_id: {
                    labelTitle: "Step",
                },
                history_dataset_id: {
                    labelTitle: "Output",
                },
                history_dataset_collection_id: {
                    labelTitle: "Output",
                },
            },
            jobsUrl: `${getAppRoot()}api/jobs`,
            workflowsUrl: `${getAppRoot()}api/workflows`,
            invocationsUrl: `${getAppRoot()}api/invocations`,
            selectedShow: false,
            workflowShow: false,
            jobShow: false,
            invocationShow: false,
            dataShow: false,
            dataCollectionShow: false,
        };
    },
    computed: {
        selectedLabelTitle() {
            const config = this.selectorConfig[this.argumentType];
            return (config && config.labelTitle) || "Select Label";
        },
    },
    created() {
        this.onCreate();
    },
    methods: {
        getInvocations() {
            return axios.get(this.invocationsUrl);
        },
        getJobs() {
            return axios.get(this.jobsUrl);
        },
        getWorkflows() {
            return axios.get(this.workflowsUrl);
        },
        onData(response) {
            this.dataShow = false;
            this.$emit("onInsert", `${this.argumentName}(history_dataset_id=${response})`);
        },
        onDataCollection(response) {
            this.dataCollectionShow = false;
            this.$emit("onInsert", `${this.argumentName}(history_dataset_collection_id=${response.id})`);
        },
        onJob(response) {
            this.jobShow = false;
            this.$emit("onInsert", `${this.argumentName}(job_id=${response.id})`);
        },
        onInvocation(response) {
            this.invocationShow = false;
            this.$emit("onInsert", `${this.argumentName}(invocation_id=${response.id})`);
        },
        onWorkflow(response) {
            this.workflowShow = false;
            this.$emit("onInsert", `workflow_display(workflow_id=${response.id})`);
        },
        onCreate() {
            if (this.argumentType == "workflow_id") {
                this.workflowShow = true;
            } else if (this.argumentType == "history_dataset_id") {
                if (this.useLabels) {
                    this.selectedShow = true;
                } else {
                    getCurrentGalaxyHistory().then((historyId) => {
                        this.dataShow = true;
                        this.dataHistoryId = historyId;
                    });
                }
            } else if (this.argumentType == "history_dataset_collection_id") {
                if (this.useLabels) {
                    this.selectedShow = true;
                } else {
                    getCurrentGalaxyHistory().then((historyId) => {
                        this.dataCollectionShow = true;
                        this.dataHistoryId = historyId;
                    });
                }
            } else if (this.argumentType == "invocation_id") {
                if (this.useLabels) {
                    this.selectedShow = true;
                } else {
                    this.invocationShow = true;
                }
            } else if (this.argumentType == "job_id") {
                if (this.useLabels) {
                    this.selectedShow = true;
                } else {
                    this.jobShow = true;
                }
            }
        },
        onOk(selectedLabel) {
            selectedLabel = selectedLabel || "<ENTER LABEL>";
            this.selectedShow = false;
            if (this.argumentType == "history_dataset_id") {
                if (this.useLabels) {
                    this.$emit("onInsert", `${this.argumentName}(output="${selectedLabel}")`);
                } else {
                    getCurrentGalaxyHistory().then((historyId) => {
                        this.dataShow = true;
                        this.dataHistoryId = historyId;
                    });
                }
            } else if (this.argumentType == "history_dataset_collection_id") {
                if (this.useLabels) {
                    this.$emit("onInsert", `${this.argumentName}(output="${selectedLabel}")`);
                } else {
                    getCurrentGalaxyHistory().then((historyId) => {
                        this.dataCollectionShow = true;
                        this.dataHistoryId = historyId;
                    });
                }
            } else if (this.argumentType == "job_id") {
                if (this.useLabels) {
                    this.$emit("onInsert", `${this.argumentName}(step="${selectedLabel}")`);
                } else {
                    this.jobShow = true;
                }
            } else if (this.argumentType == "invocation_id") {
                if (this.useLabels) {
                    this.$emit("onInsert", `${this.argumentName}(step="${selectedLabel}")`);
                } else {
                    this.invocationShow = true;
                }
            }
        },
        onCancel() {
            this.dataCollectionShow = false;
            this.selectedShow = false;
            this.workflowShow = false;
            this.jobShow = false;
            this.invocationShow = false;
            this.dataShow = false;
            this.$emit("onCancel");
        },
    },
};
</script>