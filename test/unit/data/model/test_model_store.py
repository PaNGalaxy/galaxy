"""Unit tests for importing and exporting data from model stores."""
import json
import os
import pathlib
import shutil
from tempfile import mkdtemp, NamedTemporaryFile

import pytest

from galaxy import model
from galaxy.model import store
from galaxy.model.metadata import MetadataTempFile
from galaxy.model.unittest_utils import GalaxyDataTestApp
from galaxy.objectstore.unittest_utils import Config as TestConfig
from galaxy.util.compression_utils import CompressedFile

TESTCASE_DIRECTORY = pathlib.Path(__file__).parent
TEST_PATH_1 = TESTCASE_DIRECTORY / '1.txt'
TEST_PATH_2 = TESTCASE_DIRECTORY / '2.bed'


def test_import_export_history():
    """Test a simple job import/export after decompressing an archive (like history import/export tool)."""
    app = _mock_app()

    u, h, d1, d2, j = _setup_simple_cat_job(app)

    imported_history = _import_export_history(app, h, export_files="copy")

    _assert_simple_cat_job_imported(imported_history)


def test_import_export_history_failed_job():
    """Test a simple job import/export, make sure state is maintained correctly."""
    app = _mock_app()

    u, h, d1, d2, j = _setup_simple_cat_job(app, state='error')

    imported_history = _import_export_history(app, h, export_files="copy")

    _assert_simple_cat_job_imported(imported_history, state='error')


def test_import_export_history_hidden_false_with_hidden_dataset():
    app = _mock_app()

    u, h, d1, d2, j = _setup_simple_cat_job(app)
    d2.visible = False
    app.model.session.flush()

    imported_history = _import_export_history(app, h, export_files="copy", include_hidden=False)
    assert d1.dataset.get_size() == imported_history.datasets[0].get_size()
    assert imported_history.datasets[1].get_size() == 0


def test_import_export_history_hidden_true_with_hidden_dataset():
    app = _mock_app()

    u, h, d1, d2, j = _setup_simple_cat_job(app)
    d2.visible = False
    app.model.session.flush()

    imported_history = _import_export_history(app, h, export_files="copy", include_hidden=True)
    assert d1.dataset.get_size() == imported_history.datasets[0].get_size()
    assert d2.dataset.get_size() == imported_history.datasets[1].get_size()


def test_import_export_bag_archive():
    """Test a simple job import/export using a BagIt archive."""
    dest_parent = mkdtemp()
    dest_export = os.path.join(dest_parent, "moo.tgz")

    app = _mock_app()

    u, h, d1, d2, j = _setup_simple_cat_job(app)

    with store.BagArchiveModelExportStore(dest_export, app=app, bag_archiver="tgz", export_files="copy") as export_store:
        export_store.export_history(h)

    model_store = store.BagArchiveImportModelStore(dest_export, app=app, user=u)
    with model_store.target_history(default_history=None) as imported_history:
        model_store.perform_import(imported_history)

    _assert_simple_cat_job_imported(imported_history)


def test_import_export_datasets():
    """Test a simple job import/export using a directory."""
    app, h, temp_directory, import_history = _setup_simple_export({"for_edit": False})
    u = h.user

    _perform_import_from_directory(temp_directory, app, u, import_history)

    datasets = import_history.datasets
    assert len(datasets) == 2
    imported_job = datasets[1].creating_job
    assert imported_job
    assert imported_job.output_datasets
    assert imported_job.output_datasets[0].dataset == datasets[1]

    assert imported_job.input_datasets
    assert imported_job.input_datasets[0].dataset == datasets[0]


def test_import_library_require_permissions():
    """Verify library creation (import) is off by default."""
    app = _mock_app()
    sa_session = app.model.context

    u = model.User(email="collection@example.com", password="password")

    library = model.Library(name="my library 1", description="my library description", synopsis="my synopsis")
    root_folder = model.LibraryFolder(name="my library 1", description='folder description')
    library.root_folder = root_folder
    sa_session.add_all((library, root_folder))
    sa_session.flush()

    temp_directory = mkdtemp()
    with store.DirectoryModelExportStore(temp_directory, app=app) as export_store:
        export_store.export_library(library)

    error_caught = False
    try:
        import_model_store = store.get_import_model_store_for_directory(temp_directory, app=app, user=u)
        import_model_store.perform_import()
    except AssertionError:
        # TODO: throw and catch a better exception...
        error_caught = True

    assert error_caught


