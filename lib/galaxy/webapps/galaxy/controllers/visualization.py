import logging
from json import loads

from markupsafe import escape
from paste.httpexceptions import (
    HTTPBadRequest,
    HTTPNotFound,
)
from sqlalchemy import (
    desc,
    false,
    or_,
    text,
    true,
)
from sqlalchemy.orm import (
    joinedload,
    undefer,
)

from galaxy import (
    model,
    util,
    web,
)
from galaxy.managers.hdas import HDAManager
from galaxy.managers.sharable import SlugBuilder
from galaxy.model.base import transaction
from galaxy.model.item_attrs import (
    UsesAnnotations,
    UsesItemRatings,
)
from galaxy.structured_app import StructuredApp
from galaxy.util import (
    sanitize_text,
    unicodify,
)
from galaxy.util.sanitize_html import sanitize_html
from galaxy.visualization.data_providers.phyloviz import PhylovizDataProvider
from galaxy.visualization.genomes import (
    decode_dbkey,
    GenomeRegion,
)
from galaxy.visualization.plugins import registry
from galaxy.web.framework.helpers import (
    grids,
    time_ago,
)
from galaxy.webapps.base.controller import (
    BaseUIController,
    SharableMixin,
    UsesVisualizationMixin,
)
from ..api import depends

log = logging.getLogger(__name__)


#
# -- Grids --
#
class HistoryDatasetsSelectionGrid(grids.Grid):
    class DbKeyColumn(grids.GridColumn):
        def filter(self, trans, user, query, dbkey):
            """Filter by dbkey through a raw SQL b/c metadata is a BLOB."""
            dbkey_user, dbkey = decode_dbkey(dbkey)
            dbkey = dbkey.replace("'", "\\'")
            return query.filter(
                or_(text(f'metadata like \'%"dbkey": ["{dbkey}"]%\'', f'metadata like \'%"dbkey": "{dbkey}"%\''))
            )

    class HistoryColumn(grids.GridColumn):
        def get_value(self, trans, grid, hda):
            return escape(hda.history.name)

        def sort(self, trans, query, ascending, column_name=None):
            """Sort query using this column."""
            return grids.GridColumn.sort(self, trans, query, ascending, column_name="history_id")

    available_tracks = None
    title = "Add Datasets"
    model_class = model.HistoryDatasetAssociation
    default_filter = {"deleted": "False", "shared": "All"}
    default_sort_key = "-hid"
    columns = [
        grids.GridColumn("Id", key="hid"),
        grids.TextColumn("Name", key="name", model_class=model.HistoryDatasetAssociation),
        grids.TextColumn("Type", key="extension", model_class=model.HistoryDatasetAssociation),
        grids.TextColumn("history_id", key="history_id", model_class=model.HistoryDatasetAssociation, visible=False),
        HistoryColumn("History", key="history", visible=True),
        DbKeyColumn("Build", key="dbkey", model_class=model.HistoryDatasetAssociation, visible=True, sortable=False),
    ]
    columns.append(
        grids.MulticolFilterColumn(
            "Search name and filetype",
            cols_to_filter=[columns[1], columns[2]],
            key="free-text-search",
            visible=False,
            filterable="standard",
        )
    )

    def build_initial_query(self, trans, **kwargs):
        return trans.sa_session.query(self.model_class).join(model.History.table).join(model.Dataset.table)

    def apply_query_filter(self, trans, query, **kwargs):
        if self.available_tracks is None:
            self.available_tracks = trans.app.datatypes_registry.get_available_tracks()
        return (
            query.filter(model.History.user == trans.user)
            .filter(model.HistoryDatasetAssociation.extension.in_(self.available_tracks))
            .filter(model.Dataset.state == model.Dataset.states.OK)
            .filter(model.HistoryDatasetAssociation.deleted == false())
            .filter(model.HistoryDatasetAssociation.visible == true())
        )


