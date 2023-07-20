import copy
import csv
import logging
import re

from markupsafe import escape

from galaxy import (
    model,
    util,
)
from galaxy.model.base import transaction
from galaxy.web.framework.helpers import (
    grids,
    iff,
    time_ago,
)
from galaxy.webapps.base.controller import (
    BaseUIController,
    web,
)

log = logging.getLogger(__name__)

VALID_FIELDNAME_RE = re.compile(r"^[a-zA-Z0-9\_]+$")


class FormsGrid(grids.Grid):
    # Custom column types
    class NameColumn(grids.TextColumn):
        def get_value(self, trans, grid, form):
            return escape(form.latest_form.name)

    class DescriptionColumn(grids.TextColumn):
        def get_value(self, trans, grid, form):
            return escape(form.latest_form.desc)

    class TypeColumn(grids.TextColumn):
        def get_value(self, trans, grid, form):
            return form.latest_form.type

    class StatusColumn(grids.GridColumn):
        def get_value(self, trans, grid, user):
            if user.deleted:
                return "deleted"
            return "active"

    # Grid definition
    title = "Forms"
    model_class = model.FormDefinitionCurrent
    default_sort_key = "-update_time"
    num_rows_per_page = 50
    use_paging = True
    default_filter = dict(deleted="False")
    columns = [
        NameColumn(
            "Name",
            key="name",
            model_class=model.FormDefinition,
            link=(lambda item: iff(item.deleted, None, dict(controller="admin", action="form/edit_form", id=item.id))),
            attach_popup=True,
            filterable="advanced",
        ),
        DescriptionColumn("Description", key="desc", model_class=model.FormDefinition, filterable="advanced"),
        TypeColumn("Type"),
        grids.GridColumn("Last Updated", key="update_time", format=time_ago),
        StatusColumn("Status"),
        grids.DeletedColumn("Deleted", key="deleted", visible=False, filterable="advanced"),
    ]
    columns.append(
        grids.MulticolFilterColumn(
            "Search",
            cols_to_filter=[columns[0], columns[1]],
            key="free-text-search",
            visible=False,
            filterable="standard",
        )
    )
    operations = [
        grids.GridOperation("Delete", allow_multiple=True, condition=(lambda item: not item.deleted)),
        grids.GridOperation("Undelete", condition=(lambda item: item.deleted)),
    ]
    global_actions = [grids.GridAction("Create new form", dict(controller="admin", action="form/create_form"))]

    def build_initial_query(self, trans, **kwargs):
        return trans.sa_session.query(self.model_class).join(
            model.FormDefinition, self.model_class.latest_form_id == model.FormDefinition.id
        )


