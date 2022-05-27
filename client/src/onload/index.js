// Bootstrap overwrites .tooltip() method, load it after jquery-ui
// (which is loaded everywhere via libs/jquery.custom.js)
import "bootstrap";
import "@galaxyproject/bootstrap-tour";

// Galaxy core styles
import "scss/base.scss";

// Set up webpack's public path; nothing to import but the module has side
// effects fixing webpack globals.
import "./publicPath";

// Module exports appear as objects on window.config in the browser
export { standardInit } from "./standardInit";
export { initializations$, addInitialization, prependInitialization, clearInitQueue } from "./initQueue";
export { config$, set as setConfig, get as getConfig, getAppRoot } from "./loadConfig";
export { getRootFromIndexLink } from "./getRootFromIndexLink";

// Client-side configuration variables (based on environment)
import config from "config";

if (!config.testBuild === true) {
    console.log("Configs:", config.name, config);
}
