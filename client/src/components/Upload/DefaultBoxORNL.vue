<script setup>
import { library } from "@fortawesome/fontawesome-svg-core";
import { faCopy, faEdit, faFolderOpen, faLaptop } from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/vue-fontawesome";
import { BButton } from "bootstrap-vue";
import { filesDialog } from "utils/data";
import Vue, { computed, ref } from "vue";
import { getGalaxyInstance } from "app";
import { createDatasetCollection } from "components/History/model/queries";

import { UploadQueue } from "@/utils/upload-queue.js";

import { collectionBuilder } from "./builders.js";
import { defaultModel } from "./model.js";
import { COLLECTION_TYPES, DEFAULT_FILE_NAME, hasBrowserSupport } from "./utils";

import DefaultRow from "./DefaultRow.vue";
import UploadBox from "./UploadBox.vue";
import UploadSelect from "./UploadSelect.vue";
import UploadSelectExtension from "./UploadSelectExtension.vue";

library.add(faCopy, faEdit, faFolderOpen, faLaptop);

const props = defineProps({
    chunkUploadSize: {
        type: Number,
        required: true,
    },
    defaultDbKey: {
        type: String,
        required: true,
    },
    defaultExtension: {
        type: String,
        required: true,
    },
    effectiveExtensions: {
        type: Array,
        required: true,
    },
    fileSourcesConfigured: {
        type: Boolean,
        required: true,
    },
    ftpUploadSite: {
        type: String,
        default: null,
    },
    historyId: {
        type: String,
        required: true,
    },
    multiple: {
        type: Boolean,
        default: true,
    },
    hasCallback: {
        type: Boolean,
        default: false,
    },
    lazyLoad: {
        type: Number,
        default: 50,
    },
    listDbKeys: {
        type: Array,
        required: true,
    },
    isCollection: {
        type: Boolean,
        default: false,
    },
    defaultCollectionName: {
        type: String,
        default: "",
        required: false,
    }
});

const emit = defineEmits(["dismiss", "progress", "updateCollectionName"]);

const collectionType = ref("list");
const counterAnnounce = ref(0);
const counterError = ref(0);
const counterRunning = ref(0);
const counterSuccess = ref(0);
const extension = ref(props.defaultExtension);
const dbKey = ref(props.defaultDbKey);
const queueStopping = ref(false);
const uploadCompleted = ref(0);
const uploadFile = ref(null);
const uploadItems = ref({});
const uploadSize = ref(0);
const queue = ref(createUploadQueue());
const collectionName = ref("");

const counterNonRunning = computed(() => counterAnnounce.value + counterSuccess.value + counterError.value);
const enableBuild = computed(
    () => !isRunning.value && counterAnnounce.value == 0 && counterSuccess.value > 0 && counterError.value == 0
);
const enableReset = computed(() => !isRunning.value && counterNonRunning.value > 0);
const enableStart = computed(() => !isRunning.value && counterAnnounce.value > 0);
const enableSources = computed(() => !isRunning.value && (props.multiple || counterNonRunning.value == 0));
const isRunning = computed(() => counterRunning.value > 0);
const hasRemoteFiles = computed(() => props.fileSourcesConfigured || !!props.ftpUploadSite);
const historyId = computed(() => props.historyId);
const listExtensions = computed(() => props.effectiveExtensions.filter((ext) => !ext.composite_files));
const showHelper = computed(() => Object.keys(uploadItems.value).length === 0);
const uploadValues = computed(() => Object.values(uploadItems.value));
const collectionNameComputed = computed(() => collectionName.value ? collectionName.value: props.defaultCollectionName);


function createUploadQueue() {
    return new UploadQueue({
        announce: eventAnnounce,
        chunkSize: props.chunkUploadSize,
        complete: eventComplete,
        error: eventError,
        get: (index) => uploadItems.value[index],
        multiple: props.multiple,
        progress: eventProgress,
        success: eventSuccess,
        warning: eventWarning,
    });
}

