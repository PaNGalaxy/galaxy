/**
 * Watches for key changes in global Galaxy app variable and transfers them into Vuex via commits.
 * This should be deleted when Galaxy is finally done, as features get moved into Vuex individual
 * sync functions can be removed from the plugin
 */

import { defer } from "rxjs";
import { shareReplay } from "rxjs/operators";
import { getGalaxyInstance } from "app";
import { waitForInit } from "utils/observable/waitForInit";

// store subscriptions
import { syncUserToGalaxy } from "store/userStore";
import { syncConfigToGalaxy } from "store/configStore";
import { syncCurrentHistoryToGalaxy } from "components/History/model/syncCurrentHistoryToGalaxy";
import { isBetaHistoryOpen } from "components/History/adapters/betaToggle";

export const syncVuextoGalaxy = (store) => {
    const globalGalaxy$ = defer(() => {
        return waitForInit(() => getGalaxyInstance()).pipe(shareReplay(1));
    });

    // sets current user when glaaxy changes
    syncUserToGalaxy(globalGalaxy$, store);

    // configuration
    syncConfigToGalaxy(globalGalaxy$, store);

    // Update Vuex with legacy galaxy history changes only when beta panel is closed.
    if (!isBetaHistoryOpen()) {
        syncCurrentHistoryToGalaxy(globalGalaxy$, store);
    }
};
