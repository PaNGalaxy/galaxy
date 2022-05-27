"""
API operations for Workflows
"""

import hashlib
import json
import logging
import os
from typing import Any, Dict

import requests
from gxformat2._yaml import ordered_dump
from markupsafe import escape
from sqlalchemy import desc, false, or_, true
from sqlalchemy.orm import joinedload

from galaxy import (
    exceptions,
    model,
    util
)
from galaxy.managers.context import ProvidesUserContext
from galaxy.managers.jobs import fetch_job_states, invocation_job_source_iter, summarize_job_metrics
from galaxy.managers.workflows import (
    MissingToolsException,
    RefactorRequest,
    WorkflowCreateOptions,
    WorkflowUpdateOptions,
)
from galaxy.model.item_attrs import UsesAnnotations
from galaxy.schema.schema import InvocationIndexPayload
from galaxy.structured_app import StructuredApp
from galaxy.tool_shed.galaxy_install.install_manager import InstallRepositoryManager
from galaxy.tools import recommendations
from galaxy.tools.parameters import populate_state
from galaxy.tools.parameters.basic import workflow_building_modes
from galaxy.util.sanitize_html import sanitize_html
from galaxy.version import VERSION
from galaxy.web import (
    expose_api,
    expose_api_anonymous_and_sessionless,
    expose_api_raw,
    expose_api_raw_anonymous_and_sessionless,
    format_return_as_json,
)
from galaxy.webapps.base.controller import (
    SharableMixin,
    url_for,
    UsesStoredWorkflowMixin
)
from galaxy.webapps.base.webapp import GalaxyWebTransaction
from galaxy.workflow.extract import extract_workflow
from galaxy.workflow.modules import module_factory
from galaxy.workflow.run import queue_invoke
from galaxy.workflow.run_request import build_workflow_run_configs
from . import BaseGalaxyAPIController

log = logging.getLogger(__name__)


