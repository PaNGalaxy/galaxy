import { mount, createLocalVue } from "@vue/test-utils";
import Attributes from "./Attributes";
import { UntypedParameters } from "./modules/parameters";

jest.mock("app");

const TEST_ANNOTATION = "my cool annotation";
const TEST_NAME = "workflow_name";

describe("Attributes", () => {
    it("test attributes", async () => {
        const localVue = createLocalVue();
        const untypedParameters = new UntypedParameters();
        untypedParameters.getParameter("workflow_parameter_0");
        untypedParameters.getParameter("workflow_parameter_1");
        const wrapper = mount(Attributes, {
            propsData: {
                id: "workflow_id",
                name: TEST_NAME,
                tags: ["workflow_tag_0", "workflow_tag_1"],
                parameters: untypedParameters,
                versions: ["workflow_version_0"],
                annotation: TEST_ANNOTATION,
            },
            stubs: {
                LicenseSelector: true,
            },
            localVue,
        });
        expect(wrapper.find(`[itemprop='description']`).attributes("content")).toBe(TEST_ANNOTATION);
        expect(wrapper.find(`[itemprop='name']`).attributes("content")).toBe(TEST_NAME);

        const name = wrapper.find("#workflow-name");
        expect(name.element.value).toBe(TEST_NAME);
        wrapper.setProps({ name: "new_workflow_name" });
        await localVue.nextTick();
        expect(name.element.value).toBe("new_workflow_name");
        const parameters = wrapper.findAll(".list-group-item");
        expect(parameters.length).toBe(2);
        expect(parameters.at(0).text()).toBe("1: workflow_parameter_0");
        expect(parameters.at(1).text()).toBe("2: workflow_parameter_1");
        expect(wrapper.find("#workflow-annotation").element.value).toBe(TEST_ANNOTATION);
    });
});