class Forms(BaseUIController):
    forms_grid = FormsGrid()

    @web.legacy_expose_api
    @web.require_admin
    def forms_list(self, trans, payload=None, **kwd):
        message = kwd.get("message", "")
        status = kwd.get("status", "")
        if "operation" in kwd:
            id = kwd.get("id")
            if not id:
                return self.message_exception(trans, f"Invalid form id ({str(id)}) received.")
            ids = util.listify(id)
            operation = kwd["operation"].lower()
            if operation == "delete":
                message, status = self._delete_form(trans, ids)
            elif operation == "undelete":
                message, status = self._undelete_form(trans, ids)
        if message and status:
            kwd["message"] = util.sanitize_text(message)
            kwd["status"] = status
        return self.forms_grid(trans, **kwd)

    @web.legacy_expose_api
    @web.require_admin
    def create_form(self, trans, payload=None, **kwd):
        if trans.request.method == "GET":
            fd_types = sorted(trans.app.model.FormDefinition.types.__members__.items())
            return {
                "title": "Create new form",
                "inputs": [
                    {"name": "name", "label": "Name"},
                    {"name": "desc", "label": "Description"},
                    {
                        "name": "type",
                        "type": "select",
                        "options": [(ft[1], ft[1]) for ft in fd_types],
                        "label": "Type",
                    },
                    {
                        "name": "csv_file",
                        "label": "Import from CSV",
                        "type": "upload",
                        "help": "Import fields from CSV-file with the following format: Label, Help, Type, Value, Options, Required=True/False.",
                        "optional": True,
                    },
                ],
            }
        else:
            # csv-file format: label, helptext, type, default, selectlist, required '''
            csv_file = payload.get("csv_file")
            index = 0
            if csv_file:
                lines = csv_file.splitlines()
                rows = csv.reader(lines)
                for row in rows:
                    if len(row) >= 6:
                        for column in range(len(row)):
                            row[column] = str(row[column]).strip('"')
                        prefix = "fields_%i|" % index
                        payload[f"{prefix}name"] = "%i_imported_field" % (index + 1)
                        payload[f"{prefix}label"] = row[0]
                        payload[f"{prefix}helptext"] = row[1]
                        payload[f"{prefix}type"] = row[2]
                        payload[f"{prefix}default"] = row[3]
                        payload[f"{prefix}selectlist"] = row[4]
                        payload[f"{prefix}required"] = row[5].lower() == "true"
                    index = index + 1
            new_form, message = self.save_form_definition(trans, None, payload)
            if new_form is None:
                return self.message_exception(trans, message)
            imported = (" with %i imported fields" % index) if index > 0 else ""
            message = f"The form '{payload.get('name')}' has been created{imported}."
            return {"message": util.sanitize_text(message)}

    @web.legacy_expose_api
    @web.require_admin
    def edit_form(self, trans, payload=None, **kwd):
        id = kwd.get("id")
        if not id:
            return self.message_exception(trans, "No form id received for editing.")
        form = get_form(trans, id)
        latest_form = form.latest_form
        if trans.request.method == "GET":
            fd_types = sorted(trans.app.model.FormDefinition.types.__members__.items())
            ff_types = [(t.__name__, t.__name__) for t in trans.model.FormDefinition.supported_field_types]
            field_cache = []
            field_inputs = [
                {
                    "name": "name",
                    "label": "Name",
                    "value": "field_name",
                    "help": "The field name must be unique for each field and must contain only alphanumeric characters and underscore.",
                },
                {"name": "label", "label": "Label", "value": "Field label"},
                {"name": "helptext", "label": "Help text"},
                {"name": "type", "label": "Type", "type": "select", "options": ff_types},
                {"name": "default", "label": "Default value"},
                {
                    "name": "selectlist",
                    "label": "Options",
                    "help": "*Only for fields which allow multiple selections, provide comma-separated values.",
                },
                {"name": "required", "label": "Required", "type": "boolean", "value": False},
            ]
            form_dict = {
                "title": "Edit form for '%s'" % (util.sanitize_text(latest_form.name)),
                "inputs": [
                    {"name": "name", "label": "Name", "value": latest_form.name},
                    {"name": "desc", "label": "Description", "value": latest_form.desc},
                    {
                        "name": "type",
                        "type": "select",
                        "options": [(ft[1], ft[1]) for ft in fd_types],
                        "label": "Type",
                        "value": latest_form.type,
                    },
                    {
                        "name": "fields",
                        "title": "Field",
                        "type": "repeat",
                        "cache": field_cache,
                        "inputs": field_inputs,
                    },
                ],
            }
            for field in latest_form.fields:
                new_field = copy.deepcopy(field_inputs)
                for field_input in new_field:
                    field_value = field.get(field_input["name"])
                    if field_value:
                        if isinstance(field_value, list):
                            field_value = ",".join(field_value)
                        field_input["value"] = str(field_value)
                field_cache.append(new_field)
            return form_dict
        else:
            new_form, message = self.save_form_definition(trans, id, payload)
            if new_form is None:
                return self.message_exception(trans, message)
            message = f"The form '{payload.get('name')}' has been updated."
            return {"message": util.sanitize_text(message)}

    def get_current_form(self, trans, payload=None, **kwd):
        """
        This method gets all the unsaved user-entered form details and returns a
        dictionary containing the name, desc, type, layout & fields of the form
        """
        name = payload.get("name")
        desc = payload.get("desc") or ""
        type = payload.get("type")
        fields = []
        index = 0
        while True:
            prefix = "fields_%i|" % index
            if f"{prefix}label" in payload:
                field_attributes = ["name", "label", "helptext", "required", "type", "selectlist", "default"]
                field_dict = {attr: payload.get(f"{prefix}{attr}") for attr in field_attributes}
                field_dict["visible"] = True
                if isinstance(field_dict["selectlist"], str):
                    field_dict["selectlist"] = field_dict["selectlist"].split(",")
                else:
                    field_dict["selectlist"] = []
                fields.append(field_dict)
                index = index + 1
            else:
                break
        return dict(name=name, desc=desc, type=type, layout=[], fields=fields)

    def save_form_definition(self, trans, form_id=None, payload=None, **kwd):
        """
        This method saves a form given an id
        """
        if not payload.get("name"):
            return None, "Please provide a form name."
        if payload.get("type") == "none":
            return None, "Please select a form type."
        current_form = self.get_current_form(trans, payload)
        # validate fields
        field_names_dict = {}
        for field in current_form["fields"]:
            if not field["label"]:
                return None, "All the field labels must be completed."
            if not VALID_FIELDNAME_RE.match(field["name"]):
                return None, f"{field['name']} is not a valid field name."
            if field["name"] in field_names_dict:
                return None, f"Each field name must be unique in the form definition. {field['name']} is not unique."
            else:
                field_names_dict[field["name"]] = 1
        # create a new form definition
        form_definition = trans.app.model.FormDefinition(
            name=current_form["name"],
            desc=current_form["desc"],
            fields=current_form["fields"],
            form_definition_current=None,
            type=current_form["type"],
            layout=current_form["layout"],
        )
        # save changes to the existing form
        if form_id:
            form_definition_current = trans.sa_session.query(trans.app.model.FormDefinitionCurrent).get(
                trans.security.decode_id(form_id)
            )
            if form_definition_current is None:
                return None, f"Invalid form id ({form_id}) provided. Cannot save form."
        else:
            form_definition_current = trans.app.model.FormDefinitionCurrent()
        # create corresponding row in the form_definition_current table
        form_definition.form_definition_current = form_definition_current
        form_definition_current.latest_form = form_definition
        trans.sa_session.add(form_definition_current)
        with transaction(trans.sa_session):
            trans.sa_session.commit()
        return form_definition, None

    @web.expose
    @web.require_admin
    def _delete_form(self, trans, ids):
        for form_id in ids:
            form = get_form(trans, form_id)
            form.deleted = True
            trans.sa_session.add(form)
            with transaction(trans.sa_session):
                trans.sa_session.commit()
        return ("Deleted %i form(s)." % len(ids), "done")

    @web.expose
    @web.require_admin
    def _undelete_form(self, trans, ids):
        for form_id in ids:
            form = get_form(trans, form_id)
            form.deleted = False
            trans.sa_session.add(form)
            with transaction(trans.sa_session):
                trans.sa_session.commit()
        return ("Undeleted %i form(s)." % len(ids), "done")


# ---- Utility methods -------------------------------------------------------


def get_form(trans, form_id):
    """Get a FormDefinition from the database by id."""
    form = trans.sa_session.query(trans.app.model.FormDefinitionCurrent).get(trans.security.decode_id(form_id))
    if not form:
        return trans.show_error_message(f"Form not found for id ({str(form_id)})")
    return form
