import { default as Masthead } from "./Masthead.vue";
import { mount } from "@vue/test-utils";
import { getLocalVue } from "jest/helpers";
import Scratchbook from "layout/scratchbook";
import { fetchMenu } from "layout/menu";
import { loadWebhookMenuItems } from "./_webhooks";

jest.mock("app");
jest.mock("layout/menu");
jest.mock("./_webhooks");

describe("Masthead.vue", () => {
    let wrapper;
    let localVue;
    let scratchbook;
    let quotaRendered;
    let quotaEl;
    let tabs;

    function stubFetchMenu() {
        return tabs;
    }

    function stubLoadWebhooks(items) {
        items.push({
            id: "extension",
            title: "Extension Point",
            menu: false,
            url: "extension_url",
        });
    }

    fetchMenu.mockImplementation(stubFetchMenu);
    loadWebhookMenuItems.mockImplementation(stubLoadWebhooks);

    beforeEach(() => {
        localVue = getLocalVue();
        quotaRendered = false;
        quotaEl = null;

        const quotaMeter = {
            setElement: function (el) {
                quotaEl = el;
            },
            render: function () {
                quotaRendered = true;
            },
        };

        tabs = [
            // Main Analysis Tab..
            {
                id: "analysis",
                title: "Analyze",
                menu: false,
                url: "root",
            },
            {
                id: "shared",
                title: "Shared Items",
                menu: [{ title: "_menu_title", url: "_menu_url", target: "_menu_target" }],
            },
            // Hidden tab (pre-Vue framework supported this, not sure it is used
            // anywhere?)
            {
                id: "hiddentab",
                title: "Hidden Title",
                menu: false,
                hidden: true,
            },
        ];
        const initialActiveTab = "shared";

        // scratchbook assumes this is a Backbone collection - mock that out.
        tabs.add = (x) => {
            tabs.push(x);
            return x;
        };
        scratchbook = new Scratchbook({});
        const mastheadState = {
            quotaMeter,
            frame: scratchbook,
        };

        wrapper = mount(Masthead, {
            propsData: {
                mastheadState,
                initialActiveTab,
            },
            localVue,
        });
    });

    it("should disable brand when displayGalaxyBrand is true", async () => {
        expect(wrapper.find(".navbar-brand-title").text()).toBe("Galaxy");
        wrapper.setProps({ brand: "Foo " });
        await localVue.nextTick();
        expect(wrapper.find(".navbar-brand-title").text()).toBe("Galaxy Foo");
        wrapper.setProps({ displayGalaxyBrand: false });
        await localVue.nextTick();
        expect(wrapper.find(".navbar-brand-title").text()).toBe("Foo");
    });

    it("set quota element and renders it", () => {
        expect(quotaEl).not.toBeNull();
        expect(quotaRendered).toBe(true);
    });

    it("should render simple tab item links", () => {
        expect(wrapper.findAll("li.nav-item").length).toBe(6);
        // Ensure specified link title respected.
        expect(wrapper.find("#analysis a").text()).toBe("Analyze");
        expect(wrapper.find("#analysis a").attributes("href")).toBe("/root");
    });

    it("should render tab items with menus", () => {
        // Ensure specified link title respected.
        expect(wrapper.find("#shared a").text()).toBe("Shared Items");
        expect(wrapper.find("#shared").classes("dropdown")).toBe(true);

        expect(wrapper.findAll("#shared .dropdown-menu li").length).toBe(1);
        expect(wrapper.find("#shared .dropdown-menu li a").attributes().href).toBe("/_menu_url");
        expect(wrapper.find("#shared .dropdown-menu li a").attributes().target).toBe("_menu_target");
        expect(wrapper.find("#shared .dropdown-menu li a").text()).toBe("_menu_title");
    });

    it("should make hidden tabs hidden", () => {
        expect(wrapper.find("#analysis").attributes().style).not.toEqual(expect.stringContaining("display: none"));
        expect(wrapper.find("#hiddentab").attributes().style).toEqual(expect.stringContaining("display: none"));
    });

    it("should highlight the active tab", () => {
        expect(wrapper.find("#analysis").classes("active")).toBe(false);
        expect(wrapper.find("#shared").classes("active")).toBe(true);
    });

    it("should display scratchbook button", async () => {
        expect(wrapper.find("#enable-scratchbook a span").classes("fa-th")).toBe(true);
        expect(scratchbook.active).toBe(false);
        wrapper.find("#enable-scratchbook a").trigger("click");
        await localVue.nextTick();
        expect(scratchbook.active).toBe(true);
    });

    it("should load webhooks on creation", async () => {
        expect(wrapper.find("#extension a").text()).toBe("Extension Point");
    });
});
