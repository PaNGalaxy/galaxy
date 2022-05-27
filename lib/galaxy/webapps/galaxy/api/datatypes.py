"""
API operations allowing clients to determine datatype supported by Galaxy.
"""
import logging
from typing import (
    Dict,
    List,
    Optional,
    Union,
)

from fastapi import Query

from galaxy.datatypes.registry import Registry
from galaxy.managers.datatypes import (
    DatatypeConverterList,
    DatatypeDetails,
    DatatypesCombinedMap,
    DatatypesMap,
    view_converters,
    view_edam_data,
    view_edam_formats,
    view_index,
    view_mapping,
    view_sniffers,
    view_types_and_mapping
)
from galaxy.util import asbool
from galaxy.web import expose_api_anonymous_and_sessionless
from . import (
    BaseGalaxyAPIController,
    depends,
    Router,
)

log = logging.getLogger(__name__)

router = Router(tags=['datatypes'])

ExtensionOnlyQueryParam: Optional[bool] = Query(
    default=True,
    title="Extension only",
    description="Whether to return only the datatype's extension rather than the datatype's details",
)

UploadOnlyQueryParam: Optional[bool] = Query(
    default=True,
    title="Upload only",
    description="Whether to return only datatypes which can be uploaded",
)


@router.cbv
class FastAPIDatatypes:
    datatypes_registry: Registry = depends(Registry)

    @router.get(
        '/api/datatypes',
        summary="Lists all available data types",
        response_description="List of data types",
    )
    async def index(
        self,
        extension_only: Optional[bool] = ExtensionOnlyQueryParam,
        upload_only: Optional[bool] = UploadOnlyQueryParam
    ) -> Union[List[DatatypeDetails], List[str]]:
        """Gets the list of all available data types."""
        return view_index(self.datatypes_registry, extension_only, upload_only)

    @router.get(
        '/api/datatypes/mapping',
        summary="Returns mappings for data types and their implementing classes",
        response_description="Dictionary to map data types with their classes"
    )
    async def mapping(self) -> DatatypesMap:
        """Gets mappings for data types."""
        return view_mapping(self.datatypes_registry)

    @router.get(
        '/api/datatypes/types_and_mapping',
        summary="Returns all the data types extensions and their mappings",
        response_description="Dictionary to map data types with their classes"
    )
    async def types_and_mapping(
        self,
        extension_only: Optional[bool] = ExtensionOnlyQueryParam,
        upload_only: Optional[bool] = UploadOnlyQueryParam
    ) -> DatatypesCombinedMap:
        """Combines the datatype information from (/api/datatypes) and the
        mapping information from (/api/datatypes/mapping) into a single
        response."""
        return DatatypesCombinedMap(
            datatypes=view_index(self.datatypes_registry, extension_only, upload_only),
            datatypes_mapping=view_mapping(self.datatypes_registry)
        )

    @router.get(
        '/api/datatypes/sniffers',
        summary="Returns the list of all installed sniffers",
        response_description="List of datatype sniffers"
    )
    async def sniffers(self) -> List[str]:
        """Gets the list of all installed data type sniffers."""
        return view_sniffers(self.datatypes_registry)

    @router.get(
        '/api/datatypes/converters',
        summary="Returns the list of all installed converters",
        response_description="List of all datatype converters"
    )
    async def converters(self) -> DatatypeConverterList:
        """Gets the list of all installed converters."""
        return view_converters(self.datatypes_registry)

    @router.get(
        '/api/datatypes/edam_formats',
        summary="Returns a dictionary/map of datatypes and EDAM formats",
        response_description="Dictionary/map of datatypes and EDAM formats"
    )
    async def edam_formats(self) -> Dict[str, str]:
        """Gets a map of datatypes and their corresponding EDAM formats."""
        return self.datatypes_registry.edam_formats

    @router.get(
        '/api/datatypes/edam_data',
        summary="Returns a dictionary/map of datatypes and EDAM data",
        response_description="Dictionary/map of datatypes and EDAM data"
    )
    async def edam_data(self) -> Dict[str, str]:
        """Gets a map of datatypes and their corresponding EDAM data."""
        return self.datatypes_registry.edam_data


class DatatypesController(BaseGalaxyAPIController):
    datatypes_registry: Registry = depends(Registry)

    @expose_api_anonymous_and_sessionless
    def index(self, trans, **kwd):
        """
        GET /api/datatypes
        Return an object containing upload datatypes.
        """
        extension_only = asbool(kwd.get('extension_only', True))
        upload_only = asbool(kwd.get('upload_only', True))
        return view_index(self.datatypes_registry, extension_only, upload_only)

    @expose_api_anonymous_and_sessionless
    def mapping(self, trans, **kwd):
        '''
        GET /api/datatypes/mapping
        Return a dictionary of class to class mappings.
        '''
        return view_mapping(self.datatypes_registry)

    @expose_api_anonymous_and_sessionless
    def types_and_mapping(self, trans, **kwd):
        """
        GET /api/datatypes/types_and_mapping

        Combine the datatype information from (/api/datatypes) and the
        mapping information from (/api/datatypes/mapping) into a single
        response.
        """
        extension_only = asbool(kwd.get('extension_only', True))
        upload_only = asbool(kwd.get('upload_only', True))
        return view_types_and_mapping(self.datatypes_registry, extension_only, upload_only)

    @expose_api_anonymous_and_sessionless
    def sniffers(self, trans, **kwd):
        '''
        GET /api/datatypes/sniffers
        Return a list of sniffers.
        '''
        return view_sniffers(self.datatypes_registry)

    @expose_api_anonymous_and_sessionless
    def converters(self, trans, **kwd):
        return view_converters(self.datatypes_registry)

    @expose_api_anonymous_and_sessionless
    def edam_formats(self, trans, **kwds):
        return view_edam_formats(self.datatypes_registry)

    @expose_api_anonymous_and_sessionless
    def edam_data(self, trans, **kwds):
        return view_edam_data(self.datatypes_registry)