class LibraryDatasetsSelectionGrid(grids.Grid):
    available_tracks = None
    title = "Add Datasets"
    model_class = model.LibraryDatasetDatasetAssociation
    default_filter = {"deleted": "False"}
    default_sort_key = "-id"
    columns = [
        grids.GridColumn("Id", key="id"),
        grids.TextColumn("Name", key="name", model_class=model.LibraryDatasetDatasetAssociation),
        grids.TextColumn("Type", key="extension", model_class=model.LibraryDatasetDatasetAssociation),
    ]
    columns.append(
        grids.MulticolFilterColumn(
            "Search name and filetype",
            cols_to_filter=[columns[1], columns[2]],
            key="free-text-search",
            visible=False,
            filterable="standard",
        )
    )

    def build_initial_query(self, trans, **kwargs):
        return trans.sa_session.query(self.model_class).join(model.Dataset.table)

    def apply_query_filter(self, trans, query, **kwargs):
        if self.available_tracks is None:
            self.available_tracks = trans.app.datatypes_registry.get_available_tracks()
        return (
            query.filter(model.LibraryDatasetDatasetAssociation.user == trans.user)
            .filter(model.LibraryDatasetDatasetAssociation.extension.in_(self.available_tracks))
            .filter(model.Dataset.state == model.Dataset.states.OK)
            .filter(model.LibraryDatasetDatasetAssociation.deleted == false())
            .filter(model.LibraryDatasetDatasetAssociation.visible == true())
        )


class TracksterSelectionGrid(grids.Grid):
    title = "Insert into visualization"
    model_class = model.Visualization
    default_sort_key = "-update_time"
    use_paging = False
    show_item_checkboxes = True
    columns = [
        grids.TextColumn("Title", key="title", model_class=model.Visualization, filterable="standard"),
        grids.TextColumn("Build", key="dbkey", model_class=model.Visualization),
        grids.GridColumn("Last Updated", key="update_time", format=time_ago),
    ]

    def build_initial_query(self, trans, **kwargs):
        return trans.sa_session.query(self.model_class)

    def apply_query_filter(self, trans, query, **kwargs):
        return (
            query.filter(self.model_class.user_id == trans.user.id)
            .filter(self.model_class.deleted == false())
            .filter(self.model_class.type == "trackster")
        )


class VisualizationListGrid(grids.Grid):
    def get_url_args(item):
        """
        Returns dictionary used to create item link.
        """
        url_kwargs = dict(controller="visualization", id=item.id)
        # TODO: hack to build link to saved visualization - need trans in this function instead in order to do
        # link_data = trans.app.visualizations_registry.get_visualizations( trans, item )
        if item.type in registry.VisualizationsRegistry.BUILT_IN_VISUALIZATIONS:
            url_kwargs["action"] = item.type
        else:
            url_kwargs["__route_name__"] = "saved_visualization"
            url_kwargs["visualization_name"] = item.type
            url_kwargs["action"] = "saved"
        return url_kwargs

    def get_display_name(self, trans, item):
        if trans.app.visualizations_registry and item.type in trans.app.visualizations_registry.plugins:
            plugin = trans.app.visualizations_registry.plugins[item.type]
            return plugin.config.get("name", item.type)
        return item.type

    # Grid definition
    title = "Saved Visualizations"
    model_class = model.Visualization
    default_sort_key = "-update_time"
    default_filter = dict(title="All", deleted="False", tags="All", sharing="All")
    columns = [
        grids.TextColumn("Title", key="title", attach_popup=True, link=get_url_args),
        grids.TextColumn("Type", method="get_display_name"),
        grids.TextColumn("Build", key="dbkey"),
        grids.IndividualTagsColumn(
            "Tags",
            key="tags",
            model_tag_association_class=model.VisualizationTagAssociation,
            filterable="advanced",
            grid_name="VisualizationListGrid",
        ),
        grids.SharingStatusColumn("Sharing", key="sharing", filterable="advanced", sortable=False),
        grids.GridColumn("Created", key="create_time", format=time_ago),
        grids.GridColumn("Last Updated", key="update_time", format=time_ago),
    ]
    columns.append(
        grids.MulticolFilterColumn(
            "Search",
            cols_to_filter=[columns[0], columns[2]],
            key="free-text-search",
            visible=False,
            filterable="standard",
        )
    )
    operations = [
        grids.GridOperation("Open", allow_multiple=False, url_args=get_url_args),
        grids.GridOperation(
            "Edit Attributes", allow_multiple=False, url_args=dict(controller="", action="visualizations/edit")
        ),
        grids.GridOperation("Copy", allow_multiple=False, condition=(lambda item: not item.deleted)),
        grids.GridOperation(
            "Share or Publish",
            allow_multiple=False,
            condition=(lambda item: not item.deleted),
            url_args=dict(controller="", action="visualizations/sharing"),
        ),
        grids.GridOperation(
            "Delete",
            condition=(lambda item: not item.deleted),
            confirm="Are you sure you want to delete this visualization?",
        ),
    ]

    def apply_query_filter(self, trans, query, **kwargs):
        return query.filter_by(user=trans.user, deleted=False)