/** Add files to queue */
function addFiles(files, immediate = false) {
    if (!isRunning.value) {
        if (immediate || !props.multiple) {
            eventReset();
        }
        if (props.multiple) {
            queue.value.add(files);
        } else if (files.length > 0) {
            queue.value.add([files[0]]);
        }

        var relativePath = files[0].webkitRelativePath.split("/")[0];
        if (collectionName.value === "") {
            collectionName.value = relativePath;
        }

    }
}

/** A new file has been announced to the upload queue */
function eventAnnounce(index, file) {
    counterAnnounce.value++;
    const uploadModel = {
        ...defaultModel,
        id: index,
        dbKey: dbKey.value,
        extension: extension.value,
        fileData: file,
        fileMode: file.mode || "local",
        fileName: file.name,
        filePath: file.path,
        fileSize: file.size,
        fileUri: file.uri,
    };
    Vue.set(uploadItems.value, index, uploadModel);
}

/** Populates collection builder with uploaded files */
function eventBuild() {
    const Galaxy = getGalaxyInstance();
    const models = {};
    uploadValues.value.forEach((model) => {
        const outputs = model.outputs;
        if (outputs) {
            Object.entries(outputs).forEach((output) => {
                const outputDetails = output[1];
                models[outputDetails.id] = outputDetails;
            });
        } else {
            console.debug("Warning, upload response does not contain outputs.", model);
        }
    });
    var elements = Object.values(models);
    elements = elements.map((element) => ({
        id: element.id,
        name: element.name,
        //TODO: this allows for list:list even if the filter above does not - reconcile
        src: element.src || (element.history_content_type == "dataset" ? "hda" : "hdca"),
    }));
    const queryBody = {
        collection_type: "list",
        name: collectionName.value,
        hide_source_items: true,
        element_identifiers: elements,
        options: {}
    };
    createDatasetCollection({ id: Galaxy.currHistoryPanel.model.id }, queryBody);
    counterRunning.value = 0;
    eventReset();
    emit("dismiss");
}

/** Queue is done */
function eventComplete() {
    uploadValues.value.forEach((model) => {
        if (model.status === "queued") {
            model.status = "init";
        }
    });
    counterRunning.value = 0;
    if (props.isCollection && !(queueStopping.value)) {
        eventBuild();
    }
    queueStopping.value = false;
    collectionName.value = "";
}

/** Create a new file */
function eventCreate() {
    queue.value.add([{ name: DEFAULT_FILE_NAME, size: 0, mode: "new" }]);
}

/** Error */
function eventError(index, message) {
    const it = uploadItems.value[index];
    it.percentage = 100;
    it.status = "error";
    it.info = message;
    uploadCompleted.value += it.fileSize * 100;
    counterAnnounce.value--;
    counterError.value++;
    emit("progress", uploadPercentage(100, it.fileSize), "danger");
}

/** Update model */
function eventInput(index, newData) {
    const it = uploadItems.value[index];
    Object.entries(newData).forEach(([key, value]) => {
        it[key] = value;
    });
}

/** Reflect upload progress */
function eventProgress(index, percentage) {
    const it = uploadItems.value[index];
    it.percentage = percentage;
    emit("progress", uploadPercentage(percentage, it.fileSize));
}

/** Remove model from upload list */
function eventRemove(index) {
    const it = uploadItems.value[index];
    var status = it.status;
    if (status == "success") {
        counterSuccess.value--;
    } else if (status == "error") {
        counterError.value--;
    } else {
        counterAnnounce.value--;
    }
    Vue.delete(uploadItems.value, index);
    queue.value.remove(index);
}

/** Show remote files dialog or FTP files */
function eventRemoteFiles() {
    filesDialog(
        (items) => {
            queue.value.add(
                items.map((item) => {
                    const rval = {
                        mode: "url",
                        name: item.label,
                        size: item.size,
                        path: item.url,
                    };
                    return rval;
                })
            );
        },
        { multiple: true }
    );
}

/** Remove all */
function eventReset() {
    if (!isRunning.value) {
        counterAnnounce.value = 0;
        counterSuccess.value = 0;
        counterError.value = 0;
        queue.value.reset();
        uploadItems.value = {};
        extension.value = props.defaultExtension;
        dbKey.value = props.defaultDbKey;
        emit("progress", 0);
    }
}

