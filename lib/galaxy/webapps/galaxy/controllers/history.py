import logging

from dateutil.parser import isoparse
from markupsafe import escape
from sqlalchemy import (
    false,
    true,
)
from sqlalchemy.orm import undefer

from galaxy import (
    exceptions,
    model,
    web,
)
from galaxy.managers import histories
from galaxy.managers.sharable import SlugBuilder
from galaxy.model.base import transaction
from galaxy.model.item_attrs import (
    UsesAnnotations,
    UsesItemRatings,
)
from galaxy.structured_app import StructuredApp
from galaxy.util import (
    listify,
    sanitize_text,
    string_as_bool,
    unicodify,
)
from galaxy.web import (
    expose_api_anonymous,
    url_for,
)
from galaxy.web.framework.helpers import (
    grids,
    iff,
    time_ago,
)
from galaxy.webapps.base.controller import (
    BaseUIController,
    ERROR,
    INFO,
    SharableMixin,
    SUCCESS,
    WARNING,
)
from ..api import depends

log = logging.getLogger(__name__)


class NameColumn(grids.TextColumn):
    def get_value(self, trans, grid, history):
        return escape(history.get_display_name())


class HistoryListGrid(grids.Grid):
    # Custom column types
    class ItemCountColumn(grids.GridColumn):
        def get_value(self, trans, grid, history):
            return str(history.hid_counter - 1)

    class HistoryListNameColumn(NameColumn):
        def get_link(self, trans, grid, history):
            link = None
            if not history.deleted:
                link = dict(operation="Switch", id=history.id, use_panels=grid.use_panels, async_compatible=True)
            return link

    class StatusColumn(grids.GridColumn):
        def get_accepted_filters(self):
            """Returns a list of accepted filters for this column."""
            accepted_filter_labels_and_vals = {
                "active": "active",
                "deleted": "deleted",
                "archived": "archived",
                "all": "all",
            }
            accepted_filters = []
            for label, val in accepted_filter_labels_and_vals.items():
                args = {self.key: val}
                accepted_filters.append(grids.GridColumnFilter(label, args))
            return accepted_filters

        def filter(self, trans, user, query, column_filter):
            """Modify query to filter self.model_class by state."""
            if column_filter == "all":
                return query
            elif column_filter == "active":
                return query.filter(self.model_class.deleted == false(), self.model_class.archived == false())
            elif column_filter == "deleted":
                return query.filter(self.model_class.deleted == true())
            elif column_filter == "archived":
                return query.filter(self.model_class.archived == true())

        def get_value(self, trans, grid, history):
            if history == trans.history:
                return "<strong>current history</strong>"
            if history.purged:
                return "deleted permanently"
            elif history.deleted:
                return "deleted"
            elif history.archived:
                return "archived"
            return ""

        def sort(self, trans, query, ascending, column_name=None):
            if ascending:
                query = query.order_by(self.model_class.table.c.purged.asc(), self.model_class.update_time.desc())
            else:
                query = query.order_by(self.model_class.table.c.purged.desc(), self.model_class.update_time.desc())
            return query

    def build_initial_query(self, trans, **kwargs):
        # Override to preload sharing information used when fetching data for grid.
        query = super().build_initial_query(trans, **kwargs)
        query = query.options(undefer("users_shared_with_count"))
        return query

    # Grid definition
    title = "Saved Histories"
    model_class = model.History
    default_sort_key = "-update_time"
    columns = [
        HistoryListNameColumn("Name", key="name", attach_popup=True, filterable="advanced"),
        ItemCountColumn("Items", key="item_count", sortable=False),
        grids.GridColumn("Datasets", key="datasets_by_state", sortable=False, nowrap=True, delayed=True),
        grids.IndividualTagsColumn(
            "Tags",
            key="tags",
            model_tag_association_class=model.HistoryTagAssociation,
            filterable="advanced",
            grid_name="HistoryListGrid",
        ),
        grids.SharingStatusColumn(
            "Sharing", key="sharing", filterable="advanced", sortable=False, use_shared_with_count=True
        ),
        grids.GridColumn("Size on Disk", key="disk_size", sortable=False, delayed=True),
        grids.GridColumn("Created", key="create_time", format=time_ago),
        grids.GridColumn("Last Updated", key="update_time", format=time_ago),
        StatusColumn("Status", key="status", filterable="advanced"),
    ]
    columns.append(
        grids.MulticolFilterColumn(
            "search history names and tags",
            cols_to_filter=[columns[0], columns[3]],
            key="free-text-search",
            visible=False,
            filterable="standard",
        )
    )
    global_actions = [grids.GridAction("Import history", dict(controller="", action="histories/import"))]
    operations = [
        grids.GridOperation(
            "Switch", allow_multiple=False, condition=(lambda item: not item.deleted), async_compatible=True
        ),
        grids.GridOperation("View", allow_multiple=False, url_args=dict(controller="", action="histories/view")),
        grids.GridOperation(
            "Share or Publish",
            allow_multiple=False,
            condition=(lambda item: not item.deleted),
            url_args=dict(controller="", action="histories/sharing"),
        ),
        grids.GridOperation(
            "Change Permissions",
            allow_multiple=False,
            condition=(lambda item: not item.deleted),
            url_args=dict(controller="", action="histories/permissions"),
        ),
        grids.GridOperation(
            "Copy", allow_multiple=False, condition=(lambda item: not item.deleted), async_compatible=False
        ),
        grids.GridOperation(
            "Rename",
            condition=(lambda item: not item.deleted),
            url_args=dict(controller="", action="histories/rename"),
            target="top",
        ),
        grids.GridOperation("Delete", condition=(lambda item: not item.deleted), async_compatible=True),
        grids.GridOperation(
            "Delete Permanently",
            condition=(lambda item: not item.purged),
            confirm="History contents will be removed from disk, this cannot be undone.  Continue?",
            async_compatible=True,
        ),
        grids.GridOperation(
            "Undelete", condition=(lambda item: item.deleted and not item.purged), async_compatible=True
        ),
    ]
    standard_filters = [
        grids.GridColumnFilter("Active", args=dict(deleted=False)),
        grids.GridColumnFilter("Deleted", args=dict(deleted=True)),
        grids.GridColumnFilter("All", args=dict(deleted="All")),
    ]
    default_filter = dict(name="All", status="active", tags="All", sharing="All")
    num_rows_per_page = 15
    use_paging = True
    info_text = "Histories that have been deleted for more than a time period specified by the Galaxy administrator(s) may be permanently deleted."

    def get_current_item(self, trans, **kwargs):
        return trans.get_history()

    def apply_query_filter(self, trans, query, **kwargs):
        return query.filter_by(user=trans.user, importing=False)


