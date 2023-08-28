/**
 * Monitors and requests the summary of recently changed history items and commits the
 * results to the history items and other attached stores. The initial update time threshold
 * corresponds to the module import time. Once the watcher is called, continuous requests are
 * submitted, delayed only by the throttle period and the request response time.
 */

import defaultStore from "store/index";
import { useHistoryItemsStore } from "stores/history/historyItemsStore";
import { urlData } from "utils/url";
import { loadSet } from "utils/setCache";
import { useHistoryStore } from "stores/historyStore";
import { getCurrentHistoryFromServer } from "stores/services/history.services";
import { getGalaxyInstance } from "app";

const limit = 1000;

let throttlePeriod = 3000;
let watchTimeout = null;

// last time the history has changed
let lastUpdateTime = null;

// last time changed history items have been requested
let lastRequestDate = new Date();

// We only want to kick this off once we're actively watching history
let watchingVisibility = false;

function setVisibilityThrottle() {
    if (document.visibilityState === "visible") {
        // Poll every 3 seconds when visible
        throttlePeriod = 3000;
        rewatchHistory();
    } else {
        // Poll every 60 seconds when hidden/backgrounded
        throttlePeriod = 60000;
    }
}

export async function watchHistoryOnce(store) {
    const historyStore = useHistoryStore();
    const historyItemsStore = useHistoryItemsStore();
    // "Reset" watchTimeout so we don't queue up watchHistory calls in rewatchHistory.
    watchTimeout = null;
    // get current history
    const checkForUpdate = new Date();
    const history = await getCurrentHistoryFromServer(lastUpdateTime);
    historyItemsStore.setLastCheckedTime(checkForUpdate);
    if (!history || !history.id) {
        return;
    }

    // continue if the history update time has changed
    if (!lastUpdateTime || lastUpdateTime < history.update_time) {
        const historyId = history.id;
        lastUpdateTime = history.update_time;
        historyItemsStore.setLastUpdateTime();
        // execute request to obtain recently changed items
        const params = {
            v: "dev",
            limit: limit,
            q: "update_time-ge",
            qv: lastRequestDate.toISOString(),
        };
        // request detailed info only for the expanded datasets
        const detailedIds = getCurrentlyExpandedHistoryContentIds();
        if (detailedIds.length) {
            params["details"] = detailedIds.join(",");
        }
        const url = `/api/histories/${historyId}/contents`;
        lastRequestDate = new Date();
        const payload = await urlData({ url, params });
        // show warning that not all changes have been obtained
        if (payload && payload.length == limit) {
            console.debug(`Reached limit of monitored changes (limit=${limit}).`);
        }
        // pass changed items to attached stores
        historyStore.setHistory(history);
        store.commit("saveDatasets", { payload });
        historyItemsStore.saveHistoryItems(historyId, payload);
        store.commit("saveCollectionObjects", { payload });
        // trigger changes in legacy handler
        const Galaxy = getGalaxyInstance();
        if (Galaxy) {
            Galaxy.user.fetch({
                url: `${Galaxy.user.urlRoot()}/${Galaxy.user.id || "current"}`,
            });
        }
    }
}

export async function watchHistory(store = defaultStore) {
    const historyItemsStore = useHistoryItemsStore();
    // Only set up visibility listeners once, whenever a watch is first started
    if (watchingVisibility === false) {
        watchingVisibility = true;
        historyItemsStore.setWatchingVisibility(watchingVisibility);
        document.addEventListener("visibilitychange", setVisibilityThrottle);
    }
    try {
        await watchHistoryOnce(store);
    } catch (error) {
        // error alerting the user that watch history failed
        console.warn(error);
        watchingVisibility = false;
        historyItemsStore.setWatchingVisibility(watchingVisibility);
    } finally {
        watchTimeout = setTimeout(() => {
            watchHistory(store);
        }, throttlePeriod);
    }
}

export function rewatchHistory() {
    if (watchTimeout) {
        clearTimeout(watchTimeout);
        watchHistory();
    }
}

/**
 * Returns the set of history item IDs that are currently expanded in the history panel from the cache.
 * These content items need to retrieve detailed information when updated.
 * @returns {Array<string>} List of history item IDs that are currently expanded.
 */
function getCurrentlyExpandedHistoryContentIds() {
    const expandedItemIds = [];
    const cacheKey = "expanded-history-items";
    const expandedItems = loadSet(cacheKey);
    expandedItems.forEach((key) => {
        // Items have the format: <type>-<id>
        const itemId = key.split("-")[1];
        if (itemId?.trim()) {
            expandedItemIds.push(itemId);
        }
    });
    return expandedItemIds;
}