/** Success */
function eventSuccess(index, incoming) {
    var it = uploadItems.value[index];
    it.percentage = 100;
    it.status = "success";
    it.outputs = incoming.outputs || incoming.data.outputs || {};
    emit("progress", uploadPercentage(100, it.fileSize));
    uploadCompleted.value += it.fileSize * 100;
    counterAnnounce.value--;
    counterSuccess.value++;
}

/** Start upload process */
function eventStart() {
    if (!isRunning.value && counterAnnounce.value > 0) {
        uploadSize.value = 0;
        uploadCompleted.value = 0;
        uploadValues.value.forEach((model) => {
            if (model.status === "init") {
                model.status = "queued";
                if (!model.targetHistoryId) {
                    // Associate with current history once upload starts
                    // This will not change if the current history is changed during upload
                    model.targetHistoryId = historyId.value;
                }
                uploadSize.value += model.fileSize;
            }
        });
        emit("progress", 0, "success");
        counterRunning.value = counterAnnounce.value;
        queue.value.start();
    }
}

/** Pause upload process */
function eventStop() {
    if (isRunning.value) {
        emit("progress", null, "info");
        queueStopping.value = true;
        queue.value.stop();
    }
}

/** Display warning */
function eventWarning(index, message) {
    const it = uploadItems.value[index];
    it.status = "warning";
    it.info = message;
}

/** Update collection type */
function updateCollectionType(newCollectionType) {
    collectionType.value = newCollectionType;
}

/* Update extension type for all entries */
function updateExtension(newExtension) {
    extension.value = newExtension;
    uploadValues.value.forEach((model) => {
        if (model.status === "init" && model.extension === props.defaultExtension) {
            model.extension = newExtension;
        }
    });
}

/** Update reference dataset for all entries */
function updateDbKey(newDbKey) {
    dbKey.value = newDbKey;
    uploadValues.value.forEach((model) => {
        if (model.status === "init" && model.dbKey === props.defaultDbKey) {
            model.dbKey = newDbKey;
        }
    });
}

/** Calculate percentage of all queued uploads */
function uploadPercentage(percentage, size) {
    return (uploadCompleted.value + percentage * size) / uploadSize.value;
}

function directoryUpload() {
    this.uploadFile.setAttribute("webkitdirectory", "true");
    this.uploadFile.click();
}

function singleFileUpload() {
    this.uploadFile.removeAttribute("webkitdirectory");
    this.uploadFile.click();
}

defineExpose({
    addFiles,
    counterAnnounce,
    listExtensions,
    showHelper,
});
</script>

