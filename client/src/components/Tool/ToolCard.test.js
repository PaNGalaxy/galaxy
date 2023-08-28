import { createPinia } from "pinia";
import { mount } from "@vue/test-utils";
import { getLocalVue, mockModule } from "tests/jest/helpers";
import MockAdapter from "axios-mock-adapter";
import axios from "axios";
import ToolCard from "./ToolCard";
import Vuex from "vuex";
import { configStore } from "store/configStore";
import { useUserStore } from "stores/userStore";

const localVue = getLocalVue();

const createStore = () => {
    return new Vuex.Store({
        modules: {
            config: mockModule(configStore, { config: {} }),
        },
    });
};

describe("ToolCard", () => {
    let wrapper;
    let axiosMock;
    let userStore;

    beforeEach(() => {
        axiosMock = new MockAdapter(axios);
        axiosMock.onGet(`/api/webhooks`).reply(200, []);

        const pinia = createPinia();
        const store = createStore();

        wrapper = mount(ToolCard, {
            propsData: {
                id: "identifier",
                version: "version",
                title: "title",
                description: "description",
                sustainVersion: false,
                options: {
                    id: "options.id",
                    versions: [],
                    sharable_url: "options.sharable_url",
                    help: "options.help",
                    citations: false,
                },
                messageText: "messageText",
                messageVariant: "warning",
                disabled: false,
            },
            stubs: {
                ToolSourceMenuItem: { template: "<div></div>" },
            },
            localVue,
            store,
            pinia,
            provide: { store },
        });
        userStore = useUserStore();
        userStore.currentUser = {
            id: "user.id",
            email: "user.email",
            is_admin: true,
            preferences: {},
        };
    });

    it("shows props", async () => {
        const title = wrapper.find("h1");
        expect(title.text()).toBe("title");

        const description = wrapper.find("span[itemprop='description']");
        expect(description.text()).toBe("description");

        const dropdownHeader = wrapper.find(".tool-dropdown");
        expect(dropdownHeader.attributes("title")).toBe("Options");

        const dropdownItems = wrapper.findAll(".dropdown-item");
        expect(dropdownItems.length).toBe(5);

        const backdrop = wrapper.findAll(".portlet-backdrop");
        expect(backdrop.length).toBe(0);

        await wrapper.setProps({ disabled: true });
        const backdropActive = wrapper.findAll(".portlet-backdrop");
        expect(backdropActive.length).toBe(1);
    });
});
