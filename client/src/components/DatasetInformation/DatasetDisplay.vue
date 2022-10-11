<template>
  <ConfigProvider v-slot="{ config }">
  <DatasetProvider :id="datasetId" v-slot="{ result: dataset, loading }" :key="forceView">
    <iframe id="dataset-display-iframe" v-if="!loading && (!config.file_view_threshold || dataset.file_size < config.file_view_threshold || forceView )"
            :src="`${dataset.id}/display/?preview=False`"
            width="100%"
            height="100%"
            allowfullscreen
            frameborder=0
    >
    </iframe>
    <div v-else-if="!loading">
      <div id="warning" class="warningmessage">
        This is a large file of <div style="display: inline" v-html="bytesToString(dataset.file_size)"/>.
        Are you sure you want to view/download it?
      </div>
      <button @click="showLargeFile" id="view-large-file" class="">Yes, view/download the file</button>
    </div>
  </DatasetProvider>
  </ConfigProvider>

</template>

<script>
import {DatasetProvider} from "components/providers";
import Utils from "../../utils/utils";
import { getGalaxyInstance } from "app";
import ConfigProvider from "components/providers/ConfigProvider";

export default {
  data() {
    return {
      forceView: false,
      threshold : getGalaxyInstance()?.config?.file_view_threshold || 0,
    };
  },
  components: {
    ConfigProvider,
    DatasetProvider,
  },
  props: {
    datasetId: {
      type: String,
      required: true,
    },
  },
  methods: {
    bytesToString(raw_size) {
      return Utils.bytesToString(raw_size);
    },
    showLargeFile() {
    this.forceView = true;
    }

  },
};
</script>
