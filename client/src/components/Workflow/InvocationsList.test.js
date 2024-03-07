import "jest-location-mock";

import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import axios from "axios";
import MockAdapter from "axios-mock-adapter";
import { formatDistanceToNow, parseISO } from "date-fns";
import { getLocalVue } from "tests/jest/helpers";
import VueRouter from "vue-router";

import InvocationsList from "./InvocationsList";
import mockInvocationData from "./test/json/invocation.json";

const localVue = getLocalVue();
localVue.use(VueRouter);
const router = new VueRouter();

const pinia = createTestingPinia();
describe("InvocationsList.vue", () => {
    let axiosMock;
    let wrapper;
    let $router;

    beforeEach(async () => {
        axiosMock = new MockAdapter(axios);
    });

    afterEach(() => {
        axiosMock.restore();
    });

    describe(" with empty invocation list", () => {
        beforeEach(async () => {
            axiosMock.onAny().reply(200, [], { total_matches: "0" });
            const propsData = {
                ownerGrid: false,
            };
            wrapper = mount(InvocationsList, {
                propsData,
                localVue,
            });
        });

        it("title should be shown", async () => {
            expect(wrapper.find("#invocations-title").text()).toBe("Workflow Invocations");
        });

        it("no invocations message should be shown when not loading", async () => {
            expect(wrapper.find("#no-invocations").exists()).toBe(true);
        });
    });

    describe("with server error", () => {
        beforeEach(async () => {
            axiosMock.onAny().reply(403, { err_msg: "this is a problem" });
            const propsData = {
                ownerGrid: false,
            };
            wrapper = mount(InvocationsList, {
                propsData,
                localVue,
                pinia,
            });
        });

        it("renders error message", async () => {
            expect(wrapper.find(".index-grid-message").text()).toContain("this is a problem");
        });
    });

    describe("for a workflow with an empty invocation list", () => {
        beforeEach(async () => {
            axiosMock
                .onGet("/api/invocations", {
                    params: { limit: 50, offset: 0, include_terminal: false, workflow_id: "abcde145678" },
                })
                .reply(200, [], { total_matches: "0" });
            const propsData = {
                ownerGrid: false,
                storedWorkflowName: "My Workflow",
                storedWorkflowId: "abcde145678",
            };
            wrapper = mount(InvocationsList, {
                propsData,
                localVue,
                pinia,
            });
        });

        it("title should be shown", async () => {
            expect(wrapper.find("#invocations-title").text()).toBe('Workflow Invocations for workflow "My Workflow"');
        });

        it("no invocations message should be shown when not loading", async () => {
            expect(wrapper.find("#no-invocations").exists()).toBe(true);
        });

        it("should not render pager", async () => {
            expect(wrapper.find(".gx-invocations-grid-pager").exists()).toBeFalsy();
        });
    });

    describe("for a history with an empty invocation list", () => {
        beforeEach(async () => {
            axiosMock
                .onGet("/api/invocations", {
                    params: { limit: 50, offset: 0, include_terminal: false, history_id: "abcde145678" },
                })
                .reply(200, [], { total_matches: "0" });
            const propsData = {
                ownerGrid: false,
                historyName: "My History",
                historyId: "abcde145678",
            };
            wrapper = mount(InvocationsList, {
                propsData,
                localVue,
            });
        });

        it("title should be shown", async () => {
            expect(wrapper.find("#invocations-title").text()).toBe('Workflow Invocations for history "My History"');
        });

        it("no invocations message should be shown when not loading", async () => {
            expect(wrapper.find("#no-invocations").exists()).toBe(true);
        });

        it("should not render pager", async () => {
            expect(wrapper.find(".gx-invocations-grid-pager").exists()).toBeFalsy();
        });
    });

    describe("with invocation", () => {
        beforeEach(async () => {
            axiosMock
                .onGet("/api/invocations", { params: { limit: 50, offset: 0, include_terminal: false } })
                .reply(200, [mockInvocationData], { total_matches: "1" });
            const propsData = {
                ownerGrid: false,
                loading: false,
            };
            wrapper = mount(InvocationsList, {
                propsData,
                computed: {
                    getStoredWorkflowNameByInstanceId: (state) => (id) => "workflow name",
                    getStoredWorkflowIdByInstanceId: (state) => (id) => {
                        return "workflowId";
                    },
                    getStoredWorkflowByInstanceId: (state) => (id) => {
                        return { id: "workflowId" };
                    },
                    getHistoryById: (state) => (id) => {
                        return { id: "historyId" };
                    },
                    getHistoryNameById: () => () => "history name",
                },
                stubs: {
                    "workflow-invocation-state": {
                        template: "<span/>",
                    },
                },
                localVue,
                pinia,
                router,
            });
            $router = wrapper.vm.$router;
        });

        it("renders one row", async () => {
            const rows = wrapper.findAll("tbody > tr").wrappers;
            expect(rows.length).toBe(1);
            const row = rows[0];
            const columns = row.findAll("td");
            expect(columns.at(1).text()).toBe("workflow name");
            expect(columns.at(2).text()).toBe("history name");
            expect(columns.at(3).text()).toBe(
                formatDistanceToNow(parseISO(`${mockInvocationData.create_time}Z`), { addSuffix: true })
            );
            expect(columns.at(4).text()).toBe("scheduled");
            expect(columns.at(5).text()).toBe("");
        });

        it("toggles detail rendering", async () => {
            let rows = wrapper.findAll("tbody > tr").wrappers;
            expect(rows.length).toBe(1);
            await wrapper.find(".toggle-invocation-details").trigger("click");
            rows = wrapper.findAll("tbody > tr").wrappers;
            expect(rows.length).toBe(3);
            await wrapper.find(".toggle-invocation-details").trigger("click");
            rows = wrapper.findAll("tbody > tr").wrappers;
            expect(rows.length).toBe(1);
        });

        it("calls switchHistory", async () => {
            const mockMethod = jest.fn();
            wrapper.vm.switchHistory = mockMethod;
            await wrapper.find("#switch-to-history").trigger("click");
            expect(mockMethod).toHaveBeenCalled();
        });

        it("calls executeWorkflow", async () => {
            const mockMethod = jest.fn();
            $router.push = mockMethod;
            await wrapper.find(".workflow-run").trigger("click");
            expect(mockMethod).toHaveBeenCalledWith("/workflows/run?id=workflowId");
        });

        it("should not render pager", async () => {
            expect(wrapper.find(".gx-invocations-grid-pager").exists()).toBeFalsy();
        });
    });

    describe("paginations", () => {
        beforeEach(async () => {
            axiosMock
                .onGet("/api/invocations", { params: { limit: 1, offset: 0, include_terminal: false } })
                .reply(200, [mockInvocationData], { total_matches: "3" });
            const propsData = {
                ownerGrid: false,
                loading: false,
                defaultPerPage: 1,
            };
            wrapper = mount(InvocationsList, {
                propsData,
                computed: {
                    getStoredWorkflowNameByInstanceId: (state) => (id) => "workflow name",
                    getStoredWorkflowByInstanceId: (state) => (id) => {
                        return { id: "workflowId" };
                    },
                    getHistoryById: (state) => (id) => {
                        return { id: "historyId" };
                    },
                    getHistoryNameById: () => () => "history name",
                },
                stubs: {
                    "workflow-invocation-state": {
                        template: "<span/>",
                    },
                },
                localVue,
            });
        });

        it("title should render pager", async () => {
            expect(wrapper.find(".gx-invocations-grid-pager").exists()).toBeTruthy();
        });
    });
});
