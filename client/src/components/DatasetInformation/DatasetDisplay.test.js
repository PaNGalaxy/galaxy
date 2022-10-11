import {mount} from "@vue/test-utils";
import {getLocalVue} from "jest/helpers";
import DatasetDisplay from "./DatasetDisplay";
import datasetResponse from "./testData/datasetResponse";
import flushPromises from "flush-promises";
import MockConfigProvider from "components/providers/MockConfigProvider";

const DATASET_ID = "FOO_DATASET_ID";

const mockDatasetProvider = {
    render() {
        return this.$scopedSlots.default({
            loading: false,
            result: datasetResponse,
        });
    },
};

const localVue = getLocalVue();

async function mountDatasetDisplayWrapper(threshold) {
    const propsData = {
        datasetId: DATASET_ID,
    };
    const wrapper = mount(DatasetDisplay, {
        propsData,
        stubs: {
            DatasetProvider: mockDatasetProvider,
            ConfigProvider: MockConfigProvider({
                file_view_threshold: threshold,
            }),
        },
        localVue,
    });
    await flushPromises();
    return wrapper;
}

describe("DatasetDisplay/DatasetDisplay", () => {
    it("dataset message should not exist for small files", async () => {
        const wrapper = await mountDatasetDisplayWrapper(0);
        const message = wrapper.find("#warning");
        expect(message.exists()).toBeFalsy();
    });
    it("dataset message should warn about large file", async () => {
        const wrapper = await mountDatasetDisplayWrapper(10);
        const message = wrapper.find("#warning");
        expect(message.exists()).toBeTruthy();
        const text = message.text();
        expect(text).toContain("93 b");
    });
});