def test_import_export_library():
    """Test basics of library, library folder, and library dataset import/export."""
    app = _mock_app()
    sa_session = app.model.context

    u = model.User(email="collection@example.com", password="password")

    library = model.Library(name="my library 1", description="my library description", synopsis="my synopsis")
    root_folder = model.LibraryFolder(name="my library 1", description='folder description')
    library.root_folder = root_folder
    sa_session.add_all((library, root_folder))
    sa_session.flush()

    subfolder = model.LibraryFolder(name="sub folder 1", description="sub folder")
    root_folder.add_folder(subfolder)
    sa_session.add(subfolder)

    ld = model.LibraryDataset(folder=root_folder, name="my name", info="my library dataset")
    ldda = model.LibraryDatasetDatasetAssociation(
        create_dataset=True, flush=False
    )
    ld.library_dataset_dataset_association = ldda
    root_folder.add_library_dataset(ld)

    sa_session.add(ld)
    sa_session.add(ldda)

    sa_session.flush()
    assert len(root_folder.datasets) == 1
    assert len(root_folder.folders) == 1

    temp_directory = mkdtemp()
    with store.DirectoryModelExportStore(temp_directory, app=app) as export_store:
        export_store.export_library(library)

    import_model_store = store.get_import_model_store_for_directory(temp_directory, app=app, user=u, import_options=store.ImportOptions(allow_library_creation=True))
    import_model_store.perform_import()

    all_libraries = sa_session.query(model.Library).all()
    assert len(all_libraries) == 2, len(all_libraries)
    all_lddas = sa_session.query(model.LibraryDatasetDatasetAssociation).all()
    assert len(all_lddas) == 2, len(all_lddas)

    new_library = [lib for lib in all_libraries if lib.id != library.id][0]
    assert new_library.name == "my library 1"
    assert new_library.description == "my library description"
    assert new_library.synopsis == "my synopsis"

    new_root = new_library.root_folder
    assert new_root
    assert new_root.name == "my library 1"

    assert len(new_root.folders) == 1
    assert len(new_root.datasets) == 1


def test_finalize_job_state():
    """Verify jobs are given finalized states on import."""
    app, h, temp_directory, import_history = _setup_simple_export({"for_edit": False})
    u = h.user

    with open(os.path.join(temp_directory, store.ATTRS_FILENAME_JOBS)) as f:
        job_attrs = json.load(f)

    for job in job_attrs:
        job["state"] = "queued"

    with open(os.path.join(temp_directory, store.ATTRS_FILENAME_JOBS), "w") as f:
        json.dump(job_attrs, f)

    _perform_import_from_directory(temp_directory, app, u, import_history)

    datasets = import_history.datasets
    assert len(datasets) == 2
    imported_job = datasets[1].creating_job
    assert imported_job
    assert imported_job.state == model.Job.states.ERROR


def test_import_traceback_handling():
    app, h, temp_directory, import_history = _setup_simple_export({"for_edit": False})
    u = h.user
    traceback_message = "Oh no, a traceback here!!!"

    with open(os.path.join(temp_directory, store.TRACEBACK), "w") as f:
        f.write(traceback_message)

    with pytest.raises(store.FileTracebackException) as exc:
        _perform_import_from_directory(temp_directory, app, u, import_history)
    assert exc.value.traceback == traceback_message