class SharedHistoryListGrid(grids.Grid):
    # Custom column types
    class DatasetsByStateColumn(grids.GridColumn):
        def get_value(self, trans, grid, history):
            rval = ""
            for state in ("ok", "running", "queued", "error"):
                total = sum(1 for d in history.active_datasets if d.state == state)
                if total:
                    rval += f'<div class="count-box state-color-{state}">{total}</div>'
            return rval

    class SharedByColumn(grids.GridColumn):
        def get_value(self, trans, grid, history):
            return escape(history.user.email)

    # Grid definition
    title = "Histories shared with you by others"
    model_class = model.History
    default_sort_key = "-update_time"
    columns = [
        grids.GridColumn("Name", key="name", attach_popup=True),
        DatasetsByStateColumn("Datasets", sortable=False),
        grids.GridColumn("Created", key="create_time", format=time_ago),
        grids.GridColumn("Last Updated", key="update_time", format=time_ago),
        SharedByColumn("Shared by", key="user_id"),
    ]
    operations = [
        grids.GridOperation("View", allow_multiple=False, url_args=dict(controller="", action="histories/view")),
        grids.GridOperation("Copy", allow_multiple=False),
        grids.GridOperation("Unshare", allow_multiple=False),
    ]

    def build_initial_query(self, trans, **kwargs):
        return trans.sa_session.query(self.model_class).join(self.model_class.users_shared_with)

    def apply_query_filter(self, trans, query, **kwargs):
        return query.filter(model.HistoryUserShareAssociation.user == trans.user)


