<script setup>
import { BCarousel, BCarouselSlide, BModal } from "bootstrap-vue";
import { storeToRefs } from "pinia";
import { ref, watch } from "vue";

import { setIframeEvents } from "@/components/Upload/utils";
import { useConfig } from "@/composables/config";
import { useUserHistories } from "@/composables/userHistories";
import { useUserStore } from "@/stores/userStore";
import { wait } from "@/utils/utils";


import UploadContainerORNL from "./UploadContainerORNL.vue";
//import UploadContainer from "./UploadContainer.vue";
import ExternalLink from "../ExternalLink.vue";
import HelpText from "../Help/HelpText.vue";

const { currentUser, hasSeenUploadHelp } = storeToRefs(useUserStore());
const { currentHistoryId, currentHistory } = useUserHistories(currentUser);

const { config, isConfigLoaded } = useConfig();

function getDefaultOptions() {
    const baseOptions = {
        title: "Upload from Disk or Web",
        modalStatic: true,
        callback: null,
        immediateUpload: false,
        immediateFiles: null,
    };

    const configOptions = isConfigLoaded.value
        ? {
              chunkUploadSize: config.value.chunk_upload_size,
              fileSourcesConfigured: config.value.file_sources_configured,
              ftpUploadSite: config.value.ftp_upload_site,
              defaultDbKey: config.value.default_genome,
              defaultExtension: config.value.default_extension,
          }
        : {};
    return { ...baseOptions, ...configOptions };
}

const options = ref(getDefaultOptions());
const showModal = ref(false);
const content = ref(null);

function dismiss(result) {
    if (result && options.value.callback) {
        options.value.callback(result);
    }
    showModal.value = false;
}

async function open(overrideOptions) {
    const newOptions = overrideOptions ?? {};
    options.value = { ...getDefaultOptions(), ...newOptions };
    if (options.value.callback) {
        options.value.hasCallback = true;
    }
    showModal.value = true;
    await wait(100);
    if (options.value.immediateUpload) {
        content.value.immediateUpload(options.value.immediateFiles);
    }
}

watch(
    () => showModal.value,
    (modalShown) => {
        setIframeEvents(["galaxy_main"], modalShown);

        // once the modal closes the first time a user sees help, we never show it again
        if (!modalShown && !hasSeenUploadHelp.value) {
            hasSeenUploadHelp.value = true;
        }
    }
);

defineExpose({
    open,
});
</script>

<template>
    <BModal
        v-model="showModal"
        :static="options.modalStatic"
        header-class="no-separator"
        modal-class="ui-modal"
        dialog-class="upload-dialog"
        body-class="upload-dialog-body"
        no-enforce-focus
        hide-footer>
        <template v-slot:modal-header>
            <div class="d-flex justify-content-between w-100">
                <h2 class="title h-sm" tabindex="0">
                    {{ options.title }}
                    <span v-if="currentHistory">
                        to <b>{{ currentHistory.name }}</b>
                    </span>
                </h2>

                <BCarousel v-if="!hasSeenUploadHelp" :interval="4000" no-touch>
                    <BCarouselSlide>
                        <template v-slot:img>
                            <span class="text-nowrap float-right">
                                <ExternalLink href="https://galaxy-upload.readthedocs.io/en/latest/">
                                    Click here
                                </ExternalLink>
                                to check out the
                                <HelpText uri="galaxy.upload.galaxyUploadUtil" text="galaxy-upload" />
                                util!
                            </span>
                        </template>
                    </BCarouselSlide>
                    <BCarouselSlide>
                        <template v-slot:img>
                            <span class="text-nowrap float-right">
                                More info on <HelpText uri="galaxy.upload.ruleBased" text="Rule-based" /> uploads
                                <ExternalLink
                                    href="https://training.galaxyproject.org/training-material/topics/galaxy-interface/tutorials/upload-rules/tutorial.html">
                                    here
                                </ExternalLink>
                                .
                            </span>
                        </template>
                    </BCarouselSlide>
                </BCarousel>
            </div>
        </template>
        <UploadContainerORNL
            v-if="currentHistoryId"
            ref="content"
            :current-user-id="currentUser?.id"
            :current-history-id="currentHistoryId"
            v-bind="options"
            @dismiss="dismiss" />
    </BModal>
</template>

<style>
.upload-dialog {
    width: 900px;
}

.upload-dialog-body {
    height: 550px;
    overflow: initial;
}
</style>
