import errno
import json
import logging
import os
from typing import Dict

from galaxy import util
from galaxy.structured_app import MinimalManagerApp
from galaxy.tools.data import TabularToolDataTable
from galaxy.util.template import fill_template

log = logging.getLogger(__name__)

SUPPORTED_DATA_TABLE_TYPES = (TabularToolDataTable)
VALUE_TRANSLATION_FUNCTIONS = dict(abspath=os.path.abspath)
DEFAULT_VALUE_TRANSLATION_TYPE = 'template'


class DataManagers:
    data_managers: Dict[str, 'DataManager']
    managed_data_tables: Dict[str, 'DataManager']

    def __init__(self, app: MinimalManagerApp, xml_filename=None):
        self.app = app
        self.data_managers = {}
        self.managed_data_tables = {}
        self.tool_path = None
        self._reload_count = 0
        self.filename = xml_filename or self.app.config.data_manager_config_file
        for filename in util.listify(self.filename):
            if not filename:
                continue
            self.load_from_xml(filename)
        if self.app.config.shed_data_manager_config_file:
            try:
                self.load_from_xml(self.app.config.shed_data_manager_config_file, store_tool_path=True)
            except OSError as exc:
                if exc.errno != errno.ENOENT or self.app.config.is_set('shed_data_manager_config_file'):
                    raise

    def load_from_xml(self, xml_filename, store_tool_path=True):
        try:
            tree = util.parse_xml(xml_filename)
        except OSError as e:
            if e.errno != errno.ENOENT or self.app.config.is_set('data_manager_config_file'):
                raise
            return  # default config option and it doesn't exist, which is fine
        except Exception as e:
            log.error(f'There was an error parsing your Data Manager config file "{xml_filename}": {e}')
            return  # we are not able to load any data managers
        root = tree.getroot()
        if root.tag != 'data_managers':
            log.error(f'A data managers configuration must have a "data_managers" tag as the root. "{root.tag}" is present')
            return
        if store_tool_path:
            tool_path = root.get('tool_path', None)
            if tool_path is None:
                tool_path = self.app.config.tool_path
            if not tool_path:
                tool_path = '.'
            self.tool_path = tool_path
        for data_manager_elem in root.findall('data_manager'):
            if not self.load_manager_from_elem(data_manager_elem, tool_path=self.tool_path):
                # Wasn't able to load manager, could happen when galaxy is managed by planemo.
                # Fall back to loading relative to the data_manager_conf.xml file
                tool_path = os.path.dirname(xml_filename)
                self.load_manager_from_elem(data_manager_elem, tool_path=tool_path)

    def load_manager_from_elem(self, data_manager_elem, tool_path=None, add_manager=True):
        try:
            data_manager = DataManager(self, data_manager_elem, tool_path=tool_path)
        except OSError as e:
            if e.errno == errno.ENOENT:
                # File does not exist
                return None
        except Exception:
            log.exception("Error loading data_manager")
            return None
        if add_manager:
            self.add_manager(data_manager)
        log.debug(f'Loaded Data Manager: {data_manager.id}')
        return data_manager

    def add_manager(self, data_manager):
        if data_manager.id in self.data_managers:
            log.warning(f"A data manager has been defined twice: {data_manager.id} ")
        self.data_managers[data_manager.id] = data_manager
        for data_table_name in data_manager.data_tables.keys():
            if data_table_name not in self.managed_data_tables:
                self.managed_data_tables[data_table_name] = []
            self.managed_data_tables[data_table_name].append(data_manager)

    def get_manager(self, *args, **kwds):
        return self.data_managers.get(*args, **kwds)

    def remove_manager(self, manager_ids):
        if not isinstance(manager_ids, list):
            manager_ids = [manager_ids]
        for manager_id in manager_ids:
            data_manager = self.get_manager(manager_id, None)
            if data_manager is not None:
                del self.data_managers[manager_id]
                # remove tool from toolbox
                if data_manager.tool:
                    self.app.toolbox.remove_tool_by_id(data_manager.tool.id)
                # determine if any data_tables are no longer tracked
                for data_table_name in data_manager.data_tables.keys():
                    remove_data_table_tracking = True
                    for other_data_manager in self.data_managers.values():
                        if data_table_name in other_data_manager.data_tables:
                            remove_data_table_tracking = False
                            break
                    if remove_data_table_tracking and data_table_name in self.managed_data_tables:
                        del self.managed_data_tables[data_table_name]