def test_import_export_edit_datasets():
    """Test modifying existing HDA and dataset metadata with import."""
    app, h, temp_directory, import_history = _setup_simple_export({"for_edit": True})
    u = h.user

    # Fabric editing metadata...
    datasets_metadata_path = os.path.join(temp_directory, store.ATTRS_FILENAME_DATASETS)
    with open(datasets_metadata_path) as f:
        datasets_metadata = json.load(f)

    datasets_metadata[0]["name"] = "my new name 0"
    datasets_metadata[1]["name"] = "my new name 1"

    assert "dataset" in datasets_metadata[0]
    datasets_metadata[0]["dataset"]["object_store_id"] = "foo1"

    with open(datasets_metadata_path, "w") as f:
        json.dump(datasets_metadata, f)

    _perform_import_from_directory(temp_directory, app, u, import_history, store.ImportOptions(allow_edit=True))

    datasets = import_history.datasets
    assert len(datasets) == 0

    d1 = h.datasets[0]
    d2 = h.datasets[1]

    assert d1.name == "my new name 0", d1.name
    assert d2.name == "my new name 1", d2.name
    assert d1.dataset.object_store_id == "foo1", d1.dataset.object_store_id


def test_import_export_edit_collection():
    """Test modifying existing collections with imports."""
    app = _mock_app()
    sa_session = app.model.context

    u = model.User(email="collection@example.com", password="password")
    h = model.History(name="Test History", user=u)

    c1 = model.DatasetCollection(collection_type="list", populated=False)
    hc1 = model.HistoryDatasetCollectionAssociation(history=h, hid=1, collection=c1, name="HistoryCollectionTest1")

    sa_session.add(hc1)
    sa_session.add(h)
    import_history = model.History(name="Test History for Import", user=u)
    sa_session.add(import_history)
    sa_session.flush()

    temp_directory = mkdtemp()
    with store.DirectoryModelExportStore(temp_directory, app=app, for_edit=True) as export_store:
        export_store.add_dataset_collection(hc1)

    # Fabric editing metadata for collection...
    collections_metadata_path = os.path.join(temp_directory, store.ATTRS_FILENAME_COLLECTIONS)
    datasets_metadata_path = os.path.join(temp_directory, store.ATTRS_FILENAME_DATASETS)
    with open(collections_metadata_path) as f:
        hdcas_metadata = json.load(f)

    assert len(hdcas_metadata) == 1
    hdca_metadata = hdcas_metadata[0]
    assert hdca_metadata
    assert "id" in hdca_metadata
    assert "collection" in hdca_metadata
    collection_metadata = hdca_metadata["collection"]
    assert "populated_state" in collection_metadata
    assert collection_metadata["populated_state"] == model.DatasetCollection.populated_states.NEW

    collection_metadata["populated_state"] = model.DatasetCollection.populated_states.OK

    d1 = model.HistoryDatasetAssociation(extension="txt", create_dataset=True, flush=False)
    d1.hid = 1
    d2 = model.HistoryDatasetAssociation(extension="txt", create_dataset=True, flush=False)
    d2.hid = 2
    serialization_options = model.SerializationOptions(for_edit=True)
    dataset_list = [d1.serialize(app.security, serialization_options),
                    d2.serialize(app.security, serialization_options)]

    dc = model.DatasetCollection(
        id=collection_metadata["id"],
        collection_type="list",
        element_count=2,
    )
    dc.populated_state = model.DatasetCollection.populated_states.OK
    dce1 = model.DatasetCollectionElement(
        element=d1,
        element_index=0,
        element_identifier="first",
    )
    dce2 = model.DatasetCollectionElement(
        element=d2,
        element_index=1,
        element_identifier="second",
    )
    dc.elements = [dce1, dce2]
    with open(datasets_metadata_path, "w") as datasets_f:
        json.dump(dataset_list, datasets_f)

    hdca_metadata["collection"] = dc.serialize(app.security, serialization_options)
    with open(collections_metadata_path, "w") as collections_f:
        json.dump(hdcas_metadata, collections_f)

    _perform_import_from_directory(temp_directory, app, u, import_history, store.ImportOptions(allow_edit=True))

    sa_session.refresh(c1)
    assert c1.populated_state == model.DatasetCollection.populated_states.OK, c1.populated_state
    assert len(c1.elements) == 2


