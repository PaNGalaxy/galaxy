"""This module describes the abstract interface for :class:`InstrumentPlugin`.

These are responsible for collecting and formatting a coherent set of metrics.
"""
import os.path
from abc import (
    ABCMeta,
    abstractmethod
)


from .. import formatting

INSTRUMENT_FILE_PREFIX = "__instrument"


class InstrumentPlugin(metaclass=ABCMeta):
    """Describes how to instrument job scripts and retrieve collected metrics."""
    formatter = formatting.JobMetricFormatter()

    @property
    @abstractmethod
    def plugin_type(self):
        """ Short string providing labelling this plugin """

    def pre_execute_instrument(self, job_directory):
        """ Optionally return one or more commands to instrument job. These
        commands will be executed on the compute server prior to the job
        running.
        """
        return None

    def post_execute_instrument(self, job_directory):
        """ Optionally return one or more commands to instrument job. These
        commands will be executed on the compute server after the tool defined
        command is ran.
        """
        return None

    @abstractmethod
    def job_properties(self, job_id, job_directory):
        """ Collect properties for this plugin from specified job directory.
        This method will run on the Galaxy server and can assume files created
        in job_directory with pre_execute_instrument and
        post_execute_instrument are available.
        """

    def _instrument_file_name(self, name):
        """ Provide a common pattern for naming files used by instrumentation
        plugins - to ease their staging out of remote job directories.
        """
        return f"{INSTRUMENT_FILE_PREFIX}_{self.plugin_type}_{name}"

    def _instrument_file_path(self, job_directory, name):
        return os.path.join(job_directory, self._instrument_file_name(name))