class VisualizationAllPublishedGrid(grids.Grid):
    # Grid definition
    use_panels = True
    title = "Published Visualizations"
    model_class = model.Visualization
    default_sort_key = "update_time"
    default_filter = dict(title="All", username="All")
    columns = [
        grids.PublicURLColumn("Title", key="title", filterable="advanced"),
        grids.OwnerAnnotationColumn(
            "Annotation",
            key="annotation",
            model_annotation_association_class=model.VisualizationAnnotationAssociation,
            filterable="advanced",
        ),
        grids.OwnerColumn("Owner", key="username", model_class=model.User, filterable="advanced"),
        grids.CommunityRatingColumn("Community Rating", key="rating"),
        grids.CommunityTagsColumn(
            "Community Tags",
            key="tags",
            model_tag_association_class=model.VisualizationTagAssociation,
            filterable="advanced",
            grid_name="VisualizationAllPublishedGrid",
        ),
        grids.ReverseSortColumn("Last Updated", key="update_time", format=time_ago),
    ]
    columns.append(
        grids.MulticolFilterColumn(
            "Search title, annotation, owner, and tags",
            cols_to_filter=[columns[0], columns[1], columns[2], columns[4]],
            key="free-text-search",
            visible=False,
            filterable="standard",
        )
    )

    def build_initial_query(self, trans, **kwargs):
        # See optimization description comments and TODO for tags in matching public histories query.
        return (
            trans.sa_session.query(self.model_class)
            .join(self.model_class.user)
            .options(
                joinedload(self.model_class.user).load_only("username"),
                joinedload(self.model_class.annotations),
                undefer("average_rating"),
            )
        )

    def apply_query_filter(self, trans, query, **kwargs):
        return query.filter(self.model_class.deleted == false()).filter(self.model_class.published == true())


