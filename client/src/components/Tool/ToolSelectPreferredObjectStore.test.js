import { mount } from "@vue/test-utils";
import { getLocalVue } from "tests/jest/helpers";
import { setupSelectableMock } from "@/components/ObjectStore/mockServices";
setupSelectableMock();

import flushPromises from "flush-promises";

import ToolSelectPreferredObjectStore from "./ToolSelectPreferredObjectStore.vue";

const localVue = getLocalVue(true);

function mountComponent() {
    const wrapper = mount(ToolSelectPreferredObjectStore, {
        propsData: { toolPreferredObjectStoreId: null },
        localVue,
    });
    return wrapper;
}

import { ROOT_COMPONENT } from "@/utils/navigation";

const PREFERENCES = ROOT_COMPONENT.preferences;

describe("ToolSelectPreferredObjectStore.vue", () => {
    it("updates object store to default on selection null", async () => {
        const wrapper = mountComponent();
        await flushPromises();
        const els = wrapper.findAll(PREFERENCES.object_store_selection.option_buttons.selector);
        expect(els.length).toBe(3);
        const galaxyDefaultOption = wrapper.find(
            PREFERENCES.object_store_selection.option_button({ object_store_id: "__null__" }).selector
        );
        expect(galaxyDefaultOption.exists()).toBeTruthy();
        await galaxyDefaultOption.trigger("click");
        await flushPromises();
        const errorEl = wrapper.find(".object-store-selection-error");
        expect(errorEl.exists()).toBeFalsy();
        const emitted = wrapper.emitted();
        expect(emitted["updated"][0][0]).toEqual(null);
    });
});
