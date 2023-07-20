import Vue from "vue";
import VueRouter from "vue-router";
import { getAppRoot } from "onload/loadConfig";
import { getGalaxyInstance } from "app";
import { patchRouterPush } from "./router-push";

// these modules are mounted below the masthead.
import Analysis from "entry/analysis/modules/Analysis";
import Home from "entry/analysis/modules/Home";
import CenterFrame from "entry/analysis/modules/CenterFrame";
import Login from "entry/analysis/modules/Login";
import WorkflowEditorModule from "entry/analysis/modules/WorkflowEditor";

// routes
import AdminRoutes from "entry/analysis/routes/admin-routes";
import LibraryRoutes from "entry/analysis/routes/library-routes";
import StorageDashboardRoutes from "entry/analysis/routes/storageDashboardRoutes";

// child components
import AboutGalaxy from "components/AboutGalaxy.vue";
import CarbonEmissionsCalculations from "components/JobMetrics/CarbonEmissions/CarbonEmissionsCalculations";
import Citations from "components/Citation/Citations";
import ClientError from "components/ClientError";
import CollectionEditView from "components/Collections/common/CollectionEditView";
import CustomBuilds from "components/User/CustomBuilds";
import DatasetAttributes from "components/DatasetInformation/DatasetAttributes";
import DatasetDetails from "components/DatasetInformation/DatasetDetails";
import DatasetError from "components/DatasetInformation/DatasetError";
import DatasetList from "components/Dataset/DatasetList";
import AvailableDatatypes from "components/AvailableDatatypes/AvailableDatatypes";
import FormGeneric from "components/Form/FormGeneric";
import GridShared from "components/Grid/GridShared";
import GridHistory from "components/Grid/GridHistory";
import PageList from "components/Page/PageList";
import HistoryImport from "components/HistoryImport";
import HistoryView from "components/History/HistoryView";
import HistoryPublished from "components/History/HistoryPublished";
import HistoryPublishedList from "components/History/HistoryPublishedList";
import HistoryInvocations from "components/Workflow/HistoryInvocations";
import HistoryMultipleView from "components/History/Multiple/MultipleView";
import NotificationsList from "components/Notifications/NotificationsList.vue";
import InteractiveTools from "components/InteractiveTools/InteractiveTools";
import InvocationReport from "components/Workflow/InvocationReport";
import JobDetails from "components/JobInformation/JobDetails";
import NewUserWelcome from "components/NewUserWelcome/NewUserWelcome";
import PageDisplay from "components/PageDisplay/PageDisplay";
import PageEditor from "components/PageEditor/PageEditor";
import Sharing from "components/Sharing/Sharing";
import StoredWorkflowInvocations from "components/Workflow/StoredWorkflowInvocations";
import ToolsJson from "components/ToolsView/ToolsSchemaJson/ToolsJson";
import ToolsList from "components/ToolsList/ToolsList";
import ToolSuccess from "components/Tool/ToolSuccess";
import TourList from "components/Tour/TourList";
import TourRunner from "components/Tour/TourRunner";
import TrsImport from "components/Workflow/Import/TrsImport";
import TrsSearch from "components/Workflow/Import/TrsSearch";
import UserInvocations from "components/Workflow/UserInvocations";
import UserPreferences from "components/User/UserPreferences";
import UserPreferencesForm from "components/User/UserPreferencesForm";
import VisualizationsList from "components/Visualizations/Index";
import WorkflowExport from "components/Workflow/WorkflowExport";
import VisualizationPublished from "components/Visualizations/VisualizationPublished";
import WorkflowImport from "components/Workflow/WorkflowImport";
import WorkflowList from "components/Workflow/WorkflowList";
import WorkflowPublished from "components/Workflow/WorkflowPublished";
import { APIKey } from "components/User/APIKey";
import { NotificationsPreferences } from "components/User/Notifications";
import { CloudAuth } from "components/User/CloudAuth";
import { ExternalIdentities } from "components/User/ExternalIdentities";
import { HistoryExport } from "components/HistoryExport/index";
import HistoryExportTasks from "components/History/Export/HistoryExport";
import HistoryArchiveWizard from "@/components/History/Archiving/HistoryArchiveWizard.vue";
import HistoryArchive from "@/components/History/Archiving/HistoryArchive.vue";

