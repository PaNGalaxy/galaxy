import { getGalaxyInstance } from "app";
import UI_MODAL from "mvc/ui/ui-modal";
import _l from "utils/localization";

export function collectionCreatorModalSetup(options, Galaxy = null) {
    Galaxy = Galaxy || getGalaxyInstance();
    const modal = Galaxy.modal || new UI_MODAL.View();
    const promise = new Promise((then, reject) => {
        options.oncancel = function () {
            modal.hide();
            reject("cancelled");
        };
        options.oncreate = function (creator, response) {
            modal.hide();
            then(response);
        };
    });
    const showEl = function (el) {
        modal.show({
            title: options.title || _l("Create a collection"),
            body: el,
            width: "85%",
            height: "100%",
            xlarge: true,
            closing_events: true,
        });
    };
    return { promise, options, showEl };
}
