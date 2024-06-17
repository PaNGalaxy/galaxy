import { getGalaxyInstance } from "app";
import _l from "utils/localization";
import { userLogout } from "utils/logout";

import { useUserStore } from "@/stores/userStore";

export function fetchMenu(options = {}) {
    const Galaxy = getGalaxyInstance();
    const menu = [];
    //
    // Analyze data tab.
    //
    menu.push({
        id: "analysis",
        url: "/",
        tooltip: _l("Tools and Current History"),
        icon: "fa-home",
        target: "_top",
    });

    //
    // Workflow tab.
    //
    menu.push({
        id: "workflow",
        title: _l("Workflow"),
        tooltip: _l("Chain tools into workflows"),
        disabled: !Galaxy.user.id,
        url: "/workflows/list",
    });

    //
    // Visualization tab.
    //
    if (Galaxy.config.visualizations_visible) {
        menu.push({
            id: "visualization",
            title: _l("Visualize"),
            tooltip: _l("Visualize datasets"),
            disabled: !Galaxy.user.id,
            url: "/visualizations",
        });
    }

    //
    // 'Data' tab.
    //
    if (Galaxy.user.id) {
        menu.push({
            id: "resources",
            title: _l("Data"),
            url: "javascript:void(0)",
            tooltip: _l("Access resources"),
            menu: [
                {
                    title: _l("Data Libraries"),
                    url: "/libraries",
                },
                {
                    title: _l("Datasets"),
                    url: "/datasets/list",
                },
                {
                    title: _l("Histories"),
                    url: "/histories/list",
                },
                {
                    title: _l("Pages"),
                    url: "/pages/list",
                },
                {
                    title: _l("Visualizations"),
                    url: "/visualizations/list",
                },
                {
                    title: _l("Workflows"),
                    url: "/workflows/list",
                },
                {
                    title: _l("Workflow Invocations"),
                    url: "/workflows/invocations",
                },
            ],
        });
    } else {
        menu.push({
            id: "resources",
            title: _l("Data"),
            url: "javascript:void(0)",
            tooltip: _l("Access published resources"),
            menu: [
                {
                    title: _l("Data Libraries"),
                    url: "/libraries",
                },
                {
                    title: _l("Histories"),
                    url: "/histories/list_published",
                },
                {
                    title: _l("Pages"),
                    url: "/pages/list_published",
                },
                {
                    title: _l("Visualizations"),
                    url: "/visualizations/list_published",
                },
                {
                    title: _l("Workflows"),
                    url: "/workflows/list_published",
                },
            ],
        });
    }

    //
    // Admin.
    //
    if (Galaxy.user.get("is_admin")) {
        menu.push({
            id: "admin",
            title: _l("Admin"),
            url: "/admin",
            tooltip: _l("Administer this Galaxy"),
            cls: "admin-only",
            onclick: () => {
                const userStore = useUserStore();
                userStore.toggleSideBar("admin");
            },
        });
    }

    //
    // Help tab.
    //
    const helpTab = {
        id: "help",
        title: _l("Help"),
        url: "javascript:void(0)",
        tooltip: _l("Support, contact, and community"),
        menu: [
            {
                title: _l("Galaxy Help"),
                url: options.helpsite_url,
                target: "_blank",
                hidden: !options.helpsite_url,
            },
            {
                title: _l("Support"),
                url: options.support_url,
                target: "_blank",
                hidden: !options.support_url,
            },
            {
                title: _l("Videos"),
                url: options.screencasts_url,
                target: "_blank",
                hidden: !options.screencasts_url,
            },
            {
                title: _l("Community Hub"),
                url: options.wiki_url,
                target: "_blank",
                hidden: !options.wiki_url,
            },
            {
                title: _l("How to Cite Galaxy"),
                url: options.citation_url,
                target: "_blank",
            },
            {
                title: _l("Interactive Tours"),
                url: "/tours",
            },
            {
                title: _l("About"),
                url: "/about",
            },
            {
                title: _l("Terms and Conditions"),
                url: options.terms_url,
                target: "_blank",
                hidden: !options.terms_url,
            },
        ],
    };
    menu.push(helpTab);

    //
    // User tab.
    //
    let userTab = {};
    if (!Galaxy.user.id) {
        if (options.allow_user_creation) {
            userTab = {
                id: "user",
                title: _l("Log in or Register"),
                cls: "loggedout-only",
                url: "/login",
                tooltip: _l("Log in or register a new account"),
                target: "_top",
            };
        } else {
            userTab = {
                id: "user",
                title: _l("Login"),
                cls: "loggedout-only",
                tooltip: _l("Login"),
                url: "/login",
                target: "_top",
            };
        }
    } else {
        userTab = {
            id: "user",
            title: _l("User"),
            cls: "loggedin-only",
            url: "javascript:void(0)",
            tooltip: _l("Account and saved data"),
            menu: [
                {
                    title: `${_l("Signed in as")} ${
                        Galaxy.user.get("username") ? Galaxy.user.get("username") : Galaxy.user.get("email")
                    }`,
                    disabled: true,
                },
                { divider: true },
            ],
        };
        if (Galaxy.config.interactivetools_enable) {
            userTab.menu.push({
                title: _l("Active Interactive Tools"),
                url: "/interactivetool_entry_points/list",
            });
        }
        if (Galaxy.config.enable_notification_system) {
            userTab.menu.push({
                title: _l("Notifications"),
                url: "/user/notifications",
            });
        }
        userTab.menu.push({ divider: true });
        userTab.menu.push({
            title: _l("Preferences"),
            url: "/user",
        });
        userTab.menu.push({
            title: _l("Sign Out"),
            onclick: userLogout,
            hidden: Galaxy.config.single_user || Galaxy.config.hide_sign_out,
        });
    }
    menu.push(userTab);
    return menu;
}