class HistoryController(BaseUIController, SharableMixin, UsesAnnotations, UsesItemRatings):
    history_manager: histories.HistoryManager = depends(histories.HistoryManager)
    history_serializer: histories.HistorySerializer = depends(histories.HistorySerializer)
    slug_builder: SlugBuilder = depends(SlugBuilder)

    def __init__(self, app: StructuredApp):
        super().__init__(app)

    @web.expose
    def index(self, trans):
        return ""

    @web.expose
    def list_as_xml(self, trans):
        """XML history list for functional tests"""
        trans.response.set_content_type("text/xml")
        return trans.fill_template("/history/list_as_xml.mako")

    # ......................................................................... lists
    stored_list_grid = HistoryListGrid()
    shared_list_grid = SharedHistoryListGrid()

    @web.legacy_expose_api
    @web.require_login("work with multiple histories")
    def list(self, trans, **kwargs):
        """List all available histories"""
        current_history = trans.get_history()
        message = kwargs.get("message")
        status = kwargs.get("status")
        if "operation" in kwargs:
            operation = kwargs["operation"].lower()
            history_ids = listify(kwargs.get("id", []))
            # Display no message by default
            status, message = None, None
            # Load the histories and ensure they all belong to the current user
            histories = []
            for history_id in history_ids:
                history = self.history_manager.get_owned(
                    self.decode_id(history_id), trans.user, current_history=trans.history
                )
                if history:
                    # Ensure history is owned by current user
                    if history.user_id is not None and trans.user:
                        assert trans.user.id == history.user_id, "History does not belong to current user"
                    histories.append(history)
                else:
                    log.warning("Invalid history id '%r' passed to list", history_id)
            if histories:
                if operation == "switch":
                    status, message = self._list_switch(trans, histories)
                    # Take action to update UI to reflect history switch. If
                    # grid is using panels, it is standalone and hence a redirect
                    # to root is needed; if grid is not using panels, it is nested
                    # in the main Galaxy UI and refreshing the history frame
                    # is sufficient.
                    use_panels = kwargs.get("use_panels", False) == "True"
                    if use_panels:
                        return trans.response.send_redirect(url_for("/"))
                    else:
                        kwargs["refresh_frames"] = ["history"]
                elif operation in ("delete", "delete permanently"):
                    status, message = self._list_delete(trans, histories, purge=(operation == "delete permanently"))
                    if current_history in histories:
                        # Deleted the current history, so a new, empty history was
                        # created automatically, and we need to refresh the history frame
                        kwargs["refresh_frames"] = ["history"]
                elif operation == "undelete":
                    status, message = self._list_undelete(trans, histories)

                with transaction(trans.sa_session):
                    trans.sa_session.commit()
        # Render the list view
        if message and status:
            kwargs["message"] = sanitize_text(message)
            kwargs["status"] = status
        return self.stored_list_grid(trans, **kwargs)

    def _list_delete(self, trans, histories, purge=False):
        """Delete histories"""
        n_deleted = 0
        deleted_current = False
        message_parts = []
        status = SUCCESS
        current_history = trans.get_history()
        for history in histories:
            try:
                if history.users_shared_with:
                    raise exceptions.ObjectAttributeInvalidException(
                        f"History ({history.name}) has been shared with others, unshare it before deleting it."
                    )
                if purge:
                    self.history_manager.purge(history)
                else:
                    self.history_manager.delete(history)
                if history == current_history:
                    deleted_current = True
            except Exception as e:
                message_parts.append(unicodify(e))
                status = ERROR
            else:
                trans.log_event(f"History ({history.name}) marked as deleted")
                n_deleted += 1

        if n_deleted:
            part = "Deleted %d %s" % (n_deleted, iff(n_deleted != 1, "histories", "history"))
            if purge and trans.app.config.allow_user_dataset_purge:
                part += f" and removed {iff(n_deleted != 1, 'their', 'its')} dataset{iff(n_deleted != 1, 's', '')} from disk"
            elif purge:
                part += " but the datasets were not removed from disk because that feature is not enabled in this Galaxy instance"
            message_parts.append(f"{part}.  ")
        if deleted_current:
            # if this history is the current history for this session,
            # - attempt to find the most recently used, undeleted history and switch to it.
            # - If no suitable recent history is found, create a new one and switch
            # note: this needs to come after commits above or will use an empty history that was deleted above
            not_deleted_or_purged = [model.History.deleted == false(), model.History.purged == false()]
            most_recent_history = self.history_manager.most_recent(user=trans.user, filters=not_deleted_or_purged)
            if most_recent_history:
                self.history_manager.set_current(trans, most_recent_history)
            else:
                trans.get_or_create_default_history()
            message_parts.append("Your active history was deleted, a new empty history is now active.  ")
            status = INFO
        return (status, " ".join(message_parts))

    def _list_undelete(self, trans, histories):
        """Undelete histories"""
        n_undeleted = 0
        n_already_purged = 0
        for history in histories:
            if history.purged:
                n_already_purged += 1
            if history.deleted:
                history.deleted = False
                if not history.default_permissions:
                    # For backward compatibility - for a while we were deleting all DefaultHistoryPermissions on
                    # the history when we deleted the history.  We are no longer doing this.
                    # Need to add default DefaultHistoryPermissions in case they were deleted when the history was deleted
                    default_action = trans.app.security_agent.permitted_actions.DATASET_MANAGE_PERMISSIONS
                    private_user_role = trans.app.security_agent.get_private_user_role(history.user)
                    default_permissions = {}
                    default_permissions[default_action] = [private_user_role]
                    trans.app.security_agent.history_set_default_permissions(history, default_permissions)
                n_undeleted += 1
                trans.log_event("History (%s) %d marked as undeleted" % (history.name, history.id))
        status = SUCCESS
        message_parts = []
        if n_undeleted:
            message_parts.append("Undeleted %d %s.  " % (n_undeleted, iff(n_undeleted != 1, "histories", "history")))
        if n_already_purged:
            message_parts.append("%d histories have already been purged and cannot be undeleted." % n_already_purged)
            status = WARNING
        return status, "".join(message_parts)

    def _list_switch(self, trans, histories):
        """Switch to a new different history"""
        new_history = histories[0]
        galaxy_session = trans.get_galaxy_session()
        try:
            association = (
                trans.sa_session.query(trans.app.model.GalaxySessionToHistoryAssociation)
                .filter_by(session_id=galaxy_session.id, history_id=new_history.id)
                .first()
            )
        except Exception:
            association = None
        new_history.add_galaxy_session(galaxy_session, association=association)
        trans.sa_session.add(new_history)
        with transaction(trans.sa_session):
            trans.sa_session.commit()
        trans.set_history(new_history)
        # No message
        return None, None

    @web.expose
    @web.json
    @web.require_login("work with shared histories")
    def list_shared(self, trans, **kwargs):
        """List histories shared with current user by others"""
        status = message = None
        if "operation" in kwargs:
            ids = listify(kwargs.get("id", []))
            operation = kwargs["operation"].lower()
            if operation == "unshare":
                if not ids:
                    message = "Select a history to unshare"
                    status = "error"
                for id in ids:
                    # No need to check security, association below won't yield a
                    # hit if this user isn't having the history shared with her.
                    history = self.history_manager.by_id(self.decode_id(id))
                    # Current user is the user with which the histories were shared
                    association = (
                        trans.sa_session.query(trans.app.model.HistoryUserShareAssociation)
                        .filter_by(user=trans.user, history=history)
                        .one()
                    )
                    trans.sa_session.delete(association)
                    with transaction(trans.sa_session):
                        trans.sa_session.commit()
                message = "Unshared %d shared histories" % len(ids)
                status = "done"
        # Render the list view
        return self.shared_list_grid(trans, status=status, message=message, **kwargs)

    @web.expose
    def as_xml(self, trans, id=None, show_deleted=None, show_hidden=None):
        """
        Return a history in xml format.
        """
        if trans.app.config.require_login and not trans.user:
            return trans.fill_template("/no_access.mako", message="Please log in to access Galaxy histories.")

        if id:
            history = self.history_manager.get_accessible(self.decode_id(id), trans.user, current_history=trans.history)
        else:
            history = trans.get_history(most_recent=True, create=True)

        trans.response.set_content_type("text/xml")
        return trans.fill_template_mako(
            "history/as_xml.mako",
            history=history,
            show_deleted=string_as_bool(show_deleted),
            show_hidden=string_as_bool(show_hidden),
        )

    @expose_api_anonymous
    def view(self, trans, id=None, show_deleted=False, show_hidden=False, use_panels=True):
        """
        View a history. If a history is importable, then it is viewable by any user.
        """
        show_deleted = string_as_bool(show_deleted)
        show_hidden = string_as_bool(show_hidden)
        use_panels = string_as_bool(use_panels)

        history_dictionary = {}
        user_is_owner = False
        if id:
            history_to_view = self.history_manager.get_accessible(
                self.decode_id(id), trans.user, current_history=trans.history
            )
            user_is_owner = history_to_view.user == trans.user
            history_is_current = history_to_view == trans.history
        else:
            history_to_view = trans.history
            user_is_owner = True
            history_is_current = True

        # include all datasets: hidden, deleted, and purged
        history_dictionary = self.history_serializer.serialize_to_view(
            history_to_view, view="dev-detailed", user=trans.user, trans=trans
        )

        return {
            "history": history_dictionary,
            "user_is_owner": user_is_owner,
            "history_is_current": history_is_current,
            "show_deleted": show_deleted,
            "show_hidden": show_hidden,
            "use_panels": use_panels,
            "allow_user_dataset_purge": trans.app.config.allow_user_dataset_purge,
        }

    @web.expose
    def display_by_username_and_slug(self, trans, username, slug, **kwargs):
        """
        Display history based on a username and slug.
        """
        # Get history.
        session = trans.sa_session
        user = session.query(model.User).filter_by(username=username).first()
        history = trans.sa_session.query(model.History).filter_by(user=user, slug=slug, deleted=False).first()
        if history is None:
            raise web.httpexceptions.HTTPNotFound()

        # Security check raises error if user cannot access history.
        self.history_manager.error_unless_accessible(history, trans.user, current_history=trans.history)

        # Encode history id.
        history_id = trans.security.encode_id(history.id)

        # Redirect to client.
        return trans.response.send_redirect(
            web.url_for(
                controller="published",
                action="history",
                id=history_id,
            )
        )

    @web.legacy_expose_api
    @web.require_login("changing default permissions")
    def permissions(self, trans, payload=None, **kwd):
        """
        Sets the permissions on a history.
        """
        history_id = kwd.get("id")
        if not history_id:
            return self.message_exception(trans, f"Invalid history id ({str(history_id)}) received")
        history = self.history_manager.get_owned(self.decode_id(history_id), trans.user, current_history=trans.history)
        if trans.request.method == "GET":
            inputs = []
            all_roles = trans.user.all_roles()
            current_actions = history.default_permissions
            for action_key, action in trans.app.model.Dataset.permitted_actions.items():
                in_roles = set()
                for a in current_actions:
                    if a.action == action.action:
                        in_roles.add(a.role)
                inputs.append(
                    {
                        "type": "select",
                        "multiple": True,
                        "optional": True,
                        "individual": True,
                        "name": action_key,
                        "label": action.action,
                        "help": action.description,
                        "options": [(role.name, trans.security.encode_id(role.id)) for role in set(all_roles)],
                        "value": [trans.security.encode_id(role.id) for role in in_roles],
                    }
                )
            return {"title": "Change default dataset permissions for history '%s'" % history.name, "inputs": inputs}
        else:
            self.history_manager.error_unless_mutable(history)
            permissions = {}
            for action_key, action in trans.app.model.Dataset.permitted_actions.items():
                in_roles = payload.get(action_key) or []
                in_roles = [
                    trans.sa_session.query(trans.app.model.Role).get(trans.security.decode_id(x)) for x in in_roles
                ]
                permissions[trans.app.security_agent.get_action(action.action)] = in_roles
            trans.app.security_agent.history_set_default_permissions(history, permissions)
            return {"message": "Default history '%s' dataset permissions have been changed." % history.name}

    @web.legacy_expose_api
    @web.require_login("make datasets private")
    def make_private(self, trans, history_id=None, all_histories=False, **kwd):
        """
        Sets the datasets within a history to private.  Also sets the default
        permissions for the history to private, for future datasets.
        """
        histories = []
        all_histories = string_as_bool(all_histories)
        if all_histories:
            histories = trans.user.histories
        elif history_id:
            history = self.history_manager.get_owned(
                self.decode_id(history_id), trans.user, current_history=trans.history
            )
            if history:
                histories.append(history)
        if not histories:
            return self.message_exception(trans, "Invalid history or histories specified.")
        private_role = trans.app.security_agent.get_private_user_role(trans.user)
        user_roles = trans.user.all_roles()
        private_permissions = {
            trans.app.security_agent.permitted_actions.DATASET_MANAGE_PERMISSIONS: [private_role],
            trans.app.security_agent.permitted_actions.DATASET_ACCESS: [private_role],
        }
        for history in histories:
            self.history_manager.error_unless_mutable(history)
            # Set default role for history to private
            trans.app.security_agent.history_set_default_permissions(history, private_permissions)
            # Set private role for all datasets
            for hda in history.datasets:
                if (
                    not hda.dataset.library_associations
                    and not trans.app.security_agent.dataset_is_private_to_user(trans, hda.dataset)
                    and trans.app.security_agent.can_manage_dataset(user_roles, hda.dataset)
                ):
                    # If it's not private to me, and I can manage it, set fixed private permissions.
                    trans.app.security_agent.set_all_dataset_permissions(hda.dataset, private_permissions)
                    if not trans.app.security_agent.dataset_is_private_to_user(trans, hda.dataset):
                        raise exceptions.InternalServerError("An error occurred and the dataset is NOT private.")
        return {
            "message": f"Success, requested permissions have been changed in {'all histories' if all_histories else history.name}."
        }

    @web.expose
    def adjust_hidden(self, trans, id=None, **kwd):
        """THIS METHOD IS A TEMPORARY ADDITION. It'll allow us to fix the
        regression in history-wide actions, and will be removed in the first
        release after 17.01"""
        action = kwd.get("user_action", None)
        if action == "delete":
            for hda in trans.history.datasets:
                if not hda.visible:
                    hda.mark_deleted()
        elif action == "unhide":
            trans.history.unhide_datasets()
        with transaction(trans.sa_session):
            trans.sa_session.commit()

    # ......................................................................... actions/orig. async

    @web.expose
    def purge_deleted_datasets(self, trans):
        count = 0
        if trans.app.config.allow_user_dataset_purge and trans.history:
            for hda in trans.history.datasets:
                if not hda.deleted or hda.purged:
                    continue
                hda.purge_usage_from_quota(trans.user, hda.dataset.quota_source_info)
                hda.purged = True
                trans.sa_session.add(hda)
                trans.log_event(f"HDA id {hda.id} has been purged")
                with transaction(trans.sa_session):
                    trans.sa_session.commit()
                if hda.dataset.user_can_purge:
                    try:
                        hda.dataset.full_delete()
                        trans.log_event(
                            f"Dataset id {hda.dataset.id} has been purged upon the the purge of HDA id {hda.id}"
                        )
                        trans.sa_session.add(hda.dataset)
                    except Exception:
                        log.exception(f"Unable to purge dataset ({hda.dataset.id}) on purge of hda ({hda.id}):")
                count += 1
            return trans.show_ok_message(
                "%d datasets have been deleted permanently" % count, refresh_frames=["history"]
            )
        return trans.show_error_message("Cannot purge deleted datasets from this session.")

    @web.expose
    def resume_paused_jobs(self, trans, current=False, ids=None, **kwargs):
        """Resume paused jobs the active history -- this does not require a logged in user."""
        if not ids and string_as_bool(current):
            histories = [trans.get_history()]
            refresh_frames = ["history"]
        else:
            raise NotImplementedError("You can currently only resume all the datasets of the current history.")
        for history in histories:
            history.resume_paused_jobs()
            trans.sa_session.add(history)
        with transaction(trans.sa_session):
            trans.sa_session.commit()
        return trans.show_ok_message("Your jobs have been resumed.", refresh_frames=refresh_frames)
        # TODO: used in index.mako

    @web.legacy_expose_api
    @web.require_login("rename histories")
    def rename(self, trans, payload=None, **kwd):
        id = kwd.get("id")
        if not id:
            return self.message_exception(trans, "No history id received for renaming.")
        user = trans.get_user()
        id = listify(id)
        histories = []
        for history_id in id:
            history = self.history_manager.get_mutable(
                self.decode_id(history_id), trans.user, current_history=trans.history
            )
            if history and history.user_id == user.id:
                histories.append(history)
        if trans.request.method == "GET":
            return {
                "title": "Change history name(s)",
                "inputs": [
                    {"name": "name_%i" % i, "label": f"Current: {h.name}", "value": h.name}
                    for i, h in enumerate(histories)
                ],
            }
        else:
            messages = []
            for i, h in enumerate(histories):
                cur_name = h.get_display_name()
                new_name = payload.get("name_%i" % i)
                # validate name is empty
                if not isinstance(new_name, str) or not new_name.strip():
                    messages.append("You must specify a valid name for History '%s'." % cur_name)
                # skip if not the owner
                elif h.user_id != user.id:
                    messages.append("History '%s' does not appear to belong to you." % cur_name)
                # skip if it wouldn't be a change
                elif new_name != cur_name:
                    h.name = new_name
                    trans.sa_session.add(h)
                    with transaction(trans.sa_session):
                        trans.sa_session.commit()
                    trans.log_event(f"History renamed: id: {str(h.id)}, renamed to: {new_name}")
                    messages.append(f"History '{cur_name}' renamed to '{new_name}'.")
            message = sanitize_text(" ".join(messages)) if messages else "History names remain unchanged."
            return {"message": message, "status": "success"}

    # ------------------------------------------------------------------------- current history
    @web.expose
    @web.require_login("switch to a history")
    def switch_to_history(self, trans, hist_id=None, **kwargs):
        """Change the current user's current history to one with `hist_id`."""
        # remains for backwards compat
        self.set_as_current(trans, id=hist_id)
        return trans.response.send_redirect(url_for("/"))

    def get_item(self, trans, id):
        return self.history_manager.get_owned(self.decode_id(id), trans.user, current_history=trans.history)
        # TODO: override of base ui controller?

    def history_data(self, trans, history):
        """Return the given history in a serialized, dictionary form."""
        return self.history_serializer.serialize_to_view(history, view="dev-detailed", user=trans.user, trans=trans)

    # TODO: combine these next two - poss. with a redirect flag
    # @web.require_login( "switch to a history" )
    @web.json
    @web.do_not_cache
    def set_as_current(self, trans, id, **kwargs):
        """Change the current user's current history to one with `id`."""
        try:
            history = self.history_manager.get_mutable(self.decode_id(id), trans.user, current_history=trans.history)
            trans.set_history(history)
            return self.history_data(trans, history)
        except exceptions.MessageException as msg_exc:
            trans.response.status = msg_exc.status_code
            return {"err_msg": msg_exc.err_msg, "err_code": msg_exc.err_code.code}

    @web.json
    @web.do_not_cache
    def current_history_json(self, trans, since=None, **kwargs):
        """Return the current user's current history in a serialized, dictionary form."""
        history = trans.get_history(most_recent=True, create=True)
        if since and history.update_time <= isoparse(since):
            # Should ideally be a 204 response, but would require changing web.json
            # This endpoint should either give way to a proper API or a SSE loop
            return
        return self.history_data(trans, history)

    @web.json
    def create_new_current(self, trans, name=None, **kwargs):
        """Create a new, current history for the current user"""
        new_history = trans.new_history(name)
        return self.history_data(trans, new_history)

    # TODO: /history/current to do all of the above: if ajax, return json; if post, read id and set to current