Vue.use(VueRouter);

// patches $router.push() to trigger an event and hide duplication warnings
patchRouterPush(VueRouter);

// redirect anon users
function redirectAnon() {
    const Galaxy = getGalaxyInstance();
    if (!Galaxy.user || !Galaxy.user.id) {
        return "/";
    }
}

// redirect logged in users
function redirectLoggedIn() {
    const Galaxy = getGalaxyInstance();
    if (Galaxy.user.id) {
        return "/";
    }
}

function redirectIf(condition, path) {
    if (condition) {
        return path;
    }
}

// produces the client router
export function getRouter(Galaxy) {
    const router = new VueRouter({
        base: getAppRoot(),
        mode: "history",
        routes: [
            ...AdminRoutes,
            ...LibraryRoutes,
            ...StorageDashboardRoutes,
            /** Login entry route */
            {
                path: "/login/start",
                component: Login,
                redirect: redirectLoggedIn(),
            },
            /** Page editor */
            {
                path: "/pages/editor",
                component: PageEditor,
                props: (route) => ({
                    pageId: route.query.id,
                }),
            },
            /** Workflow editor */
            { path: "/workflows/edit", component: WorkflowEditorModule },
            /** Published resources routes */
            {
                path: "/published/history",
                component: HistoryPublished,
                props: (route) => ({ id: route.query.id }),
            },
            {
                path: "/published/page",
                component: PageDisplay,
                props: (route) => ({ pageId: route.query.id }),
            },
            {
                path: "/published/visualization",
                component: VisualizationPublished,
                props: (route) => ({ id: route.query.id }),
            },
            {
                path: "/published/workflow",
                component: WorkflowPublished,
                props: (route) => ({ id: route.query.id }),
            },
            {
                name: "error",
                path: "/client-error/",
                component: ClientError,
                props: true,
            },
            /** Analysis routes */
            {
                path: "/",
                component: Analysis,
                children: [
                    {
                        path: "",
                        alias: "root",
                        component: Home,
                        props: (route) => ({ config: Galaxy.config, query: route.query }),
                    },
                    {
                        path: "about",
                        component: AboutGalaxy,
                    },
                    {
                        path: "carbon_emissions_calculations",
                        component: CarbonEmissionsCalculations,
                    },
                    {
                        path: "custom_builds",
                        component: CustomBuilds,
                        redirect: redirectAnon(),
                    },
                    {
                        path: "collection/:collection_id/edit",
                        component: CollectionEditView,
                        props: true,
                    },
                    {
                        path: "datasets/:datasetId/edit",
                        component: DatasetAttributes,
                        props: true,
                    },
                    {
                        path: "datasets/list",
                        component: DatasetList,
                    },
                    {
                        path: "datasets/:datasetId/details",
                        name: "DatasetDetails",
                        component: DatasetDetails,
                        props: true,
                    },
                    {
                        path: "datasets/:datasetId/preview",
                        component: CenterFrame,
                        props: (route) => ({
                            src: `/datasets/${route.params.datasetId}/display/?preview=True`,
                        }),
                    },
                    {
                        // legacy route, potentially used by 3rd parties
                        path: "datasets/:datasetId/show_params",
                        component: DatasetDetails,
                        props: true,
                    },
                    {
                        path: "datasets/:datasetId/error",
                        component: DatasetError,
                        props: true,
                    },
                    {
                        path: "datatypes",
                        component: AvailableDatatypes,
                    },
                    {
                        path: "histories/import",
                        component: HistoryImport,
                    },
                    {
                        path: "histories/citations",
                        component: Citations,
                        props: (route) => ({
                            id: route.query.id,
                            source: "histories",
                        }),
                    },
                    {
                        path: "histories/rename",
                        component: FormGeneric,
                        props: (route) => ({
                            url: `/history/rename?id=${route.query.id}`,
                            redirect: "/histories/list",
                        }),
                    },
                    {
                        path: "histories/sharing",
                        component: Sharing,
                        props: (route) => ({
                            id: route.query.id,
                            pluralName: "Histories",
                            modelClass: "History",
                        }),
                    },
                    {
                        path: "histories/permissions",
                        component: FormGeneric,
                        props: (route) => ({
                            url: `/history/permissions?id=${route.query.id}`,
                            redirect: "/histories/list",
                        }),
                    },
                    {
                        path: "histories/view",
                        component: HistoryView,
                        props: (route) => ({
                            id: route.query.id,
                        }),
                    },
                    {
                        path: "histories/view_multiple",
                        component: HistoryMultipleView,
                        props: true,
                    },
                    {
                        path: "histories/list_published",
                        component: HistoryPublishedList,
                        props: true,
                    },
                    {
                        path: "histories/archived",
                        component: HistoryArchive,
                    },
                    {
                        path: "histories/:actionId",
                        component: GridHistory,
                        props: true,
                        redirect: redirectAnon(),
                    },
                    {
                        path: "histories/:historyId/export",
                        get component() {
                            return Galaxy.config.enable_celery_tasks ? HistoryExportTasks : HistoryExport;
                        },
                        props: true,
                    },
                    {
                        path: "histories/:historyId/archive",
                        component: HistoryArchiveWizard,
                        props: true,
                    },
                    {
                        path: "histories/:historyId/invocations",
                        component: HistoryInvocations,
                        props: true,
                    },
                    {
                        path: "interactivetool_entry_points/list",
                        component: InteractiveTools,
                    },
                    {
                        path: "jobs/submission/success",
                        component: ToolSuccess,
                        props: true,
                    },
                    {
                        path: "jobs/:jobId/view",
                        component: JobDetails,
                        props: true,
                    },
                    {
                        path: "pages/create",
                        component: FormGeneric,
                        props: (route) => {
                            let url = "/page/create";
                            const invocation_id = route.query.invocation_id;
                            if (invocation_id) {
                                url += `?invocation_id=${invocation_id}`;
                            }
                            return {
                                url: url,
                                redirect: "/pages/list",
                                active_tab: "user",
                            };
                        },
                    },
                    {
                        path: "pages/edit",
                        component: FormGeneric,
                        props: (route) => ({
                            url: `/page/edit?id=${route.query.id}`,
                            redirect: "/pages/list",
                            active_tab: "user",
                        }),
                    },
                    {
                        path: "pages/sharing",
                        component: Sharing,
                        props: (route) => ({
                            id: route.query.id,
                            pluralName: "Pages",
                            modelClass: "Page",
                        }),
                    },
                    {
                        path: "pages/:actionId",
                        component: PageList,
                        props: (route) => ({
                            published: route.params.actionId == "list_published" ? true : false,
                        }),
                    },
                    {
                        path: "tours",
                        component: TourList,
                    },
                    {
                        path: "tours/:tourId",
                        component: TourRunner,
                        props: true,
                    },
                    {
                        path: "tools/list",
                        component: ToolsList,
                        props: (route) => {
                            return {
                                ...route.query,
                            };
                        },
                    },
                    {
                        path: "tools/json",
                        component: ToolsJson,
                    },
                    {
                        path: "user",
                        component: UserPreferences,
                        props: {
                            enableQuotas: Galaxy.config.enable_quotas,
                            userId: Galaxy.user.id,
                        },
                        redirect: redirectAnon(),
                    },
                    {
                        path: "user/api_key",
                        component: APIKey,
                        redirect: redirectAnon(),
                    },
                    {
                        path: "user/cloud_auth",
                        component: CloudAuth,
                        redirect: redirectAnon(),
                    },
                    {
                        path: "user/external_ids",
                        component: ExternalIdentities,
                        redirect: redirectAnon(),
                    },
                    {
                        path: "user/notifications",
                        component: NotificationsList,
                        redirect: redirectIf(!Galaxy.config.enable_notification_system, "/") || redirectAnon(),
                    },
                    {
                        path: "user/notifications/preferences",
                        component: NotificationsPreferences,
                        redirect: redirectAnon(),
                    },
                    {
                        path: "user/:formId",
                        component: UserPreferencesForm,
                        props: true,
                        redirect: redirectAnon(),
                    },
                    {
                        path: "visualizations",
                        component: VisualizationsList,
                        props: (route) => ({
                            datasetId: route.query.dataset_id,
                        }),
                    },
                    {
                        path: "visualizations/edit",
                        component: FormGeneric,
                        props: (route) => ({
                            url: `/visualization/edit?id=${route.query.id}`,
                            redirect: "/visualizations/list",
                            active_tab: "visualization",
                        }),
                    },
                    {
                        path: "visualizations/sharing",
                        component: Sharing,
                        props: (route) => ({
                            id: route.query.id,
                            pluralName: "Visualizations",
                            modelClass: "Visualization",
                        }),
                    },
                    {
                        path: "visualizations/:actionId",
                        component: GridShared,
                        props: (route) => ({
                            actionId: route.params.actionId,
                            item: "visualization",
                            plural: "Visualizations",
                        }),
                    },
                    {
                        path: "welcome/new",
                        component: NewUserWelcome,
                    },
                    {
                        path: "workflows/create",
                        component: FormGeneric,
                        props: {
                            url: "/workflow/create",
                            redirect: "/workflows/edit",
                            active_tab: "workflow",
                            submitTitle: "Create",
                            submitIcon: "fa-check",
                            cancelRedirect: "/workflows/list",
                        },
                    },
                    {
                        path: "workflows/export",
                        component: WorkflowExport,
                        props: (route) => ({
                            id: route.query.id,
                        }),
                    },
                    {
                        path: "workflows/import",
                        component: WorkflowImport,
                    },
                    {
                        path: "workflows/invocations",
                        component: UserInvocations,
                    },
                    {
                        path: "workflows/invocations/report",
                        component: InvocationReport,
                        props: (route) => ({
                            invocationId: route.query.id,
                        }),
                    },
                    {
                        path: "workflows/list_published",
                        component: WorkflowList,
                        props: (route) => ({
                            published: true,
                        }),
                    },
                    {
                        path: "workflows/list",
                        component: WorkflowList,
                        redirect: redirectAnon(),
                        props: (route) => ({
                            importMessage: route.query["message"],
                            importStatus: route.query["status"],
                            query: route.query["query"],
                        }),
                    },
                    {
                        path: "workflows/run",
                        component: Home,
                        props: (route) => ({
                            config: Galaxy.config,
                            query: { workflow_id: route.query.id },
                        }),
                    },
                    {
                        path: "workflows/sharing",
                        component: Sharing,
                        props: (route) => ({
                            id: route.query.id,
                            pluralName: "Workflows",
                            modelClass: "Workflow",
                        }),
                    },
                    {
                        path: "workflows/trs_import",
                        component: TrsImport,
                        props: (route) => ({
                            queryTrsServer: route.query.trs_server,
                            queryTrsId: route.query.trs_id,
                            queryTrsVersionId: route.query.trs_version,
                            queryTrsUrl: route.query.trs_url,
                            isRun: route.query.run_form == "true",
                        }),
                    },
                    {
                        path: "workflows/trs_search",
                        component: TrsSearch,
                    },
                    {
                        path: "workflows/:storedWorkflowId/invocations",
                        component: StoredWorkflowInvocations,
                        props: true,
                    },
                ],
            },
        ],
    });

    function checkAdminAccessRequired(to) {
        // Check parent route hierarchy to see if we require admin access here.
        // Access is required if *any* component in the hierarchy requires it.
        if (to.matched.some((record) => record.meta.requiresAdmin === true)) {
            const isAdmin = getGalaxyInstance()?.user?.isAdmin();
            return !isAdmin;
        }
        return false;
    }

    function checkRegisteredUserAccessRequired(to) {
        // Check parent route hierarchy to see if we require registered user access here.
        // Access is required if *any* component in the hierarchy requires it.
        if (to.matched.some((record) => record.meta.requiresRegisteredUser === true)) {
            const isAnonymous = getGalaxyInstance()?.user?.isAnonymous();
            return isAnonymous;
        }
        return false;
    }

    router.beforeEach(async (to, from, next) => {
        // TODO: merge anon redirect functionality here for more standard handling

        const isAdminAccessRequired = checkAdminAccessRequired(to);
        if (isAdminAccessRequired) {
            const error = new Error(`Admin access required for '${to.path}'.`);
            error.name = "AdminRequired";
            next(error);
        }

        const isRegisteredUserAccessRequired = checkRegisteredUserAccessRequired(to);
        if (isRegisteredUserAccessRequired) {
            const error = new Error(`Registered user access required for '${to.path}'.`);
            error.name = "RegisteredUserRequired";
            next(error);
        }
        next();
    });

    router.onError((error) => {
        router.push({ name: "error", params: { error: error } });
    });

    return router;
}