def test_import_export_composite_datasets():
    app = _mock_app()
    sa_session = app.model.context

    u = model.User(email="collection@example.com", password="password")
    h = model.History(name="Test History", user=u)

    d1 = _create_datasets(sa_session, h, 1, extension="html")[0]
    d1.dataset.create_extra_files_path()
    sa_session.add_all((h, d1))
    sa_session.flush()

    primary = NamedTemporaryFile("w")
    primary.write("cool primary file")
    primary.flush()
    app.object_store.update_from_file(
        d1.dataset,
        file_name=primary.name,
        create=True,
        preserve_symlinks=True
    )

    composite1 = NamedTemporaryFile("w")
    composite1.write("cool composite file")
    composite1.flush()

    app.object_store.update_from_file(
        d1.dataset,
        extra_dir=os.path.normpath(os.path.join(d1.extra_files_path, "parent_dir")),
        alt_name="child_file",
        file_name=composite1.name,
        create=True,
        preserve_symlinks=True
    )

    temp_directory = mkdtemp()
    with store.DirectoryModelExportStore(temp_directory, app=app, export_files="copy") as export_store:
        export_store.add_dataset(d1)

    import_history = model.History(name="Test History for Import", user=u)
    sa_session.add(import_history)
    sa_session.flush()
    _perform_import_from_directory(temp_directory, app, u, import_history)
    assert len(import_history.datasets) == 1
    import_dataset = import_history.datasets[0]
    root_extra_files_path = import_dataset.extra_files_path
    assert len(os.listdir(root_extra_files_path)) == 1
    assert os.listdir(root_extra_files_path)[0] == "parent_dir"
    composite_sub_dir = os.path.join(root_extra_files_path, "parent_dir")
    child_files = os.listdir(composite_sub_dir)
    assert len(child_files) == 1
    with open(os.path.join(composite_sub_dir, child_files[0])) as f:
        contents = f.read()
        assert contents == "cool composite file"


def test_edit_metadata_files():
    app = _mock_app(store_by="uuid")
    sa_session = app.model.context

    u = model.User(email="collection@example.com", password="password")
    h = model.History(name="Test History", user=u)

    d1 = _create_datasets(sa_session, h, 1, extension="bam")[0]
    sa_session.add_all((h, d1))
    sa_session.flush()
    index = NamedTemporaryFile("w")
    index.write("cool bam index")
    metadata_dict = {"bam_index": MetadataTempFile.from_JSON({"kwds": {}, "filename": index.name})}
    d1.metadata.from_JSON_dict(json_dict=metadata_dict)
    assert d1.metadata.bam_index
    assert isinstance(d1.metadata.bam_index, model.MetadataFile)

    temp_directory = mkdtemp()
    with store.DirectoryModelExportStore(temp_directory, app=app, for_edit=True, strip_metadata_files=False) as export_store:
        export_store.add_dataset(d1)

    import_history = model.History(name="Test History for Import", user=u)
    sa_session.add(import_history)
    sa_session.flush()
    _perform_import_from_directory(temp_directory, app, u, import_history, store.ImportOptions(allow_edit=True))


def test_sessionless_import_edit_datasets():
    app, h, temp_directory, import_history = _setup_simple_export({"for_edit": True})
    # Create a model store without a session and import it.
    import_model_store = store.get_import_model_store_for_directory(temp_directory, import_options=store.ImportOptions(allow_dataset_object_edit=True, allow_edit=True))
    import_model_store.perform_import()
    # Not using app.sa_session but a session mock that has a query/find pattern emulating usage
    # of real sa_session.
    d1 = import_model_store.sa_session.query(model.HistoryDatasetAssociation).find(h.datasets[0].id)
    d2 = import_model_store.sa_session.query(model.HistoryDatasetAssociation).find(h.datasets[1].id)
    assert d1 is not None
    assert d2 is not None


