"""
Manager and Serializer for TS groups.
"""
import logging

from sqlalchemy import (
    false,
    true,
)
from sqlalchemy.orm.exc import (
    MultipleResultsFound,
    NoResultFound,
)

from galaxy.exceptions import (
    Conflict,
    InconsistentDatabase,
    InternalServerError,
    ItemAccessibilityException,
    ObjectNotFound,
    RequestParameterInvalidException,
)
from galaxy.model.base import transaction

log = logging.getLogger(__name__)


# =============================================================================
class GroupManager:
    """
    Interface/service object for interacting with TS groups.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get(self, trans, decoded_group_id=None, name=None):
        """
        Get the group from the DB based on its ID or name.

        :param  decoded_group_id:       decoded group id
        :type   decoded_group_id:       int

        :returns:   the requested group
        :rtype:     tool_shed.model.Group
        """
        if decoded_group_id is None and name is None:
            raise RequestParameterInvalidException("You must supply either ID or a name of the group.")

        name_query = trans.sa_session.query(trans.app.model.Group).filter(trans.app.model.Group.table.c.name == name)
        id_query = trans.sa_session.query(trans.app.model.Group).filter(
            trans.app.model.Group.table.c.id == decoded_group_id
        )

        try:
            group = id_query.one() if decoded_group_id else name_query.one()
        except MultipleResultsFound:
            raise InconsistentDatabase("Multiple groups found with the same identifier.")
        except NoResultFound:
            raise ObjectNotFound("No group found with the identifier provided.")
        except Exception:
            raise InternalServerError("Error loading from the database.")
        return group

    def create(self, trans, name, description=""):
        """
        Create a new group.
        """
        if not trans.user_is_admin:
            raise ItemAccessibilityException("Only administrators can create groups.")
        else:
            if self.get(trans, name=name):
                raise Conflict(f"Group with the given name already exists. Name: {str(name)}")
            # TODO add description field to the model
            group = trans.app.model.Group(name=name)
            trans.sa_session.add(group)
            with transaction(trans.sa_session):
                trans.sa_session.commit()
            return group

    def update(self, trans, group, name=None, description=None):
        """
        Update the given group
        """
        changed = False
        if not trans.user_is_admin:
            raise ItemAccessibilityException("Only administrators can update groups.")
        if group.deleted:
            raise RequestParameterInvalidException("You cannot modify a deleted group. Undelete it first.")
        if name is not None:
            group.name = name
            changed = True
        if description is not None:
            group.description = description
            changed = True
        if changed:
            trans.sa_session.add(group)
            with transaction(trans.sa_session):
                trans.sa_session.commit()
        return group

    def delete(self, trans, group, undelete=False):
        """
        Mark given group deleted/undeleted based on the flag.
        """
        if not trans.user_is_admin:
            raise ItemAccessibilityException("Only administrators can delete and undelete groups.")
        if undelete:
            group.deleted = False
        else:
            group.deleted = True
        trans.sa_session.add(group)
        with transaction(trans.sa_session):
            trans.sa_session.commit()
        return group

    def list(self, trans, deleted=False):
        """
        Return a list of groups from the DB.

        :returns: query that will emit all groups
        :rtype:   sqlalchemy query
        """
        is_admin = trans.user_is_admin
        query = trans.sa_session.query(trans.app.model.Group)
        if is_admin:
            if deleted is None:
                #  Flag is not specified, do not filter on it.
                pass
            elif deleted:
                query = query.filter(trans.app.model.Group.table.c.deleted == true())
            else:
                query = query.filter(trans.app.model.Group.table.c.deleted == false())
        else:
            query = query.filter(trans.app.model.Group.table.c.deleted == false())
        return query
