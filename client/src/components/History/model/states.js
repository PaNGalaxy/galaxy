// Stolen from existing model.

export const STATES = {
    /** is uploading and not ready */
    UPLOAD: "upload",
    /** the job that will produce the dataset queued in the runner */
    QUEUED: "queued",
    /** the job that will produce the dataset is running */
    RUNNING: "running",
    /** metadata for the dataset is being discovered/set */
    SETTING_METADATA: "setting_metadata",
    /** was created without a tool */
    NEW: "new",
    /** job is being created, but not put into job queue yet */
    WAITING: "waiting",
    /** has no data */
    EMPTY: "empty",
    /** has successfully completed running */
    OK: "ok",
    /** the job that will produce the dataset paused */
    PAUSED: "paused",
    /** metadata discovery/setting failed or errored (but otherwise ok) */
    FAILED_METADATA: "failed_metadata",

    //TODO: not in trans.app.model.Dataset.states - is in database
    /** not accessible to the current user (i.e. due to permissions) */
    NOT_VIEWABLE: "noPermission",
    /** deleted while uploading */
    DISCARDED: "discarded",
    /** the tool producing this dataset failed */
    ERROR: "error",

    // found in job-state summary model?
    // this an actual state value or something derived from deleted prop?
    DELETED: "deleted",

    LOADING: "loading",
};

export const NOT_READY_STATES = [STATES.UPLOAD, STATES.QUEUED, STATES.RUNNING, STATES.SETTING_METADATA, STATES.NEW];