<template>
    <div class="upload-wrapper">
        <div class="upload-header">
            <div v-if="queueStopping" v-localize>Queue will pause after completing the current file...</div>
            <div v-else-if="counterAnnounce === 0">
                <div v-if="hasBrowserSupport">&nbsp;</div>
                <div v-else>
                    Browser does not support Drag & Drop. Try Firefox 4+, Chrome 7+, IE 10+, Opera 12+ or Safari 6+.
                </div>
            </div>
            <div v-else>
                <div v-if="!isRunning">
                    You added {{ counterAnnounce }} file(s) to the queue. Add more files or click 'Start' to proceed.
                </div>
                <div v-else>Please wait...{{ counterAnnounce }} out of {{ counterRunning }} remaining...</div>
            </div>
        </div>
        <div class="collection-name-div" v-if="isCollection">
            <label>Collection Name: </label>
            <input
                type="text"
                id="collectionNameTextInput"
                :value="collectionNameComputed"
                @input="collectionName = $event.target.value"
                style="margin: 5px;">
        </div>
        <UploadBox @add="addFiles">
            <div v-show="showHelper" class="upload-helper">
                <FontAwesomeIcon class="mr-1" icon="fa-copy" />
                <span v-localize>Drop files here</span>
            </div>
            <div v-show="!showHelper">
                <DefaultRow
                    v-for="[uploadIndex, uploadItem] in Object.entries(uploadItems).slice(0, lazyLoad)"
                    :key="uploadIndex"
                    :index="uploadIndex"
                    :db-key="uploadItem.dbKey"
                    :deferred="uploadItem.deferred"
                    :extension="uploadItem.extension"
                    :file-content="uploadItem.fileContent"
                    :file-mode="uploadItem.fileMode"
                    :file-name="uploadItem.fileName"
                    :file-size="uploadItem.fileSize"
                    :info="uploadItem.info"
                    :list-extensions="isCollection ? null : listExtensions"
                    :list-db-keys="isCollection ? null : listDbKeys"
                    :percentage="uploadItem.percentage"
                    :space-to-tab="uploadItem.spaceToTab"
                    :status="uploadItem.status"
                    :to-posix-lines="uploadItem.toPosixLines"
                    @remove="eventRemove"
                    @input="eventInput" />
                <div
                    v-if="uploadValues.length > lazyLoad"
                    v-localize
                    class="upload-text-message"
                    data-description="lazyload message">
                    Only showing first {{ lazyLoad }} of {{ uploadValues.length }} entries.
                </div>
            </div>
            <input ref="uploadFile" type="file" :multiple="multiple" @change="addFiles($event.target.files)" />
        </UploadBox>
        <div class="upload-footer text-center">
            <span v-if="isCollection" class="upload-footer-title">Collection:</span>
            <UploadSelect
                v-if="isCollection"
                class="upload-footer-collection-type"
                :value="collectionType"
                :disabled="isRunning"
                :options="COLLECTION_TYPES"
                :searchable="false"
                placeholder="Select Type"
                @input="updateCollectionType" />
            <span class="upload-footer-title">Type (set all):</span>
            <UploadSelectExtension
                class="upload-footer-extension"
                :value="extension"
                :disabled="isRunning"
                :list-extensions="listExtensions"
                @input="updateExtension">
            </UploadSelectExtension>
            <span class="upload-footer-title">Reference (set all):</span>
            <UploadSelect
                class="upload-footer-genome"
                :value="dbKey"
                :disabled="isRunning"
                :options="listDbKeys"
                what="reference"
                placeholder="Select Reference"
                @input="updateDbKey" />
        </div>
        <div class="upload-buttons d-flex justify-content-end">
            <BButton id="btn-local" :disabled="!enableSources" @click="singleFileUpload()">
                <FontAwesomeIcon icon="fa-laptop" />
                <span v-localize>Choose local file</span>
            </BButton>
            <BButton id="btn-dir" :disabled="!enableSources" @click="directoryUpload()">
                <FontAwesomeIcon icon="fa-laptop" />
                <span v-localize>Choose local directory</span>
            </BButton>
            <BButton v-if="hasRemoteFiles" id="btn-remote-files" :disabled="!enableSources" @click="eventRemoteFiles">
                <FontAwesomeIcon icon="fa-folder-open" />
                <span v-localize>Choose remote files</span>
            </BButton>
            <BButton id="btn-new" title="Paste/Fetch data" :disabled="!enableSources" @click="eventCreate">
                <FontAwesomeIcon icon="fa-edit" />
                <span v-localize>Paste/Fetch data</span>
            </BButton>
            <BButton
                v-if="isRunning"
                id="btn-stop"
                title="Cancel"
                @click="eventStop">
                <span v-localize>Cancel</span>
            </BButton>
            <BButton
                v-else
                id="btn-start"
                title="Start"
                :variant="enableStart ? 'primary' : null"
                @click="eventStart">
                <span v-localize>Start</span>
            </BButton>
            <BButton id="btn-reset" title="Reset" :disabled="!enableReset" @click="eventReset">
                <span v-localize>Reset</span>
            </BButton>
            <BButton id="btn-close" title="Close" @click="$emit('dismiss')">
                <span v-if="hasCallback" v-localize>Cancel</span>
                <span v-else v-localize>Close</span>
            </BButton>
        </div>
    </div>
</template>
