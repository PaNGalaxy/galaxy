from typing import (
    List,
    Optional,
    Union,
)

from sqlalchemy import (
    false,
    or_,
    select,
    true,
)

import galaxy.managers.base as managers_base
from galaxy import (
    exceptions as glx_exceptions,
    util,
)
from galaxy.managers import api_keys
from galaxy.managers.context import (
    ProvidesHistoryContext,
    ProvidesUserContext,
)
from galaxy.managers.users import (
    UserDeserializer,
    UserManager,
    UserSerializer,
)
from galaxy.model import User
from galaxy.queue_worker import send_local_control_task
from galaxy.quota import QuotaAgent
from galaxy.schema import APIKeyModel
from galaxy.schema.schema import (
    AnonUserModel,
    DetailedUserModel,
    FlexibleUserIdType,
    LimitedUserModel,
    UserModel,
)
from galaxy.security.idencoding import IdEncodingHelper
from galaxy.webapps.galaxy.services.base import (
    async_task_summary,
    ServiceBase,
)


class UsersService(ServiceBase):
    """Common interface/service logic for interactions with users in the context of the API.

    Provides the logic of the actions invoked by API controllers and uses type definitions
    and pydantic models to declare its parameters and return types.
    """

    def __init__(
        self,
        security: IdEncodingHelper,
        user_manager: UserManager,
        api_key_manager: api_keys.ApiKeyManager,
        user_serializer: UserSerializer,
        user_deserializer: UserDeserializer,
        quota_agent: QuotaAgent,
    ):
        super().__init__(security)
        self.user_manager = user_manager
        self.api_key_manager = api_key_manager
        self.user_serializer = user_serializer
        self.user_deserializer = user_deserializer
        self.quota_agent = quota_agent

    def recalculate_disk_usage(
        self,
        trans: ProvidesUserContext,
    ):
        if trans.anonymous:
            raise glx_exceptions.AuthenticationRequired("Only registered users can recalculate disk usage.")
        if trans.app.config.enable_celery_tasks:
            from galaxy.celery.tasks import recalculate_user_disk_usage

            result = recalculate_user_disk_usage.delay(task_user_id=getattr(trans.user, "id", None))
            return async_task_summary(result)
        else:
            send_local_control_task(
                trans.app,
                "recalculate_user_disk_usage",
                kwargs={
                    "user_id": trans.user.id,
                },
            )
            return None

    def get_api_key(self, trans: ProvidesUserContext, user_id: int) -> Optional[APIKeyModel]:
        """Returns the current API key or None if the user doesn't have any valid API key."""
        user = self.get_user(trans, user_id)
        api_key = self.api_key_manager.get_api_key(user)
        return APIKeyModel.construct(key=api_key.key, create_time=api_key.create_time) if api_key else None

    def get_or_create_api_key(self, trans: ProvidesUserContext, user_id: int) -> str:
        """Returns the current API key (as plain string) or creates a new one."""
        user = self.get_user(trans, user_id)
        return self.api_key_manager.get_or_create_api_key(user)

    def create_api_key(self, trans: ProvidesUserContext, user_id: int) -> APIKeyModel:
        """Creates a new API key for the given user"""
        user = self.get_user(trans, user_id)
        api_key = self.api_key_manager.create_api_key(user)
        result = APIKeyModel.construct(key=api_key.key, create_time=api_key.create_time)
        return result

    def delete_api_key(self, trans: ProvidesUserContext, user_id: int) -> None:
        """Deletes a particular API key"""
        user = self.get_user(trans, user_id)
        self.api_key_manager.delete_api_key(user)

    def get_user(self, trans: ProvidesUserContext, user_id):
        user = trans.user
        if trans.anonymous or (user and user.id != user_id and not trans.user_is_admin):
            raise glx_exceptions.InsufficientPermissionsException("Access denied.")
        user = self.user_manager.by_id(user_id)
        return user

    def _anon_user_api_value(self, trans: ProvidesHistoryContext):
        """Return data for an anonymous user, truncated to only usage and quota_percent"""
        if not trans.user and not trans.history:
            # Can't return info about this user, may not have a history yet.
            # return {}
            raise glx_exceptions.MessageException(err_msg="The user has no history, which should always be the case.")
        usage = self.quota_agent.get_usage(trans, history=trans.history)
        percent = self.quota_agent.get_percent(trans=trans, usage=usage)
        usage = usage or 0
        return {
            "total_disk_usage": int(usage),
            "nice_total_disk_usage": util.nice_size(usage),
            "quota_percent": percent,
        }

    def get_non_anonymous_user_full(
        self,
        trans: ProvidesUserContext,
        user_id: FlexibleUserIdType,
        deleted: bool,
    ) -> User:
        user = self.get_user_full(trans, user_id, deleted)
        if user is None:
            raise glx_exceptions.AuthenticationRequired(err_msg="You need to be logged in.")
        return user

    def get_user_full(
        self,
        trans: ProvidesUserContext,
        user_id: FlexibleUserIdType,
        deleted: bool,
    ) -> Optional[User]:
        try:
            # user is requesting data about themselves
            if user_id == "current":
                # ...and is anonymous - return usage and quota (if any)
                if not trans.user:
                    return None

                # ...and is logged in - return full
                else:
                    user = trans.user
            else:
                user = managers_base.get_object(
                    trans,
                    user_id,
                    "User",
                    deleted=deleted,
                )
            # check that the user is requesting themselves (and they aren't del'd) unless admin
            if not trans.user_is_admin:
                if trans.user != user or user.deleted:
                    raise glx_exceptions.RequestParameterInvalidException("Invalid user id specified")
            return user
        except glx_exceptions.MessageException:
            raise
        except Exception:
            raise glx_exceptions.RequestParameterInvalidException("Invalid user id specified")

    def show_user(
        self,
        trans: ProvidesHistoryContext,
        user_id: FlexibleUserIdType,
        deleted: bool,
    ) -> Union[DetailedUserModel, AnonUserModel]:
        user = self.get_user_full(trans=trans, deleted=deleted, user_id=user_id)
        if user is not None:
            return self.user_to_detailed_model(user)
        anon_response = self._anon_user_api_value(trans)
        return AnonUserModel(**anon_response)

    def user_to_detailed_model(
        self,
        user: User,
    ) -> DetailedUserModel:
        user_response = self.user_serializer.serialize_to_view(user, view="detailed")
        return DetailedUserModel(**user_response)

    def get_index(
        self,
        trans: ProvidesUserContext,
        deleted: bool,
        f_email: Optional[str],
        f_name: Optional[str],
        f_any: Optional[str],
    ) -> List[Union[UserModel, LimitedUserModel]]:
        rval = []
        stmt = select(User)

        if f_email and (trans.user_is_admin or trans.app.config.expose_user_email):
            stmt = stmt.filter(User.email.like(f"%{f_email}%"))

        if f_name and (trans.user_is_admin or trans.app.config.expose_user_name):
            stmt = stmt.filter(User.username.like(f"%{f_name}%"))

        if f_any:
            if trans.user_is_admin:
                stmt = stmt.filter(or_(User.email.like(f"%{f_any}%"), User.username.like(f"%{f_any}%")))
            else:
                if trans.app.config.expose_user_email and trans.app.config.expose_user_name:
                    stmt = stmt.filter(or_(User.email.like(f"%{f_any}%"), User.username.like(f"%{f_any}%")))
                elif trans.app.config.expose_user_email:
                    stmt = stmt.filter(User.email.like(f"%{f_any}%"))
                elif trans.app.config.expose_user_name:
                    stmt = stmt.filter(User.username.like(f"%{f_any}%"))

        if deleted:
            # only admins can see deleted users
            if not trans.user_is_admin:
                return []
            stmt = stmt.filter(User.deleted == true())
        else:
            # special case: user can see only their own user
            # special case2: if the galaxy admin has specified that other user email/names are
            #   exposed, we don't want special case #1
            if (
                not trans.user_is_admin
                and not trans.app.config.expose_user_name
                and not trans.app.config.expose_user_email
            ):
                item = trans.user.to_dict(value_mapper={"id": trans.security.encode_id})
                return [item]
            stmt = stmt.filter(User.deleted == false())
        for user in trans.sa_session.scalars(stmt).all():
            item = user.to_dict(value_mapper={"id": trans.security.encode_id})
            # If NOT configured to expose_email, do not expose email UNLESS the user is self, or
            # the user is an admin
            if user is not trans.user and not trans.user_is_admin:
                expose_keys = ["id"]
                if trans.app.config.expose_user_name:
                    expose_keys.append("username")
                if trans.app.config.expose_user_email:
                    expose_keys.append("email")
                new_item = {}
                for key, value in item.items():
                    if key in expose_keys:
                        new_item[key] = value
                item = new_item

            # TODO: move into api_values
            rval.append(item)
        return rval
