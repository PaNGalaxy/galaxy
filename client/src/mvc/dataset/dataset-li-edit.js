import _ from "underscore";
import $ from "jquery";
import { getAppRoot } from "onload/loadConfig";
import { getGalaxyInstance } from "app";
import STATES from "mvc/dataset/states";
import DATASET_LI from "mvc/dataset/dataset-li";
import { mountModelTags } from "components/Tags";
import ANNOTATIONS from "mvc/annotation";
import faIconButton from "ui/fa-icon-button";
import BASE_MVC from "mvc/base-mvc";
import _l from "utils/localization";

//==============================================================================
var _super = DATASET_LI.DatasetListItemView;
/** @class Editing view for DatasetAssociation.
 */
var DatasetListItemEdit = _super.extend(
    /** @lends DatasetListItemEdit.prototype */ {
        /** set up: options */
        initialize: function (attributes) {
            _super.prototype.initialize.call(this, attributes);
            this.hasUser = attributes.hasUser;

            /** allow user purge of dataset files? */
            this.purgeAllowed = attributes.purgeAllowed || false;

            //TODO: move to HiddenUntilActivatedViewMixin
            /** should the tags editor be shown or hidden initially? */
            this.tagsEditorShown = attributes.tagsEditorShown || false;
            /** should the tags editor be shown or hidden initially? */
            this.annotationEditorShown = attributes.annotationEditorShown || false;
        },

        // ......................................................................... titlebar actions
        /** In this override, add the other two primary actions: edit and delete */
        _renderPrimaryActions: function () {
            var actions = _super.prototype._renderPrimaryActions.call(this);
            if (this.model.get("state") === STATES.NOT_VIEWABLE) {
                return actions;
            }
            // render the display, edit attr and delete icon-buttons
            return _super.prototype._renderPrimaryActions
                .call(this)
                .concat([this._renderEditButton(), this._renderDeleteButton()]);
        },

        //TODO: move titleButtons into state renderers, remove state checks in the buttons

        /** Render icon-button to edit the attributes (format, permissions, etc.) this dataset. */
        _renderEditButton: function () {
            var self = this;
            // don't show edit while uploading, in-accessible
            // DO show if in error (ala previous history panel)
            if (this.model.get("state") === STATES.DISCARDED || !this.model.get("accessible")) {
                return null;
            }
            var purged = this.model.get("purged");
            var deleted = this.model.get("deleted");

            var editBtnData = {
                title: _l("Edit attributes"),
                href: `${getAppRoot()}datasets/edit?dataset_id=${this.model.get("element_id") || this.model.get("id")}`,
                faIcon: "fa-pencil",
                classes: "edit-btn",
                onclick: function (ev) {
                    if (!deleted && !purged) {
                        const Galaxy = getGalaxyInstance();
                        if (Galaxy.router) {
                            ev.preventDefault();
                            const identifier = self.model.get("element_id") || self.model.get("id");
                            Galaxy.router.push("datasets/edit", {
                                dataset_id: identifier,
                            });
                        }
                    }
                },
            };

            // disable if purged or deleted and explain why in the tooltip
            if (deleted || purged) {
                editBtnData.disabled = true;
                if (purged) {
                    editBtnData.title = _l("Cannot edit attributes of datasets removed from disk");
                } else if (deleted) {
                    editBtnData.title = _l("Undelete dataset to edit attributes");
                }

                // disable if still uploading or new
            } else if ([STATES.UPLOAD, STATES.NEW].includes(this.model.get("state"))) {
                editBtnData.disabled = true;
                editBtnData.title = _l("This dataset is not yet editable");
            }
            return faIconButton(editBtnData);
        },

        /** Render icon-button to delete this hda. */
        _renderDeleteButton: function () {
            // don't show delete if...
            if (!this.model.get("accessible")) {
                return null;
            }

            var self = this;
            var deletedAlready = this.model.isDeletedOrPurged();
            return faIconButton({
                title: !deletedAlready ? _l("Delete") : _l("Dataset is already deleted"),
                disabled: deletedAlready,
                faIcon: "fa-times",
                classes: "delete-btn",
                onclick: function () {
                    self.$el.find(".icon-btn.delete-btn").tooltip("dispose");
                    self.model["delete"]();
                },
            });
        },

        // ......................................................................... details
        /** In this override, add tags and annotations controls, make the ? dbkey a link to editing page */
        _renderDetails: function () {
            //TODO: generalize to be allow different details for each state
            var $details = _super.prototype._renderDetails.call(this);

            var state = this.model.get("state");

            if (!this.model.isDeletedOrPurged()) {
                //Enable tagging+annotation regardless of job state (see issue #6330)
                this._renderTags($details);
                this._renderAnnotation($details);
                if ([STATES.OK, STATES.FAILED_METADATA].includes(state)) {
                    this._makeDbkeyEditLink($details);
                }
            }

            this._setUpBehaviors($details);
            return $details;
        },

        /**************************************************************************
         * Render help button to show tool help text without rerunning the tool.
         * Issue #2100
         */
        _renderToolHelpButton: function () {
            var datasetID = this.model.attributes.dataset_id;
            var jobID = this.model.attributes.creating_job;
            var self = this;

            var parseToolBuild = (data) => {
                var helpString = `<div id="thdiv-${datasetID}" class="toolhelp">`;
                if (data.name && data.help) {
                    helpString += `<strong>Tool help for ${data.name}</strong><hr/>`;
                    helpString += data.help;
                } else {
                    helpString += "<strong>Tool help is unavailable for this dataset.</strong><hr/>";
                }
                helpString += "</div>";
                self.$el.find(".details").append($.parseHTML(helpString));
            };
            var parseToolID = (data) => {
                $.ajax({
                    url: `${getAppRoot()}api/tools/${data.tool_id}/build`,
                })
                    .done((data) => {
                        parseToolBuild(data);
                    })
                    .fail(() => {
                        parseToolBuild({});
                    });
            };

            const Galaxy = getGalaxyInstance();
            if (Galaxy.user.id === null) {
                return null;
            }

            return faIconButton({
                title: _l("Tool Help"),
                classes: "icon-btn",
                href: "#",
                faIcon: "fa-question",
                onclick: function (ev) {
                    ev.preventDefault();
                    if (self.$el.find(".toolhelp").length > 0) {
                        self.$el.find(".toolhelp").toggle();
                    } else {
                        $.ajax({
                            url: `${getAppRoot()}api/jobs/${jobID}`,
                        })
                            .done((data) => {
                                parseToolID(data);
                            })
                            .fail(() => {
                                console.log(
                                    `Failed at recovering job information from the  Galaxy API for job id "${jobID}".`
                                );
                            });
                    }
                },
            });
        },
        //*************************************************************************

        /** Add less commonly used actions in the details section based on state */
        _renderSecondaryActions: function () {
            var actions = _super.prototype._renderSecondaryActions.call(this);
            switch (this.model.get("state")) {
                case STATES.UPLOAD:
                case STATES.NOT_VIEWABLE:
                    return actions;
                case STATES.ERROR:
                    // error button comes first
                    actions.unshift(this._renderErrButton());
                    return actions.concat([this._renderRerunButton(), this._renderToolHelpButton()]);
                case STATES.OK:
                case STATES.FAILED_METADATA:
                    return actions.concat([
                        this._renderRerunButton(),
                        this._renderVisualizationsButton(),
                        this._renderToolHelpButton(),
                    ]);
            }
            return actions.concat([this._renderRerunButton(), this._renderToolHelpButton()]);
        },

        /** Render icon-button to report an error on this dataset to the galaxy admin. */
        _renderErrButton: function () {
            var self = this;
            return faIconButton({
                title: _l("View or report this error"),
                href: `${getAppRoot()}datasets/error?dataset_id=${
                    self.model.get("element_id") || self.model.get("id")
                }`,
                classes: "report-error-btn",
                faIcon: "fa-bug",
                onclick: function (ev) {
                    const Galaxy = getGalaxyInstance();
                    if (Galaxy.router) {
                        ev.preventDefault();
                        Galaxy.router.push("datasets/error", {
                            dataset_id: self.model.get("element_id") || self.model.get("id"),
                        });
                    }
                },
            });
        },

        /** Render icon-button to re-run the job that created this dataset. */
        _renderRerunButton: function () {
            var creating_job = this.model.get("creating_job");
            if (this.model.get("rerunnable")) {
                return faIconButton({
                    title: _l("Run this job again"),
                    href: this.model.urls.rerun,
                    classes: "rerun-btn",
                    target: this.linkTarget,
                    faIcon: "fa-redo",
                    onclick: function (ev) {
                        const Galaxy = getGalaxyInstance();
                        if (Galaxy.router) {
                            ev.preventDefault();
                            Galaxy.router.push("/", {
                                job_id: creating_job,
                            });
                        }
                    },
                });
            }
        },

        /** Render an icon-button or popupmenu of links based on the applicable visualizations */
        _renderVisualizationsButton: function () {
            //TODO: someday - lazyload visualizations
            const Galaxy = getGalaxyInstance();
            const visualizations = this.model.get("visualizations");
            if (
                !Galaxy.config.visualizations_visible ||
                this.model.isDeletedOrPurged() ||
                !this.hasUser ||
                !this.model.hasData() ||
                _.isEmpty(visualizations)
            ) {
                return null;
            }
            if (!_.isObject(visualizations[0])) {
                this.warn("Visualizations have been switched off");
                return null;
            }
            if (visualizations.length >= 1) {
                const dsid = this.model.get("element_id") || this.model.get("id");
                const url = getAppRoot() + "visualizations?dataset_id=" + dsid;
                return faIconButton({
                    title: _l("Visualize this data"),
                    href: url,
                    classes: "visualization-link",
                    faIcon: "fa-bar-chart-o",
                    onclick: (ev) => {
                        if (Galaxy.frame && Galaxy.frame.active) {
                            ev.preventDefault();
                            Galaxy.frame.add({ url: url, title: "Visualization" });
                        } else if (Galaxy.router) {
                            ev.preventDefault();
                            Galaxy.router.push("visualizations", {
                                dataset_id: dsid,
                            });
                            Galaxy.trigger("activate-hda", dsid);
                        }
                    },
                });
            }
        },

        /** Render the tags list/control */
        _renderTags: function ($where) {
            if (!this.hasUser) {
                return;
            }

            const el = $where.find(".tags-display")[0];

            const propsData = {
                model: this.model,
                disabled: false,
                context: "dataset-li-edit",
            };

            const vm = mountModelTags(propsData, el);

            // tag icon button open/closes
            const activator = faIconButton({
                title: _l("Edit dataset tags"),
                classes: "tag-btn",
                faIcon: "fa-tags",
            }).appendTo($where.find(".actions .right"));

            const toggleEditor = () => {
                $(vm.$el).toggleClass("active");
                this.tagsEditorShown = $(vm.$el).hasClass("active");
            };

            activator.on("click", toggleEditor);

            if (this.tagsEditorShown) {
                const editorIsOpen = $(vm.$el).hasClass("active");
                if (!editorIsOpen) {
                    toggleEditor();
                }
            }

            return vm;
        },

        /** Render the annotation display/control */
        _renderAnnotation: function ($where) {
            if (!this.hasUser) {
                return;
            }
            var view = this;
            this.annotationEditor = new ANNOTATIONS.AnnotationEditor({
                model: this.model,
                el: $where.find(".annotation-display"),
                onshowFirstTime: function () {
                    this.render();
                },
                // persist state on the hda view (and not the editor) since these are currently re-created each time
                onshow: function () {
                    view.annotationEditorShown = true;
                },
                onhide: function () {
                    view.annotationEditorShown = false;
                },
                $activator: faIconButton({
                    title: _l("Edit dataset annotation"),
                    classes: "annotate-btn",
                    faIcon: "fa-comment",
                }).appendTo($where.find(".actions .right")),
            });
            if (this.annotationEditorShown) {
                this.annotationEditor.toggle(true);
            }
        },

        /** If the format/dbkey/genome_build isn't set, make the display a link to the edit page */
        _makeDbkeyEditLink: function ($details) {
            // make the dbkey a link to editing
            if (this.model.get("metadata_dbkey") === "?" && !this.model.isDeletedOrPurged()) {
                var editableDbkey = $('<a class="value">?</a>')
                    .attr("href", this.model.urls.edit)
                    .attr("target", "_top");
                $details.find(".dbkey .value").replaceWith(editableDbkey);
            }
        },

        // ......................................................................... events
        /** event map */
        events: _.extend(_.clone(_super.prototype.events), {
            "click .undelete-link": "_clickUndeleteLink",
            "click .purge-link": "_clickPurgeLink",

            "click .edit-btn": function (ev) {
                this.trigger("edit", this, ev);
            },
            "click .delete-btn": function (ev) {
                this.trigger("delete", this, ev);
            },
            "click .rerun-btn": function (ev) {
                this.trigger("rerun", this, ev);
            },
            "click .report-err-btn": function (ev) {
                this.trigger("report-err", this, ev);
            },
            "click .visualization-btn": function (ev) {
                this.trigger("visualize", this, ev);
            },
            "click .dbkey a": function (ev) {
                this.trigger("edit", this, ev);
            },
        }),

        /** listener for item undelete (in the messages section) */
        _clickUndeleteLink: function (ev) {
            this.model.undelete();
            return false;
        },

        /** listener for item purge (in the messages section) */
        _clickPurgeLink: function (ev) {
            if (window.confirm(_l("This will permanently remove the data in your dataset. Are you sure?"))) {
                this.model.purge();
            }
            return false;
        },

        // ......................................................................... misc
        /** string rep */
        toString: function () {
            var modelString = this.model ? `${this.model}` : "(no model)";
            return `HDAEditView(${modelString})`;
        },
    }
);