class VisualizationController(
    BaseUIController, SharableMixin, UsesVisualizationMixin, UsesAnnotations, UsesItemRatings
):
    _visualization_list_grid = VisualizationListGrid()
    _published_list_grid = VisualizationAllPublishedGrid()
    _history_datasets_grid = HistoryDatasetsSelectionGrid()
    _library_datasets_grid = LibraryDatasetsSelectionGrid()
    _tracks_grid = TracksterSelectionGrid()
    hda_manager: HDAManager = depends(HDAManager)
    slug_builder: SlugBuilder = depends(SlugBuilder)

    def __init__(self, app: StructuredApp):
        super().__init__(app)

    #
    # -- Functions for listing visualizations. --
    #

    @web.expose
    @web.json
    @web.require_login("see all available libraries")
    def list_libraries(self, trans, **kwargs):
        """List all libraries that can be used for selecting datasets."""
        return self._libraries_grid(trans, **kwargs)

    @web.expose
    @web.json
    @web.require_login("see a history's datasets that can added to this visualization")
    def list_history_datasets(self, trans, **kwargs):
        """List a history's datasets that can be added to a visualization."""
        kwargs["show_item_checkboxes"] = "True"
        return self._history_datasets_grid(trans, **kwargs)

    @web.expose
    @web.json
    @web.require_login("see a history's datasets that can added to this visualization")
    def list_library_datasets(self, trans, **kwargs):
        """List a library's datasets that can be added to a visualization."""
        kwargs["show_item_checkboxes"] = "True"
        return self._library_datasets_grid(trans, **kwargs)

    @web.expose
    @web.json
    def list_tracks(self, trans, **kwargs):
        return self._tracks_grid(trans, **kwargs)

    @web.expose
    @web.json
    def list_published(self, trans, *args, **kwargs):
        grid = self._published_list_grid(trans, **kwargs)
        grid["shared_by_others"] = self._get_shared(trans)
        return grid

    @web.legacy_expose_api
    @web.require_login("use Galaxy visualizations", use_panels=True)
    def list(self, trans, **kwargs):
        message = kwargs.get("message")
        status = kwargs.get("status")
        if "operation" in kwargs and "id" in kwargs:
            session = trans.sa_session
            operation = kwargs["operation"].lower()
            ids = util.listify(kwargs["id"])
            for id in ids:
                if operation == "delete":
                    item = self.get_visualization(trans, id)
                    item.deleted = True
                if operation == "copy":
                    self.copy(trans, **kwargs)
            with transaction(session):
                session.commit()
        kwargs["embedded"] = True
        if message and status:
            kwargs["message"] = sanitize_text(message)
            kwargs["status"] = status
        grid = self._visualization_list_grid(trans, **kwargs)
        grid["shared_by_others"] = self._get_shared(trans)
        return grid

    def _get_shared(self, trans):
        """Identify shared visualizations"""
        shared_by_others = (
            trans.sa_session.query(model.VisualizationUserShareAssociation)
            .filter_by(user=trans.get_user())
            .join(model.Visualization.table)
            .filter(model.Visualization.deleted == false())
            .order_by(desc(model.Visualization.update_time))
            .all()
        )
        return [
            {"username": v.visualization.user.username, "slug": v.visualization.slug, "title": v.visualization.title}
            for v in shared_by_others
        ]

    #
    # -- Functions for operating on visualizations. --
    #

    @web.expose
    @web.require_login("use Galaxy visualizations", use_panels=True)
    def index(self, trans, *args, **kwargs):
        """Lists user's saved visualizations."""
        return self.list(trans, *args, **kwargs)

    @web.expose
    @web.require_login()
    def copy(self, trans, id, **kwargs):
        visualization = self.get_visualization(trans, id, check_ownership=False, check_accessible=True)
        user = trans.get_user()
        owner = visualization.user == user
        new_title = f"Copy of '{visualization.title}'"
        if not owner:
            new_title += f" shared by {visualization.user.email}"

        copied_viz = visualization.copy(user=trans.user, title=new_title)

        # Persist
        session = trans.sa_session
        session.add(copied_viz)
        with transaction(session):
            session.commit()

        # Display the management page
        trans.set_message(f'Created new visualization with name "{copied_viz.title}"')
        return

    @web.expose
    @web.require_login("share Galaxy visualizations")
    def imp(self, trans, id, **kwargs):
        """Import a visualization into user's workspace."""
        # Set referer message.
        referer = trans.request.referer
        if referer and not referer.startswith(f"{trans.request.application_url}{web.url_for('/login')}"):
            referer_message = f"<a href='{escape(referer)}'>return to the previous page</a>"
        else:
            referer_message = f"<a href='{web.url_for('/')}'>go to Galaxy's start page</a>"

        # Do import.
        session = trans.sa_session
        visualization = self.get_visualization(trans, id, check_ownership=False, check_accessible=True)
        if visualization.importable is False:
            return trans.show_error_message(
                f"The owner of this visualization has disabled imports via this link.<br>You can {referer_message}",
                use_panels=True,
            )
        elif visualization.deleted:
            return trans.show_error_message(
                f"You can't import this visualization because it has been deleted.<br>You can {referer_message}",
                use_panels=True,
            )
        else:
            # Create imported visualization via copy.
            #   TODO: need to handle custom db keys.

            imported_visualization = visualization.copy(user=trans.user, title=f"imported: {visualization.title}")

            # Persist
            session = trans.sa_session
            session.add(imported_visualization)
            with transaction(session):
                session.commit()

            # Redirect to load galaxy frames.
            return trans.show_ok_message(
                message="""Visualization "{}" has been imported. <br>You can <a href="{}">start using this visualization</a> or {}.""".format(
                    visualization.title, web.url_for("/visualizations/list"), referer_message
                ),
                use_panels=True,
            )

    @web.expose
    def display_by_username_and_slug(self, trans, username, slug, **kwargs):
        """Display visualization based on a username and slug."""

        # Get visualization.
        session = trans.sa_session
        user = session.query(model.User).filter_by(username=username).first()
        visualization = (
            trans.sa_session.query(model.Visualization).filter_by(user=user, slug=slug, deleted=False).first()
        )
        if visualization is None:
            raise web.httpexceptions.HTTPNotFound()

        # Security check raises error if user cannot access visualization.
        self.security_check(trans, visualization, check_ownership=False, check_accessible=True)

        # Encode page identifier.
        visualization_id = trans.security.encode_id(visualization.id)

        # Redirect to client.
        return trans.response.send_redirect(
            web.url_for(
                controller="published",
                action="visualization",
                id=visualization_id,
            )
        )

    @web.json
    def save(self, trans, vis_json=None, type=None, id=None, title=None, dbkey=None, annotation=None, **kwargs):
        """
        Save a visualization; if visualization does not have an ID, a new
        visualization is created. Returns JSON of visualization.
        """
        # Get visualization attributes from kwargs or from config.
        vis_config = loads(vis_json)
        vis_type = type or vis_config["type"]
        vis_id = id or vis_config.get("id", None)
        vis_title = title or vis_config.get("title", None)
        vis_dbkey = dbkey or vis_config.get("dbkey", None)
        vis_annotation = annotation or vis_config.get("annotation", None)
        return self.save_visualization(trans, vis_config, vis_type, vis_id, vis_title, vis_dbkey, vis_annotation)

    @web.legacy_expose_api
    @web.require_login("edit visualizations")
    def edit(self, trans, payload=None, **kwd):
        """
        Edit a visualization's attributes.
        """
        id = kwd.get("id")
        if not id:
            return self.message_exception(trans, "No visualization id received for editing.")
        trans_user = trans.get_user()
        v = self.get_visualization(trans, id, check_ownership=True)
        if trans.request.method == "GET":
            if v.slug is None:
                self.slug_builder.create_item_slug(trans.sa_session, v)
            return {
                "title": "Edit visualization attributes",
                "inputs": [
                    {"name": "title", "label": "Name", "value": v.title},
                    {
                        "name": "slug",
                        "label": "Identifier",
                        "value": v.slug,
                        "help": "A unique identifier that will be used for public links to this visualization. This field can only contain lowercase letters, numbers, and dashes (-).",
                    },
                    {
                        "name": "dbkey",
                        "label": "Build",
                        "type": "select",
                        "optional": True,
                        "value": v.dbkey,
                        "options": trans.app.genomes.get_dbkeys(trans_user, chrom_info=True),
                        "help": "Parameter to associate your visualization with a database key.",
                    },
                    {
                        "name": "annotation",
                        "label": "Annotation",
                        "value": self.get_item_annotation_str(trans.sa_session, trans.user, v),
                        "help": "A description of the visualization. The annotation is shown alongside published visualizations.",
                    },
                ],
            }
        else:
            v_title = payload.get("title")
            v_slug = payload.get("slug")
            v_dbkey = payload.get("dbkey")
            v_annotation = payload.get("annotation")
            if not v_title:
                return self.message_exception(trans, "Please provide a visualization name is required.")
            elif not v_slug:
                return self.message_exception(trans, "Please provide a unique identifier.")
            elif not self._is_valid_slug(v_slug):
                return self.message_exception(
                    trans, "Visualization identifier can only contain lowercase letters, numbers, and dashes (-)."
                )
            elif (
                v_slug != v.slug
                and trans.sa_session.query(model.Visualization)
                .filter_by(user=v.user, slug=v_slug, deleted=False)
                .first()
            ):
                return self.message_exception(trans, "Visualization id must be unique.")
            else:
                v.title = v_title
                v.slug = v_slug
                v.dbkey = v_dbkey
                if v_annotation:
                    v_annotation = sanitize_html(v_annotation)
                    self.add_item_annotation(trans.sa_session, trans_user, v, v_annotation)
                trans.sa_session.add(v)
                with transaction(trans.sa_session):
                    trans.sa_session.commit()
            return {"message": "Attributes of '%s' successfully saved." % v.title, "status": "success"}

    # ------------------------- registry.
    @web.expose
    @web.require_login("use Galaxy visualizations", use_panels=True)
    def render(self, trans, visualization_name, embedded=None, **kwargs):
        """
        Render the appropriate visualization template, parsing the `kwargs`
        into appropriate variables and resources (such as ORM models)
        based on this visualizations `param` data in visualizations_conf.xml.

        URL: /visualization/show/{visualization_name}
        """
        plugin = self._get_plugin_from_registry(trans, visualization_name)
        try:
            return plugin.render(trans=trans, embedded=embedded, **kwargs)
        except Exception as exception:
            self._handle_plugin_error(trans, visualization_name, exception)

    def _get_plugin_from_registry(self, trans, visualization_name):
        """
        Get the named plugin from the registry.
        :raises HTTPNotFound: if registry has been turned off in config.
        :raises HTTPNotFound: if visualization_name isn't a registered plugin.
        """
        if not trans.app.visualizations_registry:
            raise HTTPNotFound("No visualization registry (possibly disabled in galaxy.ini)")
        return trans.app.visualizations_registry.get_plugin(visualization_name)

    def _handle_plugin_error(self, trans, visualization_name, exception):
        """
        Log, raise if debugging; log and show html message if not.
        """
        log.exception("error rendering visualization (%s)", visualization_name)
        if trans.debug:
            raise exception
        return trans.show_error_message(
            "There was an error rendering the visualization. "
            + "Contact your Galaxy administrator if the problem persists."
            + "<br/>Details: "
            + unicodify(exception),
            use_panels=False,
        )

    @web.expose
    @web.require_login("use Galaxy visualizations", use_panels=True)
    def saved(self, trans, id=None, revision=None, type=None, config=None, title=None, **kwargs):
        """
        Save (on POST) or load (on GET) a visualization then render.
        """
        # TODO: consider merging saved and render at this point (could break saved URLs, tho)
        if trans.request.method == "POST":
            self._POST_to_saved(trans, id=id, revision=revision, type=type, config=config, title=title, **kwargs)

        # check the id and load the saved visualization
        if id is None:
            return HTTPBadRequest("A valid visualization id is required to load a visualization")
        visualization = self.get_visualization(trans, id, check_ownership=False, check_accessible=True)

        # re-add title to kwargs for passing to render
        if title:
            kwargs["title"] = title
        plugin = self._get_plugin_from_registry(trans, visualization.type)
        try:
            return plugin.render_saved(visualization, trans=trans, **kwargs)
        except Exception as exception:
            self._handle_plugin_error(trans, visualization.type, exception)

    def _POST_to_saved(self, trans, id=None, revision=None, type=None, config=None, title=None, **kwargs):
        """
        Save the visualiztion info (revision, type, config, title, etc.) to
        the Visualization at `id` or to a new Visualization if `id` is None.

        Uses POST/redirect/GET after a successful save, redirecting to GET.
        """
        DEFAULT_VISUALIZATION_NAME = "Unnamed Visualization"

        # post to saved in order to save a visualization
        if type is None or config is None:
            return HTTPBadRequest("A visualization type and config are required to save a visualization")
        if isinstance(config, str):
            config = loads(config)
        title = title or DEFAULT_VISUALIZATION_NAME

        # TODO: allow saving to (updating) a specific revision - should be part of UsesVisualization
        # TODO: would be easier if this returned the visualization directly
        # check security if posting to existing visualization
        if id is not None:
            self.get_visualization(trans, id, check_ownership=True, check_accessible=False)
            # ??: on not owner: error raised, but not returned (status = 200)
        # TODO: there's no security check in save visualization (if passed an id)
        returned = self.save_visualization(trans, config, type, id, title)

        # redirect to GET to prevent annoying 'Do you want to post again?' dialog on page reload
        render_url = web.url_for(controller="visualization", action="saved", id=returned.get("vis_id"))
        return trans.response.send_redirect(render_url)

    #
    # Visualizations.
    #
    @web.expose
    @web.require_login()
    def trackster(self, trans, **kwargs):
        """
        Display browser for the visualization denoted by id and add the datasets listed in `dataset_ids`.
        """

        # define app configuration
        app = {"jscript": "trackster"}

        # get dataset to add
        id = kwargs.get("id", None)

        # get dataset to add
        new_dataset_id = kwargs.get("dataset_id", None)

        # set up new browser if no id provided
        if not id:
            # use dbkey from dataset to be added or from incoming parameter
            dbkey = None
            if new_dataset_id:
                decoded_id = self.decode_id(new_dataset_id)
                hda = self.hda_manager.get_owned(decoded_id, trans.user, current_history=trans.user)
                dbkey = hda.dbkey
                if dbkey == "?":
                    dbkey = kwargs.get("dbkey", None)

            # save database key
            app["default_dbkey"] = dbkey
        else:
            # load saved visualization
            vis = self.get_visualization(trans, id, check_ownership=False, check_accessible=True)
            app["viz_config"] = self.get_visualization_config(trans, vis)

        # backup id
        app["id"] = id

        # add dataset id
        app["add_dataset"] = new_dataset_id

        # check for gene region
        gene_region = GenomeRegion.from_str(kwargs.get("gene_region", ""))

        # update gene region of saved visualization if user parses a new gene region in the url
        if gene_region.chrom is not None:
            app["gene_region"] = {"chrom": gene_region.chrom, "start": gene_region.start, "end": gene_region.end}

        # fill template
        return trans.fill_template("visualization/trackster.mako", config={"app": app, "bundle": "extended"})

    @web.expose
    def circster(self, trans, id=None, hda_ldda=None, dataset_id=None, dbkey=None, **kwargs):
        """
        Display a circster visualization.
        """

        # Get dataset to add.
        dataset = None
        if dataset_id:
            dataset = self.get_hda_or_ldda(trans, hda_ldda, dataset_id)

        # Get/create vis.
        if id:
            # Display existing viz.
            vis = self.get_visualization(trans, id, check_ownership=False, check_accessible=True)
            dbkey = vis.dbkey
        else:
            # Create new viz.
            if not dbkey:
                # If dbkey not specified, use dataset's dbkey.
                dbkey = dataset.dbkey
                if not dbkey or dbkey == "?":
                    # Circster requires a valid dbkey.
                    return trans.show_error_message(
                        "You must set the dataset's dbkey to view it. You can set "
                        "a dataset's dbkey by clicking on the pencil icon and editing "
                        "its attributes.",
                        use_panels=True,
                    )

            vis = self.create_visualization(trans, type="genome", dbkey=dbkey, save=False)

        # Get the vis config and work with it from here on out. Working with the
        # config is only possible because the config structure of trackster/genome
        # visualizations is well known.
        viz_config = self.get_visualization_config(trans, vis)

        # Add dataset if specified.
        if dataset:
            viz_config["tracks"].append(self.get_new_track_config(trans, dataset))

        # Get genome info.
        chroms_info = self.app.genomes.chroms(trans, dbkey=dbkey)
        genome = {"dbkey": dbkey, "chroms_info": chroms_info}

        # Add genome-wide data to each track in viz.
        tracks = viz_config.get("tracks", [])
        for track in tracks:
            dataset_dict = track["dataset"]
            dataset = self.get_hda_or_ldda(trans, dataset_dict["hda_ldda"], dataset_dict["id"])

            genome_data = self._get_genome_data(trans, dataset, dbkey)
            if not isinstance(genome_data, str):
                track["preloaded_data"] = genome_data

        # define app configuration for generic mako template
        app = {"jscript": "circster", "viz_config": viz_config, "genome": genome}

        # fill template
        return trans.fill_template("visualization/trackster.mako", config={"app": app, "bundle": "extended"})

    @web.expose
    def sweepster(self, trans, id=None, hda_ldda=None, dataset_id=None, regions=None, **kwargs):
        """
        Displays a sweepster visualization using the incoming parameters. If id is available,
        get the visualization with the given id; otherwise, create a new visualization using
        a given dataset and regions.
        """
        regions = regions or "{}"
        # Need to create history if necessary in order to create tool form.
        trans.get_history(most_recent=True, create=True)

        if id:
            # Loading a shared visualization.
            viz = self.get_visualization(trans, id)
            viz_config = self.get_visualization_config(trans, viz)
            decoded_id = self.decode_id(viz_config["dataset_id"])
            dataset = self.hda_manager.get_owned(decoded_id, trans.user, current_history=trans.history)
        else:
            # Loading new visualization.
            dataset = self.get_hda_or_ldda(trans, hda_ldda, dataset_id)
            job = self.hda_manager.creating_job(dataset)
            viz_config = {"dataset_id": dataset_id, "tool_id": job.tool_id, "regions": loads(regions)}

        # Add tool, dataset attributes to config based on id.
        tool = trans.app.toolbox.get_tool(viz_config["tool_id"])
        viz_config["tool"] = tool.to_dict(trans, io_details=True)
        viz_config["dataset"] = trans.security.encode_dict_ids(dataset.to_dict())

        return trans.fill_template_mako("visualization/sweepster.mako", config=viz_config)

    def get_item(self, trans, id):
        return self.get_visualization(trans, id)

    @web.expose
    def phyloviz(self, trans, id=None, dataset_id=None, tree_index=0, **kwargs):
        config = None
        data = None

        # if id, then this is a saved visualization; get its config and the dataset_id from there
        if id:
            visualization = self.get_visualization(trans, id)
            config = self.get_visualization_config(trans, visualization)
            dataset_id = config.get("dataset_id", None)

        # get the hda if we can, then its data using the phyloviz parsers
        if dataset_id:
            decoded_id = self.decode_id(dataset_id)
            hda = self.hda_manager.get_accessible(decoded_id, trans.user)
            hda = self.hda_manager.error_if_uploading(hda)
        else:
            return trans.show_message("Phyloviz couldn't find a dataset_id")

        pd = PhylovizDataProvider(original_dataset=hda)
        data = pd.get_data(tree_index=tree_index)

        # ensure at least a default configuration (gen. an new/unsaved visualization)
        if not config:
            config = {
                "dataset_id": dataset_id,
                "title": hda.display_name(),
                "ext": hda.datatype.file_ext,
                "treeIndex": tree_index,
                "saved_visualization": False,
            }
        return trans.fill_template_mako("visualization/phyloviz.mako", data=data, config=config)
