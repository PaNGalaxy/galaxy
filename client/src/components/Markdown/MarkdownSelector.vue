<template>
    <span>
        <b-modal
            v-model="modalShow"
            :title="title"
            ok-title="Continue"
            @ok="onOk"
            @cancel="onCancel"
            @hidden="onCancel">
            <div class="ml-2">
                <h2 class="mb-3 h-text">Select {{ labelTitle }} Label:</h2>
                <div v-if="hasLabels">
                    <b-form-radio
                        v-for="(label, index) in labels"
                        :key="index"
                        v-model="selectedValue"
                        class="my-2"
                        name="labels"
                        :value="index">
                        {{ label }}
                    </b-form-radio>
                </div>
                <b-alert v-else show variant="info">
                    No labels found. Please specify labels in the Workflow Editor.
                </b-alert>
                <p class="mt-3 text-muted">
                    You may add new labels by selecting a step in the workflow editor and then editing the corresponding
                    label field in the step form.
                </p>
            </div>
        </b-modal>
    </span>
</template>

<script>
import BootstrapVue from "bootstrap-vue";
import Vue from "vue";

Vue.use(BootstrapVue);

export default {
    props: {
        labelTitle: {
            type: String,
            default: "",
        },
        labels: {
            type: Array,
            default: null,
        },
        argumentName: {
            type: String,
            default: null,
        },
    },
    data() {
        return {
            selectedValue: 0,
            modalShow: true,
        };
    },
    computed: {
        title() {
            return `Insert '${this.argumentName}'`;
        },
        hasLabels() {
            return this.labels && this.labels.length > 0;
        },
    },
    methods: {
        onOk() {
            this.$emit("onOk", this.labels[this.selectedValue]);
        },
        onCancel() {
            this.$emit("onCancel");
        },
    },
};
</script>
