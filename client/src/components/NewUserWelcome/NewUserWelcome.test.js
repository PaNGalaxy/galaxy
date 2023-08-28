import { mount } from "@vue/test-utils";
import { getLocalVue } from "tests/jest/helpers";
import testData from "./testData.json";
import NewUserWelcome from "./NewUserWelcome.vue";
import { getResource } from "./getResource";

const localVue = getLocalVue();
import MockConfigProvider from "../providers/MockConfigProvider";

jest.mock("./getResource");

// mock resource connector
getResource.mockImplementation(() => null);

describe("New user first view", () => {
    let wrapper;

    beforeEach(async () => {
        wrapper = mount(NewUserWelcome, {
            localVue,
            stubs: {
                ConfigProvider: MockConfigProvider({ id: "fakeconfig" }),
            },
        });
        wrapper.setData({ loaded: true, newUser: testData });
    });

    it("Contains standard header", async () => {
        expect(wrapper.find(".main-header").text()).toContain("Welcome to Galaxy");
    });

    it("Starts on overall topics", async () => {
        wrapper.setData({ position: [] });
        expect(wrapper.vm.depth).toBe(0);
        expect(wrapper.vm.currentNode.topics).toHaveLength(1);
    });

    it("Displays second tier of topics", async () => {
        wrapper.setData({ position: [0] });
        expect(wrapper.vm.depth).toBe(1);
        expect(wrapper.vm.currentNode.topics).toHaveLength(2);
        expect(wrapper.vm.currentNode.title).toBe("testTopic");
    });

    it("Goes into subtopic", async () => {
        wrapper.setData({ position: [0, 0] });
        expect(wrapper.vm.depth).toBe(2);
        expect(wrapper.vm.currentNode.title).toBe("subtopicTitle");
        expect(wrapper.vm.currentNode.slides).toHaveLength(3);
    });
});
