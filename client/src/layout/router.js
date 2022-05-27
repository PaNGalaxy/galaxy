import $ from "jquery";
import Backbone from "backbone";
import { getAppRoot } from "onload/loadConfig";
import { getGalaxyInstance } from "app";
import QUERY_STRING from "utils/query-string-parsing";
import Ui from "mvc/ui/ui-misc";

const Router = Backbone.Router.extend({
    // TODO: not many client routes at this point - fill and remove from server.
    // since we're at root here, this may be the last to be routed entirely on the client.
    initialize: function (page, options) {
        this.page = page;
        this.options = options;
    },

    executeUseRouter: function (url) {
        const prefix = getAppRoot();
        if (url.startsWith(prefix)) {
            url = url.replace(prefix, "/");
        }
        return this.push(url);
    },

    /** helper to push a new navigation state */
    push: function (url, data) {
        data = data || {};
        data.__identifer = Math.random().toString(36).substr(2);
        url += url.indexOf("?") == -1 ? "?" : "&";
        const bustParam = $.param(data, true);
        url += bustParam;
        const Galaxy = getGalaxyInstance();
        Galaxy.params = data;
        this.navigate(url, { trigger: true });
        window.history.replaceState(window.history.state, "", window.location.pathname.replace(bustParam, ""));
    },

    /** override to parse query string into obj and send to each route */
    execute: function (callback, args, name) {
        const Galaxy = getGalaxyInstance();
        Galaxy.debug("router execute:", callback, args, name);
        const queryObj = QUERY_STRING.parse(args.pop());
        args.push(queryObj);
        if (callback) {
            if (this.authenticate(args, name)) {
                callback.apply(this, args);
            } else {
                this.access_denied();
            }
        }
    },

    authenticate: function (args, name) {
        return true;
    },

    access_denied: function () {
        this.page.display(
            new Ui.Message({
                status: "danger",
                message: "You must be logged in with proper credentials to make this request.",
                persistent: true,
            })
        );
    },
});

export default Router;
