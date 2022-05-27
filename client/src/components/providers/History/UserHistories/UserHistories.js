/**
 * Given that almost everything in here simply passes through to Vuex, an argument can be made for
 * not even having this provider, but I'm making anyway because:
 *
 * (1) Vuex requires a component to kick off initializations through a lifecycle event handler. Vuex
 *     lacks the ability to lazy-load data because you can't do an async watch internally, thus that
 *     kind of behavior needs to be managed by a component (which has lifecyle)
 * (2) We should separate history list management from the rendering UI elements, just as a matter of
 *     good code design.
 * (2) Having this space gives us a place to house additional update logic if we start caching
 *     history objects in IndexDB or reading updates from a websocket. Even if we continue to store
 *     data in Vuex, we will need a place to subscribe and unsubscribe from sockets/observables
 */

import { mapActions, mapGetters } from "vuex";
import { History } from "components/History/model/History";

export default {
    props: {
        user: { type: Object, required: true },
    },
    computed: {
        ...mapGetters("betaHistory", ["currentHistoryId", "currentHistory", "histories"]),

        currentHistoryModel() {
            if (this.currentHistory !== null) {
                return new History(this.currentHistory);
            }
            return null;
        },
        historyModels() {
            return this.histories.map((h) => new History(h));
        },
    },
    methods: {
        ...mapActions("betaHistory", [
            "loadHistoryById",
            "createNewHistory",
            "updateHistory",
            "deleteHistory",
            "setCurrentHistoryId",
            "setHistory",
            "loadUserHistories",
            "secureHistory",
        ]),

        updateCurrentHistory(updates) {
            this.updateHistory({ ...updates, id: this.currentHistory.id });
        },
    },
    watch: {
        // when user changes reload histories
        user: {
            immediate: true,
            handler() {
                this.loadUserHistories();
            },
        },

        // refresh history when the current id changes
        currentHistoryId(newId) {
            this.loadHistoryById(newId);
        },
    },
    render() {
        return this.$scopedSlots.default({
            // list of available histories
            histories: this.historyModels,

            // currently selected history object, should be a full object not just a summary
            currentHistory: this.currentHistoryModel,
            currentHistoryId: this.currentHistoryId,

            handlers: {
                // Updates the history in the store without a trip to the server, in the event that a
                // downstream component does the ajax update itself.
                setHistory: this.setHistory,

                // select new history, basically just needs the id
                setCurrentHistory: (h) => this.setCurrentHistoryId(h.id),

                // create new history then select it
                createNewHistory: this.createNewHistory,

                // save new history params should be an object with an id property and any additional
                // properties that are to be updated on the server. A full history object is not required
                updateHistory: this.updateHistory,
                updateCurrentHistory: this.updateCurrentHistory,

                // also conform to .sync event name format
                "update:history": this.updateHistory,
                "update:currentHistory": this.updateCurrentHistory,

                // delete history then clear currentHistoryId
                deleteHistory: (history) => this.deleteHistory({ history }),
                deleteCurrentHistory: () => this.deleteHistory({ history: this.currentHistory }),

                // purge history then clearn currentHistoryId
                purgeHistory: (history) => this.deleteHistory({ history, purge: true }),
                purgeCurrentHistory: () => this.deleteHistory({ history: this.currentHistory, purge: true }),

                secureHistory: this.secureHistory,
            },
        });
    },
};
