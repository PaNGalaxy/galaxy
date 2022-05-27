import os
from abc import (
    ABCMeta,
    abstractmethod,
)

from galaxy.job_execution.setup import JobIO
from galaxy.model import Job


class ComputeEnvironment(metaclass=ABCMeta):
    """ Definition of the job as it will be run on the (potentially) remote
    compute server.
    """

    @abstractmethod
    def output_names(self):
        """ Output unqualified filenames defined by job. """

    @abstractmethod
    def input_path_rewrite(self, dataset):
        """Input path for specified dataset."""

    @abstractmethod
    def output_path_rewrite(self, dataset):
        """Output path for specified dataset."""

    @abstractmethod
    def input_extra_files_rewrite(self, dataset):
        """Input extra files path rewrite for specified dataset."""

    @abstractmethod
    def output_extra_files_rewrite(self, dataset):
        """Output extra files path rewrite for specified dataset."""

    @abstractmethod
    def input_metadata_rewrite(self, dataset, metadata_value):
        """Input metadata path rewrite for specified dataset."""

    @abstractmethod
    def unstructured_path_rewrite(self, path):
        """Rewrite loc file paths, etc.."""

    @abstractmethod
    def working_directory(self):
        """ Job working directory (potentially remote) """

    @abstractmethod
    def config_directory(self):
        """ Directory containing config files (potentially remote) """

    @abstractmethod
    def env_config_directory(self):
        """Working directory (possibly as environment variable evaluation)."""

    @abstractmethod
    def sep(self):
        """ os.path.sep for the platform this job will execute in.
        """

    @abstractmethod
    def new_file_path(self):
        """ Absolute path to dump new files for this job on compute server. """

    @abstractmethod
    def tool_directory(self):
        """ Absolute path to tool files for this job on compute server. """

    @abstractmethod
    def version_path(self):
        """ Location of the version file for the underlying tool. """

    @abstractmethod
    def home_directory(self):
        """Home directory of target job - none if HOME should not be set."""

    @abstractmethod
    def tmp_directory(self):
        """Temp directory of target job - none if HOME should not be set."""

    @abstractmethod
    def galaxy_url(self):
        """URL to access Galaxy API from for this compute environment."""

    @abstractmethod
    def get_file_sources_dict(self):
        """Return file sources dict for current user."""


class SimpleComputeEnvironment:

    def config_directory(self):
        return os.path.join(self.working_directory(), "configs")  # type: ignore[attr-defined]

    def sep(self):
        return os.path.sep


class SharedComputeEnvironment(SimpleComputeEnvironment, ComputeEnvironment):
    """ Default ComputeEnvironment for job and task wrapper to pass
    to ToolEvaluator - valid when Galaxy and compute share all the relevant
    file systems.
    """

    def __init__(self, job_io: JobIO, job: Job):
        self.job_io = job_io
        self.job = job

    def get_file_sources_dict(self):
        return self.job_io.file_sources_dict

    def output_names(self):
        return self.job_io.get_output_basenames()

    def output_paths(self):
        return self.job_io.get_output_fnames()

    def input_path_rewrite(self, dataset):
        return self.job_io.get_input_path(dataset).false_path

    def output_path_rewrite(self, dataset):
        dataset_path = self.job_io.get_output_path(dataset)
        if hasattr(dataset_path, "false_path"):
            return dataset_path.false_path
        else:
            return dataset_path

    def input_extra_files_rewrite(self, dataset):
        return None

    def output_extra_files_rewrite(self, dataset):
        return None

    def input_metadata_rewrite(self, dataset, metadata_value):
        return None

    def unstructured_path_rewrite(self, path):
        return None

    def working_directory(self):
        return self.job_io.working_directory

    def env_config_directory(self):
        """Working directory (possibly as environment variable evaluation)."""
        return "$_GALAXY_JOB_DIR"

    def new_file_path(self):
        return self.job_io.new_file_path

    def version_path(self):
        return self.job_io.version_path

    def tool_directory(self):
        return self.job_io.tool_directory

    def home_directory(self):
        return self.job_io.home_directory

    def tmp_directory(self):
        return self.job_io.tmp_directory

    def galaxy_url(self):
        return self.job_io.galaxy_url