class DataManager:
    GUID_TYPE = 'data_manager'
    DEFAULT_VERSION = "0.0.1"

    def __init__(self, data_managers, elem=None, tool_path=None):
        self.data_managers = data_managers
        self.declared_id = None
        self.name = None
        self.description = None
        self.version = self.DEFAULT_VERSION
        self.guid = None
        self.tool = None
        self.data_tables = {}
        self.output_ref_by_data_table = {}
        self.move_by_data_table_column = {}
        self.value_translation_by_data_table_column = {}
        self.tool_shed_repository_info_dict = None
        self.undeclared_tables = False
        if elem is not None:
            self.load_from_element(elem, tool_path or self.data_managers.tool_path)

    def load_from_element(self, elem, tool_path):
        assert elem.tag == 'data_manager', f'A data manager configuration must have a "data_manager" tag as the root. "{elem.tag}" is present'
        self.declared_id = elem.get('id')
        self.guid = elem.get('guid')
        path = elem.get('tool_file')
        tool_shed_repository = None
        tool_guid = None

        if path is None:
            tool_elem = elem.find('tool')
            assert tool_elem is not None, f"Error loading tool for data manager. Make sure that a tool_file attribute or a tool tag set has been defined:\n{util.xml_to_string(elem)}"
            path = tool_elem.get("file")
            tool_guid = tool_elem.get("guid")
            # need to determine repository info so that dependencies will work correctly
            tool_shed_repository = self.data_managers.app.toolbox.get_tool_repository_from_xml_item(tool_elem, path)
            self.tool_shed_repository_info_dict = dict(tool_shed=tool_shed_repository.tool_shed,
                                                       name=tool_shed_repository.name,
                                                       owner=tool_shed_repository.owner,
                                                       installed_changeset_revision=tool_shed_repository.installed_changeset_revision)
            # use shed_conf_file to determine tool_path
            shed_conf_file = elem.get("shed_conf_file")
            if shed_conf_file:
                shed_conf = self.data_managers.app.toolbox.get_shed_config_dict_by_filename(shed_conf_file)
                if shed_conf:
                    tool_path = shed_conf.get("tool_path", tool_path)
        assert path is not None, f"A tool file path could not be determined:\n{util.xml_to_string(elem)}"
        self.load_tool(os.path.join(tool_path, path),
                       guid=tool_guid,
                       data_manager_id=self.id,
                       tool_shed_repository=tool_shed_repository)
        self.name = elem.get('name', self.tool.name)
        self.description = elem.get('description', self.tool.description)
        self.undeclared_tables = util.asbool(elem.get('undeclared_tables', self.undeclared_tables))
        self.version = elem.get('version', self.tool.version)

        for data_table_elem in elem.findall('data_table'):
            data_table_name = data_table_elem.get("name")
            assert data_table_name is not None, "A name is required for a data table entry"
            if data_table_name not in self.data_tables:
                self.data_tables[data_table_name] = {}
            output_elem = data_table_elem.find('output')
            if output_elem is not None:
                for column_elem in output_elem.findall('column'):
                    column_name = column_elem.get('name', None)
                    assert column_name is not None, "Name is required for column entry"
                    data_table_coumn_name = column_elem.get('data_table_name', column_name)
                    self.data_tables[data_table_name][data_table_coumn_name] = column_name
                    output_ref = column_elem.get('output_ref', None)
                    if output_ref is not None:
                        if data_table_name not in self.output_ref_by_data_table:
                            self.output_ref_by_data_table[data_table_name] = {}
                        self.output_ref_by_data_table[data_table_name][data_table_coumn_name] = output_ref
                    value_translation_elems = column_elem.findall('value_translation')
                    if value_translation_elems is not None:
                        for value_translation_elem in value_translation_elems:
                            value_translation = value_translation_elem.text
                            if value_translation is not None:
                                value_translation_type = value_translation_elem.get('type', DEFAULT_VALUE_TRANSLATION_TYPE)
                                if data_table_name not in self.value_translation_by_data_table_column:
                                    self.value_translation_by_data_table_column[data_table_name] = {}
                                if data_table_coumn_name not in self.value_translation_by_data_table_column[data_table_name]:
                                    self.value_translation_by_data_table_column[data_table_name][data_table_coumn_name] = []
                                if value_translation_type == 'function':
                                    if value_translation in VALUE_TRANSLATION_FUNCTIONS:
                                        value_translation = VALUE_TRANSLATION_FUNCTIONS[value_translation]
                                    else:
                                        raise ValueError(f"Unsupported value translation function: '{value_translation}'")
                                else:
                                    assert value_translation_type == DEFAULT_VALUE_TRANSLATION_TYPE, ValueError(f"Unsupported value translation type: '{value_translation_type}'")
                                self.value_translation_by_data_table_column[data_table_name][data_table_coumn_name].append(value_translation)

                    for move_elem in column_elem.findall('move'):
                        move_type = move_elem.get('type', 'directory')
                        relativize_symlinks = move_elem.get('relativize_symlinks', False)  # TODO: should we instead always relativize links?
                        source_elem = move_elem.find('source')
                        if source_elem is None:
                            source_base = None
                            source_value = ''
                        else:
                            source_base = source_elem.get('base', None)
                            source_value = source_elem.text
                        target_elem = move_elem.find('target')
                        if target_elem is None:
                            target_base = None
                            target_value = ''
                        else:
                            target_base = target_elem.get('base', None)
                            target_value = target_elem.text
                        if data_table_name not in self.move_by_data_table_column:
                            self.move_by_data_table_column[data_table_name] = {}
                        self.move_by_data_table_column[data_table_name][data_table_coumn_name] = \
                            dict(type=move_type,
                                 source_base=source_base,
                                 source_value=source_value,
                                 target_base=target_base,
                                 target_value=target_value,
                                 relativize_symlinks=relativize_symlinks)

    @property
    def id(self):
        return self.guid or self.declared_id  # if we have a guid, we will use that as the data_manager id

    def load_tool(self, tool_filename, guid=None, data_manager_id=None, tool_shed_repository_id=None, tool_shed_repository=None):
        toolbox = self.data_managers.app.toolbox
        tool = toolbox.load_hidden_tool(tool_filename,
                                        guid=guid,
                                        data_manager_id=data_manager_id,
                                        repository_id=tool_shed_repository_id,
                                        tool_shed_repository=tool_shed_repository,
                                        use_cached=True)
        self.data_managers.app.toolbox.data_manager_tools[tool.id] = tool
        self.tool = tool
        return tool

    def process_result(self, out_data):
        data_manager_dicts = {}
        data_manager_dict = {}
        # TODO: fix this merging below
        for output_name, output_dataset in out_data.items():
            try:
                output_dict = json.loads(open(output_dataset.file_name).read())
            except Exception as e:
                log.warning(f'Error reading DataManagerTool json for "{output_name}": {e}')
                continue
            data_manager_dicts[output_name] = output_dict
            for key, value in output_dict.items():
                if key not in data_manager_dict:
                    data_manager_dict[key] = {}
                data_manager_dict[key].update(value)
            data_manager_dict.update(output_dict)

        data_tables_dict = data_manager_dict.get('data_tables', {})
        for data_table_name in self.data_tables.keys():
            data_table_values = data_tables_dict.pop(data_table_name, None)
            if not data_table_values:
                log.warning(f'No values for data table "{data_table_name}" were returned by the data manager "{self.id}".')
                continue  # next data table
            data_table_remove_values = None
            if isinstance(data_table_values, dict):
                values_to_add = data_table_values.get('add')
                data_table_remove_values = data_table_values.get('remove')
                if values_to_add or data_table_remove_values:
                    # We don't have an old style data table definition
                    data_table_values = values_to_add

            data_table = self.data_managers.app.tool_data_tables.get(data_table_name, None)
            if data_table is None:
                log.error(f"The data manager \"{self.id}\" returned an unknown data table \"{data_table_name}\" with new entries \"{data_table_values}\". These entries will not be created. Please confirm that an entry for \"{data_table_name}\" exists in your \"tool_data_table_conf.xml\" file.")
                continue  # next table name
            if not isinstance(data_table, SUPPORTED_DATA_TABLE_TYPES):
                log.error(f'The data manager "{self.id}" returned an unsupported data table "{data_table_name}" with type "{type(data_table)}" with new entries "{data_table_values}". These entries will not be created. Please confirm that the data table is of a supported type ({SUPPORTED_DATA_TABLE_TYPES}).')
                continue  # next table name
            output_ref_values = {}
            if data_table_name in self.output_ref_by_data_table:
                for data_table_column, output_ref in self.output_ref_by_data_table[data_table_name].items():
                    output_ref_dataset = out_data.get(output_ref, None)
                    assert output_ref_dataset is not None, "Referenced output was not found."
                    output_ref_values[data_table_column] = output_ref_dataset

            if not isinstance(data_table_values, list):
                data_table_values = [data_table_values] if data_table_values else []
            if not isinstance(data_table_remove_values, list):
                data_table_remove_values = [data_table_remove_values] if data_table_remove_values else []
            for data_table_row in data_table_values:
                data_table_value = dict(**data_table_row)  # keep original values here
                for name in data_table_row.keys():  # FIXME: need to loop through here based upon order listed in data_manager config
                    if name in output_ref_values:
                        self.process_move(data_table_name, name, output_ref_values[name].extra_files_path, **data_table_value)
                        data_table_value[name] = self.process_value_translation(data_table_name, name, **data_table_value)
                data_table.add_entry(data_table_value, persist=True, entry_source=self)
            # Removes data table entries
            for data_table_row in data_table_remove_values:
                data_table_value = dict(**data_table_row)  # keep original values here
                data_table.remove_entry(list(data_table_value.values()))

            self.data_managers.app.queue_worker.send_control_task(
                'reload_tool_data_tables',
                noop_self=True,
                kwargs={'table_name': data_table_name}
            )
        if self.undeclared_tables and data_tables_dict:
            # We handle the data move, by just moving all the data out of the extra files path
            # moving a directory and the target already exists, we move the contents instead
            log.debug('Attempting to add entries for undeclared tables: %s.', ', '.join(data_tables_dict.keys()))
            for ref_file in out_data.values():
                if ref_file.extra_files_path_exists():
                    util.move_merge(ref_file.extra_files_path, self.data_managers.app.config.galaxy_data_manager_data_path)
            path_column_names = ['path']
            for data_table_name, data_table_values in data_tables_dict.items():
                data_table = self.data_managers.app.tool_data_tables.get(data_table_name, None)
                if not isinstance(data_table_values, list):
                    data_table_values = [data_table_values]
                for data_table_row in data_table_values:
                    data_table_value = dict(**data_table_row)  # keep original values here
                    for name, value in data_table_row.items():
                        if name in path_column_names:
                            data_table_value[name] = os.path.abspath(os.path.join(self.data_managers.app.config.galaxy_data_manager_data_path, value))
                    data_table.add_entry(data_table_value, persist=True, entry_source=self)
                self.data_managers.app.queue_worker.send_control_task(
                    'reload_tool_data_tables',
                    noop_self=True,
                    kwargs={'table_name': data_table_name}
                )
        else:
            for data_table_name, data_table_values in data_tables_dict.items():
                # tool returned extra data table entries, but data table was not declared in data manager
                # do not add these values, but do provide messages
                log.warning(f'The data manager "{self.id}" returned an undeclared data table "{data_table_name}" with new entries "{data_table_values}". These entries will not be created. Please confirm that an entry for "{data_table_name}" exists in your "{self.data_managers.filename}" file.')

    def process_move(self, data_table_name, column_name, source_base_path, relative_symlinks=False, **kwd):
        if data_table_name in self.move_by_data_table_column and column_name in self.move_by_data_table_column[data_table_name]:
            move_dict = self.move_by_data_table_column[data_table_name][column_name]
            source = move_dict['source_base']
            if source is None:
                source = source_base_path
            else:
                source = fill_template(source, GALAXY_DATA_MANAGER_DATA_PATH=self.data_managers.app.config.galaxy_data_manager_data_path, **kwd).strip()
            if move_dict['source_value']:
                source = os.path.join(source, fill_template(move_dict['source_value'], GALAXY_DATA_MANAGER_DATA_PATH=self.data_managers.app.config.galaxy_data_manager_data_path, **kwd).strip())
            target = move_dict['target_base']
            if target is None:
                target = self.data_managers.app.config.galaxy_data_manager_data_path
            else:
                target = fill_template(target, GALAXY_DATA_MANAGER_DATA_PATH=self.data_managers.app.config.galaxy_data_manager_data_path, **kwd).strip()
            if move_dict['target_value']:
                target = os.path.join(target, fill_template(move_dict['target_value'], GALAXY_DATA_MANAGER_DATA_PATH=self.data_managers.app.config.galaxy_data_manager_data_path, **kwd).strip())

            if move_dict['type'] == 'file':
                dirs = os.path.split(target)[0]
                try:
                    os.makedirs(dirs)
                except OSError as e:
                    if e.errno != errno.EEXIST:
                        raise e
            # moving a directory and the target already exists, we move the contents instead
            if os.path.exists(source):
                util.move_merge(source, target)

            if move_dict.get('relativize_symlinks', False):
                util.relativize_symlinks(target)

            return True
        return False

    def process_value_translation(self, data_table_name, column_name, **kwd):
        value = kwd.get(column_name)
        if data_table_name in self.value_translation_by_data_table_column and column_name in self.value_translation_by_data_table_column[data_table_name]:
            for value_translation in self.value_translation_by_data_table_column[data_table_name][column_name]:
                if isinstance(value_translation, str):
                    value = fill_template(value_translation, GALAXY_DATA_MANAGER_DATA_PATH=self.data_managers.app.config.galaxy_data_manager_data_path, **kwd).strip()
                else:
                    value = value_translation(value)
        return value

    def get_tool_shed_repository_info_dict(self):
        return self.tool_shed_repository_info_dict