// ............................................................................ TEMPLATES
/** underscore templates */
DatasetListItemEdit.prototype.templates = (() => {
    var warnings = _.extend({}, _super.prototype.templates.warnings, {
        failed_metadata: BASE_MVC.wrapTemplate(
            [
                // in this override, provide a link to the edit page
                '<% if( dataset.state === "failed_metadata" ){ %>',
                '<div class="failed_metadata-warning warningmessagesmall">',
                _l("An error occurred setting the metadata for this dataset"),
                '<br /><a href="<%- dataset.urls.edit %>" target="_top">',
                _l("Set it manually or retry auto-detection"),
                "</a>",
                "</div>",
                "<% } %>",
            ],
            "dataset"
        ),

        deleted: BASE_MVC.wrapTemplate(
            [
                // in this override, provide links to undelete or purge the dataset
                "<% if( dataset.deleted && !dataset.purged ){ %>",
                // deleted not purged
                '<div class="deleted-msg warningmessagesmall">',
                _l("This dataset has been deleted"),
                '<br /><a class="undelete-link" href="javascript:void(0);">',
                _l("Undelete it"),
                "</a>",
                "<% if( view.purgeAllowed ){ %>",
                '<br /><a class="purge-link" href="javascript:void(0);">',
                _l("Permanently remove it from disk"),
                "</a>",
                "<% } %>",
                "</div>",
                "<% } %>",
            ],
            "dataset"
        ),
    });
    return _.extend({}, _super.prototype.templates, {
        warnings: warnings,
    });
})();

//==============================================================================
export default {
    DatasetListItemEdit: DatasetListItemEdit,
};
