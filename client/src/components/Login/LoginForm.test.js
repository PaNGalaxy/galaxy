import axios from "axios";
import MockAdapter from "axios-mock-adapter";
import { mount } from "@vue/test-utils";
import { getLocalVue } from "tests/jest/helpers";
import MountTarget from "./LoginForm";

const localVue = getLocalVue(true);

describe("LoginForm", () => {
    let wrapper;
    let axiosMock;

    beforeEach(() => {
        axiosMock = new MockAdapter(axios);
        wrapper = mount(MountTarget, {
            propsData: {
                sessionCsrfToken: "sessionCsrfToken",
            },
            localVue,
            stubs: {
                ExternalLogin: true,
            },
        });
    });

    afterEach(() => {
        axiosMock.reset();
    });

    it("basics", async () => {
        const cardHeader = wrapper.find(".card-header");
        expect(cardHeader.text()).toBe("Welcome to Galaxy, please log in");
        const inputs = wrapper.findAll("input");
        expect(inputs.length).toBe(2);
        const usernameField = inputs.at(0);
        expect(usernameField.attributes("type")).toBe("text");
        await usernameField.setValue("test_user");
        const pwdField = inputs.at(1);
        expect(pwdField.attributes("type")).toBe("password");
        await pwdField.setValue("test_pwd");
        const submitButton = wrapper.find("button[type='submit']");
        await submitButton.trigger("submit");
        const postedData = JSON.parse(axiosMock.history.post[0].data);
        expect(postedData.login).toBe("test_user");
        expect(postedData.password).toBe("test_pwd");
    });

    it("props", async () => {
        const $register = "[id='register-toggle']";
        expect(wrapper.findAll($register).length).toBe(0);
        await wrapper.setProps({
            allowUserCreation: true,
            enableOidc: true,
            showWelcomeWithLogin: true,
            welcomeUrl: "welcome_url",
        });
        const register = wrapper.find($register);
        expect(register.text()).toBeLocalizationOf("Register here.");
        const welcomePage = wrapper.find("iframe");
        expect(welcomePage.attributes("src")).toBe("welcome_url");
    });

    it("connect external provider", async () => {
        const external_email = "test@test.com";
        const provider_id = "test_provider";
        const provider_label = "Provider";
        await wrapper.setData({
            connectExternalEmail: external_email,
            connectExternalProvider: provider_id,
            connectExternalLabel: provider_label,
        });
        expect(wrapper.find(".card-header").exists()).toBe(false);
        const alert = wrapper.find(".alert");
        expect(alert.classes()).toContain("alert-info");
        expect(alert.text()).toContain(`There already exists a user with the email ${external_email}`);
        expect(alert.text()).toContain(`In order to associate this account with ${provider_label}`);
        const inputs = wrapper.findAll("input");
        expect(inputs.length).toBe(2);
        const usernameField = inputs.at(0);
        expect(usernameField.attributes("type")).toBe("text");
        expect(usernameField.element.disabled).toBe(true);
        expect(usernameField.element.value).not.toBe("");
        expect(usernameField.element.value).toContain(external_email);
        const pwdField = inputs.at(1);
        expect(pwdField.attributes("type")).toBe("password");
        expect(pwdField.element.value).toBe("");
        await pwdField.setValue("test_pwd");
        const submitButton = wrapper.find("button[type='submit']");
        await submitButton.trigger("submit");
        const postedData = JSON.parse(axiosMock.history.post[0].data);
        expect(postedData.login).toBe(external_email);
        expect(postedData.password).toBe("test_pwd");
        const postedURL = axiosMock.history.post[0].url;
        expect(postedURL).toBe("/user/login");
    });
});