def test_import_datasets_with_ids_fails_if_not_editing_models():
    app, h, temp_directory, import_history = _setup_simple_export({"for_edit": True})
    u = h.user

    caught = None
    try:
        _perform_import_from_directory(temp_directory, app, u, import_history, store.ImportOptions(allow_edit=False))
    except AssertionError as e:
        # TODO: catch a better exception
        caught = e
    assert caught


def _setup_simple_export(export_kwds):
    app = _mock_app()

    u, h, d1, d2, j = _setup_simple_cat_job(app)

    sa_session = app.model.context

    import_history = model.History(name="Test History for Import", user=u)
    sa_session.add(import_history)
    sa_session.flush()

    temp_directory = mkdtemp()
    with store.DirectoryModelExportStore(temp_directory, app=app, **export_kwds) as export_store:
        export_store.add_dataset(d1)
        export_store.add_dataset(d2)

    return app, h, temp_directory, import_history


def _assert_simple_cat_job_imported(imported_history, state='ok'):
    assert imported_history.name == "imported from archive: Test History"

    datasets = imported_history.datasets
    assert len(datasets) == 2
    assert datasets[0].state == datasets[1].state == state
    imported_job = datasets[1].creating_job
    assert imported_job
    assert imported_job.state == state
    assert imported_job.output_datasets
    assert imported_job.output_datasets[0].dataset == datasets[1]

    assert imported_job.input_datasets
    assert imported_job.input_datasets[0].dataset == datasets[0]

    with open(datasets[0].file_name) as f:
        assert f.read().startswith("chr1    4225    19670")
    with open(datasets[1].file_name) as f:
        assert f.read().startswith("chr1\t147962192\t147962580\tNM_005997_cds_0_0_chr1_147962193_r\t0\t-")


def _setup_simple_cat_job(app, state='ok'):
    sa_session = app.model.context

    u = model.User(email="collection@example.com", password="password")
    h = model.History(name="Test History", user=u)

    d1, d2 = _create_datasets(sa_session, h, 2)
    d1.state = d2.state = state

    j = model.Job()
    j.user = u
    j.tool_id = "cat1"
    j.state = state

    j.add_input_dataset("input1", d1)
    j.add_output_dataset("out_file1", d2)

    sa_session.add_all((d1, d2, h, j))
    sa_session.flush()

    app.object_store.update_from_file(d1, file_name=TEST_PATH_1, create=True)
    app.object_store.update_from_file(d2, file_name=TEST_PATH_2, create=True)

    return u, h, d1, d2, j


def _import_export_history(app, h, dest_export=None, export_files=None, include_hidden=False):
    if dest_export is None:
        dest_parent = mkdtemp()
        dest_export = os.path.join(dest_parent, "moo.tgz")

    with store.TarModelExportStore(dest_export, app=app, export_files=export_files) as export_store:
        export_store.export_history(h, include_hidden=include_hidden)

    imported_history = import_archive(dest_export, app, h.user)
    assert imported_history
    return imported_history


def _perform_import_from_directory(directory, app, user, import_history, import_options=None):
    import_model_store = store.get_import_model_store_for_directory(directory, app=app, user=user, import_options=import_options)
    with import_model_store.target_history(default_history=import_history):
        import_model_store.perform_import(import_history)


def _create_datasets(sa_session, history, n, extension="txt"):
    return [model.HistoryDatasetAssociation(extension=extension, history=history, create_dataset=True, sa_session=sa_session, hid=i + 1) for i in range(n)]


def _mock_app(store_by="id"):
    app = GalaxyDataTestApp()
    test_object_store_config = TestConfig(store_by=store_by)
    app.object_store = test_object_store_config.object_store
    app.model.Dataset.object_store = app.object_store
    return app


class Options:
    is_url = False
    is_file = True
    is_b64encoded = False


def import_archive(archive_path, app, user):
    dest_parent = mkdtemp()
    dest_dir = CompressedFile(archive_path).extract(dest_parent)

    new_history = None
    model_store = store.get_import_model_store_for_directory(dest_dir, app=app, user=user)
    with model_store.target_history(default_history=None) as new_history:
        model_store.perform_import(new_history)

    shutil.rmtree(dest_parent)

    return new_history