class WorkflowsAPIController(BaseGalaxyAPIController, UsesStoredWorkflowMixin, UsesAnnotations, SharableMixin):

    def __init__(self, app: StructuredApp):
        super().__init__(app)
        self.history_manager = app.history_manager
        self.workflow_manager = app.workflow_manager
        self.workflow_contents_manager = app.workflow_contents_manager
        self.tool_recommendations = recommendations.ToolRecommendations()

    def __get_full_shed_url(self, url):
        for shed_url in self.app.tool_shed_registry.tool_sheds.values():
            if url in shed_url:
                return shed_url
        return None

    @expose_api_anonymous_and_sessionless
    def index(self, trans: ProvidesUserContext, **kwd):
        """
        GET /api/workflows
        """
        return self.get_workflows_list(trans, **kwd)

    @expose_api
    def get_workflow_menu(self, trans: ProvidesUserContext, **kwd):
        """
        Get workflows present in the tools panel
        GET /api/workflows/menu
        """
        user = trans.user
        ids_in_menu = [x.stored_workflow_id for x in user.stored_workflow_menu_entries]
        return {
            'ids_in_menu': ids_in_menu,
            'workflows': self.get_workflows_list(trans, **kwd)
        }

    @expose_api
    def set_workflow_menu(self, trans: GalaxyWebTransaction, payload=None, **kwd):
        """
        Save workflow menu to be shown in the tool panel
        PUT /api/workflows/menu
        """
        payload = payload or {}
        user = trans.user
        workflow_ids = payload.get('workflow_ids')
        if workflow_ids is None:
            workflow_ids = []
        elif type(workflow_ids) != list:
            workflow_ids = [workflow_ids]
        workflow_ids_decoded = []
        # Decode the encoded workflow ids
        for ids in workflow_ids:
            workflow_ids_decoded.append(trans.security.decode_id(ids))
        sess = trans.sa_session
        # This explicit remove seems like a hack, need to figure out
        # how to make the association do it automatically.
        for m in user.stored_workflow_menu_entries:
            sess.delete(m)
        user.stored_workflow_menu_entries = []
        q = sess.query(model.StoredWorkflow)
        # To ensure id list is unique
        seen_workflow_ids = set()
        for wf_id in workflow_ids_decoded:
            if wf_id in seen_workflow_ids:
                continue
            else:
                seen_workflow_ids.add(wf_id)
            m = model.StoredWorkflowMenuEntry()
            m.stored_workflow = q.get(wf_id)
            user.stored_workflow_menu_entries.append(m)
        sess.flush()
        message = "Menu updated."
        trans.set_message(message)
        return {'message': message, 'status': 'done'}

    def get_workflows_list(self, trans: ProvidesUserContext, missing_tools=False, show_published=None, show_hidden=False, show_deleted=False, **kwd):
        """
        Displays a collection of workflows.

        :param  show_published:      if True, show also published workflows
        :type   show_published:      boolean
        :param  show_hidden:         if True, show hidden workflows
        :type   show_hidden:         boolean
        :param  show_deleted:        if True, show deleted workflows
        :type   show_deleted:        boolean
        :param  missing_tools:       if True, include a list of missing tools per workflow
        :type   missing_tools:       boolean
        """
        rval = []
        filter1 = model.StoredWorkflow.user == trans.user
        user = trans.user
        if show_published or user is None and show_published is None:
            filter1 = or_(filter1, (model.StoredWorkflow.published == true()))
        query = trans.sa_session.query(model.StoredWorkflow).options(
            joinedload("annotations")).options(
            joinedload("latest_workflow").undefer("step_count").lazyload("steps")).options(
            joinedload("tags")
        ).filter(filter1)
        query = query.filter_by(hidden=true() if show_hidden else false(), deleted=true() if show_deleted else false())
        for wf in query.order_by(desc(model.StoredWorkflow.table.c.update_time)).all():
            item = wf.to_dict(value_mapper={'id': trans.security.encode_id})
            encoded_id = trans.security.encode_id(wf.id)
            item['annotations'] = [x.annotation for x in wf.annotations]
            item['url'] = url_for('workflow', id=encoded_id)
            item['owner'] = wf.user.username
            item['number_of_steps'] = wf.latest_workflow.step_count
            item['show_in_tool_panel'] = False
            if user is not None:
                item['show_in_tool_panel'] = wf.show_in_tool_panel(user_id=user.id)
            rval.append(item)
        for wf_sa in trans.sa_session.query(model.StoredWorkflowUserShareAssociation).join(
                model.StoredWorkflowUserShareAssociation.stored_workflow).options(
                joinedload("stored_workflow").joinedload("annotations")).options(
                joinedload("stored_workflow").joinedload("latest_workflow").undefer("step_count").lazyload("steps")).options(
                joinedload("stored_workflow").joinedload("user")).options(
                joinedload("stored_workflow").joinedload("tags")).filter(model.StoredWorkflowUserShareAssociation.user == trans.user).filter(
                model.StoredWorkflow.table.c.deleted == false()).order_by(
                desc(model.StoredWorkflow.update_time)).all():
            item = wf_sa.stored_workflow.to_dict(value_mapper={'id': trans.security.encode_id})
            encoded_id = trans.security.encode_id(wf_sa.stored_workflow.id)
            item['annotations'] = [x.annotation for x in wf_sa.stored_workflow.annotations]
            item['url'] = url_for('workflow', id=encoded_id)
            item['slug'] = wf_sa.stored_workflow.slug
            item['owner'] = wf_sa.stored_workflow.user.username
            item['number_of_steps'] = wf_sa.stored_workflow.latest_workflow.step_count
            item['show_in_tool_panel'] = False
            if user is not None:
                item['show_in_tool_panel'] = wf_sa.stored_workflow.show_in_tool_panel(user_id=user.id)
            rval.append(item)
        if missing_tools:
            workflows_missing_tools = []
            workflows = []
            workflows_by_toolshed = dict()
            for value in rval:
                tools = self.workflow_contents_manager.get_all_tools(
                    self.__get_stored_workflow(trans, value["id"]).latest_workflow
                )
                missing_tool_ids = [
                    tool["tool_id"] for tool in tools if self.app.toolbox.is_missing_shed_tool(tool["tool_id"])
                ]
                if len(missing_tool_ids) > 0:
                    value['missing_tools'] = missing_tool_ids
                    workflows_missing_tools.append(value)
            for workflow in workflows_missing_tools:
                for tool_id in workflow['missing_tools']:
                    toolshed, _, owner, name, tool, version = tool_id.split('/')
                    shed_url = self.__get_full_shed_url(toolshed)
                    repo_identifier = '/'.join((toolshed, owner, name))
                    if repo_identifier not in workflows_by_toolshed:
                        workflows_by_toolshed[repo_identifier] = dict(shed=shed_url.rstrip('/'), repository=name, owner=owner, tools=[tool_id], workflows=[workflow['name']])
                    else:
                        if tool_id not in workflows_by_toolshed[repo_identifier]['tools']:
                            workflows_by_toolshed[repo_identifier]['tools'].append(tool_id)
                        if workflow['name'] not in workflows_by_toolshed[repo_identifier]['workflows']:
                            workflows_by_toolshed[repo_identifier]['workflows'].append(workflow['name'])
            for repo_tag in workflows_by_toolshed:
                workflows.append(workflows_by_toolshed[repo_tag])
            return workflows
        return rval

    @expose_api_anonymous_and_sessionless
    def show(self, trans: GalaxyWebTransaction, id, **kwd):
        """
        GET /api/workflows/{encoded_workflow_id}

        :param  instance:                 true if fetch by Workflow ID instead of StoredWorkflow id, false
                                          by default.
        :type   instance:                 boolean

        Displays information needed to run a workflow.
        """
        stored_workflow = self.__get_stored_workflow(trans, id, **kwd)
        if stored_workflow.importable is False and stored_workflow.user != trans.user and not trans.user_is_admin:
            if trans.sa_session.query(model.StoredWorkflowUserShareAssociation).filter_by(user=trans.user, stored_workflow=stored_workflow).count() == 0:
                message = "Workflow is neither importable, nor owned by or shared with current user"
                raise exceptions.ItemAccessibilityException(message)
        if kwd.get("legacy", False):
            style = "legacy"
        else:
            style = "instance"
        version = kwd.get('version')
        if version is None and util.string_as_bool(kwd.get("instance", "false")):
            # A Workflow instance may not be the latest workflow version attached to StoredWorkflow.
            # This figures out the correct version so that we return the correct Workflow and version.
            workflow_id = self.decode_id(id)
            for i, workflow in enumerate(reversed(stored_workflow.workflows)):
                if workflow.id == workflow_id:
                    version = i
                    break
        return self.workflow_contents_manager.workflow_to_dict(trans, stored_workflow, style=style, version=version)

    @expose_api
    def show_versions(self, trans: GalaxyWebTransaction, workflow_id, **kwds):
        """
        GET /api/workflows/{encoded_workflow_id}/versions

        :param  instance:                 true if fetch by Workflow ID instead of StoredWorkflow id, false
                                          by default.
        :type   instance:                 boolean

        Lists all versions of this workflow.
        """
        instance = util.string_as_bool(kwds.get("instance", "false"))
        stored_workflow = self.workflow_manager.get_stored_accessible_workflow(trans, workflow_id, by_stored_id=not instance)
        return [{'version': i, 'update_time': str(w.update_time), 'steps': len(w.steps)} for i, w in enumerate(reversed(stored_workflow.workflows))]

    @expose_api
    def create(self, trans: GalaxyWebTransaction, payload=None, **kwd):
        """
        POST /api/workflows

        Create workflows in various ways.

        :param  from_history_id:             Id of history to extract a workflow from.
        :type   from_history_id:             str

        :param  job_ids:                     If from_history_id is set - optional list of jobs to include when extracting a workflow from history
        :type   job_ids:                     str

        :param  dataset_ids:                 If from_history_id is set - optional list of HDA "hid"s corresponding to workflow inputs when extracting a workflow from history
        :type   dataset_ids:                 str

        :param  dataset_collection_ids:      If from_history_id is set - optional list of HDCA "hid"s corresponding to workflow inputs when extracting a workflow from history
        :type   dataset_collection_ids:      str

        :param  workflow_name:               If from_history_id is set - name of the workflow to create when extracting a workflow from history
        :type   workflow_name:               str

        """
        ways_to_create = {
            'archive_source',
            'from_history_id',
            'from_path',
            'shared_workflow_id',
            'workflow',
        }

        if trans.user_is_bootstrap_admin:
            raise exceptions.RealUserRequiredException("Only real users can create or run workflows.")

        if payload is None or len(ways_to_create.intersection(payload)) == 0:
            message = f"One parameter among - {', '.join(ways_to_create)} - must be specified"
            raise exceptions.RequestParameterMissingException(message)

        if len(ways_to_create.intersection(payload)) > 1:
            message = f"Only one parameter among - {', '.join(ways_to_create)} - must be specified"
            raise exceptions.RequestParameterInvalidException(message)

        if 'archive_source' in payload:
            archive_source = payload['archive_source']
            archive_file = payload.get('archive_file')
            archive_data = None
            if archive_source:
                if archive_source.startswith("file://"):
                    if not trans.user_is_admin:
                        raise exceptions.AdminRequiredException()
                    workflow_src = {"src": "from_path", "path": archive_source[len("file://"):]}
                    payload["workflow"] = workflow_src
                    return self.__api_import_new_workflow(trans, payload, **kwd)
                elif archive_source == "trs_tool":
                    trs_server = payload.get("trs_server")
                    trs_tool_id = payload.get("trs_tool_id")
                    trs_version_id = payload.get("trs_version_id")
                    archive_data = self.app.trs_proxy.get_version_descriptor(trs_server, trs_tool_id, trs_version_id)
                else:
                    try:
                        archive_data = requests.get(archive_source, timeout=util.DEFAULT_SOCKET_TIMEOUT).text
                    except Exception:
                        raise exceptions.MessageException(f"Failed to open URL '{escape(archive_source)}'.")
            elif hasattr(archive_file, 'file'):
                uploaded_file = archive_file.file
                uploaded_file_name = uploaded_file.name
                if os.path.getsize(os.path.abspath(uploaded_file_name)) > 0:
                    archive_data = util.unicodify(uploaded_file.read())
                else:
                    raise exceptions.MessageException("You attempted to upload an empty file.")
            else:
                raise exceptions.MessageException("Please provide a URL or file.")
            return self.__api_import_from_archive(trans, archive_data, "uploaded file", payload=payload)

        if 'from_history_id' in payload:
            from_history_id = payload.get('from_history_id')
            from_history_id = self.decode_id(from_history_id)
            history = self.history_manager.get_accessible(from_history_id, trans.user, current_history=trans.history)

            job_ids = [self.decode_id(_) for _ in payload.get('job_ids', [])]
            dataset_ids = payload.get('dataset_ids', [])
            dataset_collection_ids = payload.get('dataset_collection_ids', [])
            workflow_name = payload['workflow_name']
            stored_workflow = extract_workflow(
                trans=trans,
                user=trans.user,
                history=history,
                job_ids=job_ids,
                dataset_ids=dataset_ids,
                dataset_collection_ids=dataset_collection_ids,
                workflow_name=workflow_name,
            )
            item = stored_workflow.to_dict(value_mapper={'id': trans.security.encode_id})
            item['url'] = url_for('workflow', id=item['id'])
            return item

        if 'from_path' in payload:
            from_path = payload.get('from_path')
            object_id = payload.get("object_id")
            workflow_src = {"src": "from_path", "path": from_path}
            if object_id is not None:
                workflow_src["object_id"] = object_id
            payload["workflow"] = workflow_src
            return self.__api_import_new_workflow(trans, payload, **kwd)

        if 'shared_workflow_id' in payload:
            workflow_id = payload['shared_workflow_id']
            return self.__api_import_shared_workflow(trans, workflow_id, payload)

        if 'workflow' in payload:
            return self.__api_import_new_workflow(trans, payload, **kwd)

        # This was already raised above, but just in case...
        raise exceptions.RequestParameterMissingException("No method for workflow creation supplied.")

    @expose_api_raw_anonymous_and_sessionless
    def workflow_dict(self, trans: GalaxyWebTransaction, workflow_id, **kwd):
        """
        GET /api/workflows/{encoded_workflow_id}/download

        Returns a selected workflow.

        :type   style:  str
        :param  style:  Style of export. The default is 'export', which is the meant to be used
                        with workflow import endpoints. Other formats such as 'instance', 'editor',
                        'run' are more tied to the GUI and should not be considered stable APIs.
                        The default format for 'export' is specified by the
                        admin with the `default_workflow_export_format` config
                        option. Style can be specified as either 'ga' or 'format2' directly
                        to be explicit about which format to download.

        :param  instance:                 true if fetch by Workflow ID instead of StoredWorkflow id, false
                                          by default.
        :type   instance:                 boolean
        """
        stored_workflow = self.__get_stored_accessible_workflow(trans, workflow_id, **kwd)

        style = kwd.get("style", "export")
        download_format = kwd.get('format')
        version = kwd.get('version')
        history_id = kwd.get('history_id')
        history = None
        if history_id:
            history = self.history_manager.get_accessible(self.decode_id(history_id), trans.user, current_history=trans.history)
        ret_dict = self.workflow_contents_manager.workflow_to_dict(trans, stored_workflow, style=style, version=version, history=history)
        if download_format == 'json-download':
            sname = stored_workflow.name
            sname = ''.join(c in util.FILENAME_VALID_CHARS and c or '_' for c in sname)[0:150]
            if ret_dict.get("format-version", None) == "0.1":
                extension = "ga"
            else:
                extension = "gxwf.json"
            trans.response.headers["Content-Disposition"] = f'attachment; filename="Galaxy-Workflow-{sname}.{extension}"'
            trans.response.set_content_type('application/galaxy-archive')

        if style == "format2" and download_format != 'json-download':
            return ordered_dump(ret_dict)
        else:
            return format_return_as_json(ret_dict, pretty=True)

    @expose_api
    def delete(self, trans: ProvidesUserContext, id, **kwd):
        """
        DELETE /api/workflows/{encoded_workflow_id}
        Deletes a specified workflow
        Author: rpark

        copied from galaxy.web.controllers.workflows.py (delete)
        """
        stored_workflow = self.__get_stored_workflow(trans, id, **kwd)

        # check to see if user has permissions to selected workflow
        if stored_workflow.user != trans.user and not trans.user_is_admin:
            raise exceptions.InsufficientPermissionsException()

        # Mark a workflow as deleted
        stored_workflow.deleted = True
        trans.sa_session.flush()

        # TODO: Unsure of response message to let api know that a workflow was successfully deleted
        return (f"Workflow '{stored_workflow.name}' successfully deleted")

    @expose_api
    def import_new_workflow_deprecated(self, trans: GalaxyWebTransaction, payload, **kwd):
        """
        POST /api/workflows/upload
        Importing dynamic workflows from the api. Return newly generated workflow id.
        Author: rpark

        # currently assumes payload['workflow'] is a json representation of a workflow to be inserted into the database

        Deprecated in favor to POST /api/workflows with encoded 'workflow' in
        payload the same way.
        """
        return self.__api_import_new_workflow(trans, payload, **kwd)

    @expose_api
    def update(self, trans: GalaxyWebTransaction, id, payload, **kwds):
        """
        PUT /api/workflows/{id}

        Update the workflow stored with ``id``.

        :type   id:      str
        :param  id:      the encoded id of the workflow to update
        :param  instance: true if fetch by Workflow ID instead of StoredWorkflow id, false by default.
        :type   instance: boolean
        :type   payload: dict
        :param  payload: a dictionary containing any or all the

            :workflow:

                the json description of the workflow as would be
                produced by GET workflows/<id>/download or
                given to `POST workflows`

                The workflow contents will be updated to target this.

            :name:

                optional string name for the workflow, if not present in payload,
                name defaults to existing name

            :annotation:

                optional string annotation for the workflow, if not present in payload,
                annotation defaults to existing annotation

            :menu_entry:

                optional boolean marking if the workflow should appear in the user\'s menu,
                if not present, workflow menu entries are not modified

            :tags:

                optional list containing list of tags to add to the workflow (overwriting
                existing tags), if not present, tags are not modified

            :from_tool_form:

                True iff encoded state coming in is encoded for the tool form.


        :rtype:     dict
        :returns:   serialized version of the workflow
        """
        stored_workflow = self.__get_stored_workflow(trans, id, **kwds)
        workflow_dict = payload.get('workflow', {})
        workflow_dict.update({k: v for k, v in payload.items() if k not in workflow_dict})
        if workflow_dict:
            raw_workflow_description = self.__normalize_workflow(trans, workflow_dict)
            workflow_dict = raw_workflow_description.as_dict
            new_workflow_name = workflow_dict.get('name')
            old_workflow = stored_workflow.latest_workflow
            name_updated = (new_workflow_name and new_workflow_name != stored_workflow.name)
            steps_updated = 'steps' in workflow_dict
            if name_updated and not steps_updated:
                sanitized_name = sanitize_html(new_workflow_name or old_workflow.name)
                workflow = old_workflow.copy(user=trans.user)
                workflow.stored_workflow = stored_workflow
                workflow.name = sanitized_name
                stored_workflow.name = sanitized_name
                stored_workflow.latest_workflow = workflow
                trans.sa_session.add(workflow, stored_workflow)
                trans.sa_session.flush()

            if 'hidden' in workflow_dict and stored_workflow.hidden != workflow_dict['hidden']:
                stored_workflow.hidden = workflow_dict['hidden']
                trans.sa_session.flush()

            if 'published' in workflow_dict and stored_workflow.published != workflow_dict['published']:
                stored_workflow.published = workflow_dict['published']
                trans.sa_session.flush()

            if 'annotation' in workflow_dict and not steps_updated:
                newAnnotation = sanitize_html(workflow_dict['annotation'])
                self.add_item_annotation(trans.sa_session, trans.user, stored_workflow, newAnnotation)
                trans.sa_session.flush()

            if 'menu_entry' in workflow_dict or 'show_in_tool_panel' in workflow_dict:
                if workflow_dict.get('menu_entry') or workflow_dict.get('show_in_tool_panel'):
                    workflow_ids = [wf.stored_workflow_id for wf in trans.user.stored_workflow_menu_entries]
                    if trans.security.decode_id(id) not in workflow_ids:
                        menuEntry = model.StoredWorkflowMenuEntry()
                        menuEntry.stored_workflow = stored_workflow
                        trans.user.stored_workflow_menu_entries.append(menuEntry)
                else:
                    # remove if in list
                    entries = {x.stored_workflow_id: x for x in trans.user.stored_workflow_menu_entries}
                    if trans.security.decode_id(id) in entries:
                        trans.user.stored_workflow_menu_entries.remove(entries[trans.security.decode_id(id)])
            # set tags
            if 'tags' in workflow_dict:
                trans.app.tag_handler.set_tags_from_list(user=trans.user, item=stored_workflow, new_tags_list=workflow_dict['tags'])

            if 'steps' in workflow_dict:
                try:
                    workflow_update_options = WorkflowUpdateOptions(**payload)
                    workflow, errors = self.workflow_contents_manager.update_workflow_from_raw_description(
                        trans,
                        stored_workflow,
                        raw_workflow_description,
                        workflow_update_options,
                    )
                except MissingToolsException:
                    raise exceptions.MessageException("This workflow contains missing tools. It cannot be saved until they have been removed from the workflow or installed.")

        else:
            message = "Updating workflow requires dictionary containing 'workflow' attribute with new JSON description."
            raise exceptions.RequestParameterInvalidException(message)
        return self.workflow_contents_manager.workflow_to_dict(trans, stored_workflow, style="instance")

    @expose_api
    def refactor(self, trans, id, payload, **kwds):
        """
        * PUT /api/workflows/{id}/refactor
            updates the workflow stored with ``id``

        :type   id:      str
        :param  id:      the encoded id of the workflow to update
        :param  instance:                 true if fetch by Workflow ID instead of StoredWorkflow id, false
                                          by default.
        :type   instance:                 boolean
        :type   payload: dict
        :param  payload: a dictionary containing list of actions to apply.
        :rtype:     dict
        :returns:   serialized version of the workflow
        """
        stored_workflow = self.__get_stored_workflow(trans, id, **kwds)
        refactor_request = RefactorRequest(**payload)
        return self.workflow_contents_manager.refactor(
            trans, stored_workflow, refactor_request
        )

    @expose_api
    def build_module(self, trans: GalaxyWebTransaction, payload=None):
        """
        POST /api/workflows/build_module
        Builds module models for the workflow editor.
        """
        if payload is None:
            payload = {}
        inputs = payload.get('inputs', {})
        trans.workflow_building_mode = workflow_building_modes.ENABLED
        module = module_factory.from_dict(trans, payload, from_tool_form=True)
        if 'tool_state' not in payload:
            module_state: Dict[str, Any] = {}
            populate_state(trans, module.get_inputs(), inputs, module_state, check=False)
            module.recover_state(module_state, from_tool_form=True)
        return {
            'label': inputs.get('__label', ''),
            'annotation': inputs.get('__annotation', ''),
            'name': module.get_name(),
            'tool_state': module.get_state(),
            'content_id': module.get_content_id(),
            'inputs': module.get_all_inputs(connectable_only=True),
            'outputs': module.get_all_outputs(),
            'config_form': module.get_config_form(),
            'post_job_actions': module.get_post_job_actions(inputs)
        }

    @expose_api
    def get_tool_predictions(self, trans: ProvidesUserContext, payload, **kwd):
        """
        POST /api/workflows/get_tool_predictions

        Fetch predicted tools for a workflow

        :type   payload: dict
        :param  payload:

            a dictionary containing two parameters
            'tool_sequence' - comma separated sequence of tool ids
            'remote_model_url' - (optional) path to the deep learning model
        """
        remote_model_url = payload.get('remote_model_url', trans.app.config.tool_recommendation_model_path)
        tool_sequence = payload.get('tool_sequence', "")
        if 'tool_sequence' not in payload or remote_model_url is None:
            return
        tool_sequence, recommended_tools = self.tool_recommendations.get_predictions(trans, tool_sequence, remote_model_url)
        return {
            "current_tool": tool_sequence,
            "predicted_data": recommended_tools
        }

    #
    # -- Helper methods --
    #
    def __api_import_from_archive(self, trans: GalaxyWebTransaction, archive_data, source=None, payload=None):
        payload = payload or {}
        try:
            data = json.loads(archive_data)
        except Exception:
            if "GalaxyWorkflow" in archive_data:
                data = {"yaml_content": archive_data}
            else:
                raise exceptions.MessageException("The data content does not appear to be a valid workflow.")
        if not data:
            raise exceptions.MessageException("The data content is missing.")
        raw_workflow_description = self.__normalize_workflow(trans, data)
        workflow_create_options = WorkflowCreateOptions(**payload)
        workflow, missing_tool_tups = self._workflow_from_dict(trans, raw_workflow_description, workflow_create_options, source=source)
        workflow_id = workflow.id
        workflow = workflow.latest_workflow

        response = {"message": f"Workflow '{escape(workflow.name)}' imported successfully.", "status": "success",
                    "id": trans.security.encode_id(workflow_id)}
        if workflow.has_errors:
            response["message"] = "Imported, but some steps in this workflow have validation errors."
            response["status"] = "error"
        elif len(workflow.steps) == 0:
            response["message"] = "Imported, but this workflow has no steps."
            response["status"] = "error"
        elif workflow.has_cycles:
            response["message"] = "Imported, but this workflow contains cycles."
            response["status"] = "error"
        return response

    def __api_import_new_workflow(self, trans: GalaxyWebTransaction, payload, **kwd):
        data = payload['workflow']
        raw_workflow_description = self.__normalize_workflow(trans, data)
        workflow_create_options = WorkflowCreateOptions(**payload)
        workflow, missing_tool_tups = self._workflow_from_dict(
            trans,
            raw_workflow_description,
            workflow_create_options,
        )
        # galaxy workflow newly created id
        workflow_id = workflow.id
        # api encoded, id
        encoded_id = trans.security.encode_id(workflow_id)
        item = workflow.to_dict(value_mapper={'id': trans.security.encode_id})
        item['annotations'] = [x.annotation for x in workflow.annotations]
        item['url'] = url_for('workflow', id=encoded_id)
        item['owner'] = workflow.user.username
        item['number_of_steps'] = len(workflow.latest_workflow.steps)
        return item

    def __normalize_workflow(self, trans: GalaxyWebTransaction, as_dict):
        return self.workflow_contents_manager.normalize_workflow_format(trans, as_dict)

    @expose_api
    def import_shared_workflow_deprecated(self, trans: GalaxyWebTransaction, payload, **kwd):
        """
        POST /api/workflows/import
        Import a workflow shared by other users.

        :param  workflow_id:      the workflow id (required)
        :type   workflow_id:      str

        :raises: exceptions.MessageException, exceptions.ObjectNotFound
        """
        # Pull parameters out of payload.
        workflow_id = payload.get('workflow_id', None)
        if workflow_id is None:
            raise exceptions.ObjectAttributeMissingException("Missing required parameter 'workflow_id'.")
        self.__api_import_shared_workflow(trans, workflow_id, payload)

    def __api_import_shared_workflow(self, trans: GalaxyWebTransaction, workflow_id, payload, **kwd):
        try:
            stored_workflow = self.get_stored_workflow(trans, workflow_id, check_ownership=False)
        except Exception:
            raise exceptions.ObjectNotFound(f"Malformed workflow id ( {workflow_id} ) specified.")
        if stored_workflow.importable is False:
            raise exceptions.ItemAccessibilityException('The owner of this workflow has disabled imports via this link.')
        elif stored_workflow.deleted:
            raise exceptions.ItemDeletionException("You can't import this workflow because it has been deleted.")
        imported_workflow = self._import_shared_workflow(trans, stored_workflow)
        item = imported_workflow.to_dict(value_mapper={'id': trans.security.encode_id})
        encoded_id = trans.security.encode_id(imported_workflow.id)
        item['url'] = url_for('workflow', id=encoded_id)
        return item

    @expose_api
    def invoke(self, trans: GalaxyWebTransaction, workflow_id, payload, **kwd):
        """
        POST /api/workflows/{encoded_workflow_id}/invocations

        Schedule the workflow specified by `workflow_id` to run.

        .. note:: This method takes the same arguments as
            :func:`galaxy.webapps.galaxy.api.workflows.WorkflowsAPIController.create` above.

        :raises: exceptions.MessageException, exceptions.RequestParameterInvalidException
        """
        # Get workflow + accessibility check.
        stored_workflow = self.__get_stored_accessible_workflow(trans, workflow_id, instance=kwd.get('instance', False))
        workflow = stored_workflow.latest_workflow
        run_configs = build_workflow_run_configs(trans, workflow, payload)
        is_batch = payload.get('batch')
        if not is_batch and len(run_configs) != 1:
            raise exceptions.RequestParameterInvalidException("Must specify 'batch' to use batch parameters.")

        require_exact_tool_versions = util.string_as_bool(payload.get("require_exact_tool_versions", "true"))
        tools = self.workflow_contents_manager.get_all_tools(workflow)
        missing_tools = [
            tool
            for tool in tools
            if not self.app.toolbox.has_tool(
                tool["tool_id"], tool_version=tool["tool_version"], exact=require_exact_tool_versions
            )
        ]
        if missing_tools:
            missing_tools_message = "Workflow was not invoked; the following required tools are not installed: "
            if require_exact_tool_versions:
                missing_tools_message += ", ".join(
                    [f"{tool['tool_id']} (version {tool['tool_version']})" for tool in missing_tools]
                )
            else:
                missing_tools_message += ", ".join([tool["tool_id"] for tool in missing_tools])
            raise exceptions.MessageException(missing_tools_message)

        invocations = []
        for run_config in run_configs:
            workflow_scheduler_id = payload.get('scheduler', None)
            # TODO: workflow scheduler hints
            work_request_params = dict(scheduler=workflow_scheduler_id)
            workflow_invocation = queue_invoke(
                trans=trans,
                workflow=workflow,
                workflow_run_config=run_config,
                request_params=work_request_params,
                flush=False,
            )
            invocations.append(workflow_invocation)

        trans.sa_session.flush()
        invocations = [self.encode_all_ids(trans, invocation.to_dict(), recursive=True) for invocation in invocations]

        if is_batch:
            return invocations
        else:
            return invocations[0]

    @expose_api
    def index_invocations(self, trans: GalaxyWebTransaction, **kwd):
        """
        GET /api/workflows/{workflow_id}/invocations
        GET /api/invocations

        Get the list of a user's workflow invocations. If workflow_id is supplied
        (either via URL or query parameter) it should be an encoded StoredWorkflow id
        and returned invocations will be restricted to that workflow. history_id (an encoded
        History id) can be used to further restrict the query. If neither a workflow_id or
        history_id is supplied, all the current user's workflow invocations will be indexed
        (as determined by the invocation being executed on one of the user's histories).

        :param  workflow_id:      an encoded stored workflow id to restrict query to
        :type   workflow_id:      str

        :param  instance:         true if fetch by Workflow ID instead of StoredWorkflow id, false
                                  by default.
        :type   instance:         boolean

        :param  history_id:       an encoded history id to restrict query to
        :type   history_id:       str

        :param  job_id:           an encoded job id to restrict query to
        :type   job_id:           str

        :param  user_id:          an encoded user id to restrict query to, must be own id if not admin user
        :type   user_id:          str

        :param  view:             level of detail to return per invocation 'element' or 'collection'.
        :type   view:             str

        :param  step_details:     If 'view' is 'element', also include details on individual steps.
        :type   step_details:     bool

        :raises: exceptions.MessageException, exceptions.ObjectNotFound
        """
        invocation_payload = InvocationIndexPayload(**kwd)
        workflow_id = invocation_payload.workflow_id
        if invocation_payload.instance:
            invocation_payload.workflow_id = self.__get_stored_workflow(trans, trans.security.encode_id(workflow_id), instance=True).id
        if invocation_payload.history_id:
            # access check
            self.history_manager.get_accessible(invocation_payload.history_id, trans.user, current_history=trans.history)
        if not trans.user_is_admin:
            # We restrict the query to the current users' invocations
            # Endpoint requires user login, so trans.user.id is never None
            # TODO: user_id should be optional!
            user_id = trans.user.id
            if invocation_payload.user_id and invocation_payload.user_id != user_id:
                raise exceptions.AdminRequiredException("Only admins can index the invocations of others")
        else:
            # Get all invocation if user is admin (and user_id is None)
            user_id = invocation_payload.user_id
        invocations, total_matches = self.workflow_manager.build_invocations_query(
            trans,
            stored_workflow_id=invocation_payload.workflow_id,
            history_id=invocation_payload.history_id,
            job_id=invocation_payload.job_id,
            user_id=user_id,
            include_terminal=invocation_payload.include_terminal,
            limit=invocation_payload.limit,
            offset=invocation_payload.offset,
            sort_by=invocation_payload.sort_by,
            sort_desc=invocation_payload.sort_desc,
        )
        trans.response.headers['total_matches'] = total_matches
        return self.workflow_manager.serialize_workflow_invocations(invocations, **kwd)

    @expose_api
    def show_invocation(self, trans: GalaxyWebTransaction, invocation_id, **kwd):
        """
        GET /api/workflows/{workflow_id}/invocations/{invocation_id}
        GET /api/invocations/{invocation_id}

        Get detailed description of workflow invocation

        :param  invocation_id:      the invocation id (required)
        :type   invocation_id:      str

        :param  step_details:       fetch details about individual invocation steps
                                    and populate a steps attribute in the resulting
                                    dictionary. Defaults to false.
        :type   step_details:       bool

        :param  legacy_job_state:   If step_details is true, and this is set to true
                                    populate the invocation step state with the job state
                                    instead of the invocation step state. This will also
                                    produce one step per job in mapping jobs to mimic the
                                    older behavior with respect to collections. Partially
                                    scheduled steps may provide incomplete information
                                    and the listed steps outputs are the mapped over
                                    step outputs but the individual job outputs
                                    when this is set - at least for now.
        :type   legacy_job_state:   bool

        :raises: exceptions.MessageException, exceptions.ObjectNotFound
        """
        decoded_workflow_invocation_id = self.decode_id(invocation_id)
        workflow_invocation = self.workflow_manager.get_invocation(trans, decoded_workflow_invocation_id, eager=True)
        if workflow_invocation:
            step_details = util.string_as_bool(kwd.pop('step_details', 'False'))
            legacy_job_state = util.string_as_bool(kwd.pop('legacy_job_state', 'False'))
            return self.__encode_invocation(workflow_invocation, step_details=step_details, legacy_job_state=legacy_job_state, **kwd)
        return None

    @expose_api
    def cancel_invocation(self, trans: ProvidesUserContext, invocation_id, **kwd):
        """
        DELETE /api/workflows/{workflow_id}/invocations/{invocation_id}
        DELETE /api/invocations/{invocation_id}
        Cancel the specified workflow invocation.

        :param  invocation_id:      the usage id (required)
        :type   invocation_id:      str

        :raises: exceptions.MessageException, exceptions.ObjectNotFound
        """
        decoded_workflow_invocation_id = self.decode_id(invocation_id)
        workflow_invocation = self.workflow_manager.cancel_invocation(trans, decoded_workflow_invocation_id)
        return self.__encode_invocation(workflow_invocation, **kwd)

    @expose_api
    def show_invocation_report(self, trans: GalaxyWebTransaction, invocation_id, **kwd):
        """
        GET /api/workflows/{workflow_id}/invocations/{invocation_id}/report
        GET /api/invocations/{invocation_id}/report

        Get JSON summarizing invocation for reporting.
        """
        kwd["format"] = "json"
        return self.workflow_manager.get_invocation_report(trans, invocation_id, **kwd)

    @expose_api_raw
    def show_invocation_report_pdf(self, trans: GalaxyWebTransaction, invocation_id, **kwd):
        """
        GET /api/workflows/{workflow_id}/invocations/{invocation_id}/report.pdf
        GET /api/invocations/{invocation_id}/report.pdf

        Get JSON summarizing invocation for reporting.
        """
        kwd["format"] = "pdf"
        trans.response.set_content_type("application/pdf")
        return self.workflow_manager.get_invocation_report(trans, invocation_id, **kwd)

    def _generate_invocation_bco(self, trans: GalaxyWebTransaction, invocation_id, **kwd):
        decoded_workflow_invocation_id = self.decode_id(invocation_id)
        workflow_invocation = self.workflow_manager.get_invocation(trans, decoded_workflow_invocation_id)
        history = workflow_invocation.history
        workflow = workflow_invocation.workflow
        stored_workflow = workflow.stored_workflow

        # pull in the user info from those who the history and workflow has been shared with
        contributing_users = [stored_workflow.user]

        # may want to extend this to have more reviewers.
        reviewing_users = [stored_workflow.user]
        encoded_workflow_id = trans.security.encode_id(stored_workflow.id)
        encoded_history_id = trans.security.encode_id(history.id)
        dict_workflow = json.loads(self.workflow_dict(trans, encoded_workflow_id))

        spec_version = kwd.get('spec_version', 'https://w3id.org/ieee/ieee-2791-schema/2791object.json')

        for i, w in enumerate(reversed(stored_workflow.workflows)):
            if workflow == w:
                current_version = i

        contributors = []
        for contributing_user in contributing_users:
            contributor = {
                'orcid': kwd.get('xref', []),
                'name': contributing_user.username,
                'affiliation': "",
                'contribution': ['authoredBy'],
                'email': contributing_user.email,
            }
            contributors.append(contributor)

        reviewers = []
        for reviewer in reviewing_users:
            reviewer = {
                'status': 'approved',
                'reviewer_comment': '',
                'date': workflow_invocation.update_time.isoformat(),
                'reviewer': {
                    'orcid': kwd.get('orcid', []),
                    'name': contributing_user.username,
                    'affiliation': "",
                    'contribution': 'curatedBy',
                    'email': contributing_user.email
                }
            }
            reviewers.append(reviewer)

        provenance_domain = {
            'name': workflow.name,
            'version': current_version,
            'review': reviewers,
            'derived_from': url_for('workflow', id=encoded_workflow_id, qualified=True),
            'created': workflow_invocation.create_time.isoformat(),
            'modified': workflow_invocation.update_time.isoformat(),
            'contributors': contributors,
            'license': 'https://spdx.org/licenses/CC-BY-4.0.html',
        }

        keywords = []
        for tag in stored_workflow.tags:
            keywords.append(tag.user_tname)
        for tag in history.tags:
            if tag.user_tname not in keywords:
                keywords.append(tag.user_tname)

        metrics = {}
        tools, input_subdomain, output_subdomain, pipeline_steps, software_prerequisites = [], [], [], [], []
        for step in workflow_invocation.steps:
            if step.workflow_step.type == 'tool':
                workflow_outputs_list, output_list, input_list = set(), [], []
                for wo in step.workflow_step.workflow_outputs:
                    workflow_outputs_list.add(wo.output_name)
                for job in step.jobs:
                    metrics[i] = summarize_job_metrics(trans, job)
                    for job_input in job.input_datasets:
                        if hasattr(job_input.dataset, 'dataset_id'):
                            encoded_dataset_id = trans.security.encode_id(job_input.dataset.dataset_id)
                            input_obj = {
                                # TODO: that should maybe be a step prefix + element identifier where appropriate.
                                'filename': job_input.dataset.name,
                                'uri': url_for('history_content', history_id=encoded_history_id, id=encoded_dataset_id, qualified=True),
                                'access_time': job_input.dataset.create_time.isoformat(),
                            }
                            input_list.append(input_obj)

                    for job_output in job.output_datasets:
                        if hasattr(job_output.dataset, 'dataset_id'):
                            encoded_dataset_id = trans.security.encode_id(job_output.dataset.dataset_id)
                            output_obj = {
                                'filename': job_output.dataset.name,
                                'uri': url_for('history_content', history_id=encoded_history_id, id=encoded_dataset_id, qualified=True),
                                'access_time': job_output.dataset.create_time.isoformat(),
                            }
                            output_list.append(output_obj)

                            if job_output.name in workflow_outputs_list:
                                output = {
                                    'mediatype': job_output.dataset.extension,
                                    'uri': {
                                        'filename': job_output.dataset.name,
                                        'uri': url_for('history_content', history_id=encoded_history_id, id=encoded_dataset_id, qualified=True),
                                        'access_time': job_output.dataset.create_time.isoformat(),
                                    }
                                }
                                output_subdomain.append(output)
                workflow_step = step.workflow_step
                step_index = workflow_step.order_index
                current_step = dict_workflow['steps'][str(step_index)]
                pipeline_step = {
                    'step_number': step_index,
                    'name': current_step['name'],
                    'description': current_step['annotation'],
                    'version': current_step['tool_version'],
                    'prerequisite': kwd.get('prerequisite', []),
                    'input_list': input_list,
                    'output_list': output_list
                }
                pipeline_steps.append(pipeline_step)
                try:
                    software_prerequisite = {
                        'name': current_step['content_id'],
                        'version': current_step['tool_version'],
                        'uri': {
                            'uri': current_step['content_id'],
                            'access_time': current_step['uuid']
                        }
                    }
                    if software_prerequisite['uri']['uri'] not in tools:
                        software_prerequisites.append(software_prerequisite)
                        tools.append(software_prerequisite['uri']['uri'])
                except Exception:
                    continue

            if step.workflow_step.type == 'data_input' and step.output_datasets:
                for output_assoc in step.output_datasets:
                    encoded_dataset_id = trans.security.encode_id(output_assoc.dataset_id)
                    input_obj = {
                        'filename': step.workflow_step.label,
                        'uri': url_for('history_content', history_id=encoded_history_id, id=encoded_dataset_id, qualified=True),
                        'access_time': step.workflow_step.update_time.isoformat(),
                    }
                    input_subdomain.append(input_obj)

            if step.workflow_step.type == 'data_collection_input' and step.output_dataset_collections:
                for output_dataset_collection_association in step.output_dataset_collections:
                    encoded_dataset_id = trans.security.encode_id(output_dataset_collection_association.dataset_collection_id)
                    input_obj = {
                        'filename': step.workflow_step.label,
                        'uri': url_for('history_content', history_id=encoded_history_id, id=encoded_dataset_id, type="dataset_collection", qualified=True),
                        'access_time': step.workflow_step.update_time.isoformat(),
                    }
                    input_subdomain.append(input_obj)

        usability_domain = []
        for a in stored_workflow.annotations:
            usability_domain.append(a.annotation)
        for h in history.annotations:
            usability_domain.append(h.annotation)

        parametric_domain = []
        for inv_step in workflow_invocation.steps:
            try:
                for k, v in inv_step.workflow_step.tool_inputs.items():
                    param, value, step = k, v, inv_step.workflow_step.order_index
                    parametric_domain.append({'param': param, 'value': value, 'step': step})
            except Exception:
                continue

        execution_domain = {
            'script_access_type': 'a_galaxy_workflow',
            'script': [url_for('workflows', encoded_workflow_id=encoded_workflow_id, qualified=True)],
            'script_driver': 'Galaxy',
            'software_prerequisites': software_prerequisites,
            'external_data_endpoints': [
                {
                    'name': 'Access to Galaxy',
                    'url': url_for('/', qualified=True)
                },
                kwd.get('external_data_endpoints')
            ],
            'environment_variables': kwd.get('environment_variables', {})
        }

        extension = [
            {
                'extension_schema': 'https://raw.githubusercontent.com/biocompute-objects/extension_domain/6d2cd8482e6075746984662edcf78b57d3d38065/galaxy/galaxy_extension.json',
                'galaxy_extension': {
                    'galaxy_url': url_for('/', qualified=True),
                    'galaxy_version': VERSION,
                    # TODO:
                    # 'aws_estimate': aws_estimate,
                    # 'job_metrics': metrics
                }
            }
        ]

        error_domain = {
            'empirical_error': kwd.get('empirical_error', []),
            'algorithmic_error': kwd.get('algorithmic_error', [])
        }

        bco_dict = {
            'provenance_domain': provenance_domain,
            'usability_domain': usability_domain,
            'extension_domain': extension,
            'description_domain': {
                'keywords': keywords,
                'xref': kwd.get('xref', []),
                'platform': ['Galaxy'],
                'pipeline_steps': pipeline_steps,
            },
            'execution_domain': execution_domain,
            'parametric_domain': parametric_domain,
            'io_domain': {
                'input_subdomain': input_subdomain,
                'output_subdomain': output_subdomain,
            },
            'error_domain': error_domain,
        }
        # Generate etag from the BCO excluding object_id and spec_version, as
        # specified in https://github.com/biocompute-objects/BCO_Specification/blob/main/docs/top-level.md#203-etag-etag
        etag = hashlib.sha256(json.dumps(bco_dict, sort_keys=True).encode()).hexdigest()
        bco_dict.update({
            'object_id': url_for(controller=f"api/invocations/{invocation_id}", action='biocompute', qualified=True),
            'spec_version': spec_version,
            'etag': etag,
        })
        return bco_dict

    @expose_api
    def export_invocation_bco(self, trans: GalaxyWebTransaction, invocation_id, **kwd):
        '''
        GET /api/invocations/{invocations_id}/biocompute

        Return a BioCompute Object for the workflow invocation.

        The BioCompute Object endpoints are in beta - important details such
        as how inputs and outputs are represented, how the workflow is encoded,
        and how author and version information is encoded, and how URLs are
        generated will very likely change in important ways over time.
        '''
        return self._generate_invocation_bco(trans, invocation_id, **kwd)

    @expose_api_raw
    def download_invocation_bco(self, trans: GalaxyWebTransaction, invocation_id, **kwd):
        """
        GET /api/invocations/{invocations_id}/biocompute/download

        Returns a selected BioCompute Object as a file for download (HTTP
        headers configured with filename and such).

        The BioCompute Object endpoints are in beta - important details such
        as how inputs and outputs are represented, how the workflow is encoded,
        and how author and version information is encoded, and how URLs are
        generated will very likely change in important ways over time.
        """
        ret_dict = self._generate_invocation_bco(trans, invocation_id, **kwd)
        trans.response.headers["Content-Disposition"] = f'attachment; filename="bco_{invocation_id}.json"'
        trans.response.set_content_type("application/json")
        return format_return_as_json(ret_dict, pretty=True)

    @expose_api
    def invocation_step(self, trans, invocation_id, step_id, **kwd):
        """
        GET /api/workflows/{workflow_id}/invocations/{invocation_id}/steps/{step_id}
        GET /api/invocations/{invocation_id}/steps/{step_id}

        :param  invocation_id:      the invocation id (required)
        :type   invocation_id:      str

        :param  step_id:      encoded id of the WorkflowInvocationStep (required)
        :type   step_id:      str

        :param  payload:       payload containing update action information
                               for running workflow.

        :raises: exceptions.MessageException, exceptions.ObjectNotFound
        """
        decoded_invocation_step_id = self.decode_id(step_id)
        invocation_step = self.workflow_manager.get_invocation_step(
            trans,
            decoded_invocation_step_id
        )
        return self.__encode_invocation_step(trans, invocation_step)

    @expose_api_anonymous_and_sessionless
    def invocation_step_jobs_summary(self, trans: GalaxyWebTransaction, invocation_id, **kwd):
        """
        GET /api/workflows/{workflow_id}/invocations/{invocation_id}/step_jobs_summary
        GET /api/invocations/{invocation_id}/step_jobs_summary

        return job state summary info aggregated across per step of the workflow invocation

        Warning: We allow anyone to fetch job state information about any object they
        can guess an encoded ID for - it isn't considered protected data. This keeps
        polling IDs as part of state calculation for large histories and collections as
        efficient as possible.

        :param  invocation_id:    the invocation id (required)
        :type   invocation_id:    str

        :rtype:     dict[]
        :returns:   an array of job summary object dictionaries for each step
        """
        decoded_invocation_id = self.decode_id(invocation_id)
        ids = []
        types = []
        for (job_source_type, job_source_id, _) in invocation_job_source_iter(trans.sa_session, decoded_invocation_id):
            ids.append(job_source_id)
            types.append(job_source_type)
        return [self.encode_all_ids(trans, s) for s in fetch_job_states(trans.sa_session, ids, types)]

    @expose_api_anonymous_and_sessionless
    def invocation_jobs_summary(self, trans: GalaxyWebTransaction, invocation_id, **kwd):
        """
        GET /api/workflows/{workflow_id}/invocations/{invocation_id}/jobs_summary
        GET /api/invocations/{invocation_id}/jobs_summary

        return job state summary info aggregated across all current jobs of workflow invocation

        Warning: We allow anyone to fetch job state information about any object they
        can guess an encoded ID for - it isn't considered protected data. This keeps
        polling IDs as part of state calculation for large histories and collections as
        efficient as possible.

        :param  invocation_id:    the invocation id (required)
        :type   invocation_id:    str

        :rtype:     dict
        :returns:   a job summary object merged for all steps in workflow invocation
        """
        ids = [self.decode_id(invocation_id)]
        types = ["WorkflowInvocation"]
        return [self.encode_all_ids(trans, s) for s in fetch_job_states(trans.sa_session, ids, types)][0]

    @expose_api
    def update_invocation_step(self, trans: GalaxyWebTransaction, invocation_id, step_id, payload, **kwd):
        """
        PUT /api/workflows/{workflow_id}/invocations/{invocation_id}/steps/{step_id}
        PUT /api/invocations/{invocation_id}/steps/{step_id}

        Update state of running workflow step invocation - still very nebulous
        but this would be for stuff like confirming paused steps can proceed
        etc....

        :param  invocation_id:      the usage id (required)
        :type   invocation_id:      str

        :param  step_id:      encoded id of the WorkflowInvocationStep (required)
        :type   step_id:      str

        :raises: exceptions.MessageException, exceptions.ObjectNotFound
        """
        decoded_invocation_step_id = self.decode_id(step_id)
        action = payload.get("action", None)

        invocation_step = self.workflow_manager.update_invocation_step(
            trans,
            decoded_invocation_step_id,
            action=action,
        )
        return self.__encode_invocation_step(trans, invocation_step)

    def _workflow_from_dict(self, trans, data, workflow_create_options, source=None):
        """Creates a workflow from a dict.

        Created workflow is stored in the database and returned.
        """
        publish = workflow_create_options.publish
        importable = workflow_create_options.is_importable
        if publish and not importable:
            raise exceptions.RequestParameterInvalidException("Published workflow must be importable.")

        workflow_contents_manager = self.app.workflow_contents_manager
        raw_workflow_description = workflow_contents_manager.ensure_raw_description(data)
        created_workflow = workflow_contents_manager.build_workflow_from_raw_description(
            trans,
            raw_workflow_description,
            workflow_create_options,
            source=source,
        )
        if importable:
            self._make_item_accessible(trans.sa_session, created_workflow.stored_workflow)
            trans.sa_session.flush()

        self._import_tools_if_needed(trans, workflow_create_options, raw_workflow_description)
        return created_workflow.stored_workflow, created_workflow.missing_tools

    def _import_tools_if_needed(self, trans, workflow_create_options, raw_workflow_description):
        if not workflow_create_options.import_tools:
            return

        if not trans.user_is_admin:
            raise exceptions.AdminRequiredException()

        data = raw_workflow_description.as_dict

        tools = {}
        for key in data['steps']:
            item = data['steps'][key]
            if item is not None:
                if 'tool_shed_repository' in item:
                    tool_shed_repository = item['tool_shed_repository']
                    if 'owner' in tool_shed_repository and 'changeset_revision' in tool_shed_repository and 'name' in tool_shed_repository and 'tool_shed' in tool_shed_repository:
                        toolstr = tool_shed_repository['owner'] \
                            + tool_shed_repository['changeset_revision'] \
                            + tool_shed_repository['name'] \
                            + tool_shed_repository['tool_shed']
                        tools[toolstr] = tool_shed_repository

        irm = InstallRepositoryManager(self.app)
        install_options = workflow_create_options.install_options
        for k in tools:
            item = tools[k]
            tool_shed_url = f"https://{item['tool_shed']}/"
            name = item['name']
            owner = item['owner']
            changeset_revision = item['changeset_revision']
            irm.install(tool_shed_url,
                        name,
                        owner,
                        changeset_revision,
                        install_options)

    def __encode_invocation_step(self, trans: ProvidesUserContext, invocation_step):
        return self.encode_all_ids(
            trans,
            invocation_step.to_dict('element'),
            True
        )

    def __get_stored_accessible_workflow(self, trans, workflow_id, **kwd):
        instance = util.string_as_bool(kwd.get("instance", "false"))
        return self.workflow_manager.get_stored_accessible_workflow(trans, workflow_id, by_stored_id=not instance)

    def __get_stored_workflow(self, trans, workflow_id, **kwd):
        instance = util.string_as_bool(kwd.get("instance", "false"))
        return self.workflow_manager.get_stored_workflow(trans, workflow_id, by_stored_id=not instance)

    def __encode_invocation(self, invocation, **kwd):
        return self.workflow_manager.serialize_workflow_invocation(invocation, **kwd)
