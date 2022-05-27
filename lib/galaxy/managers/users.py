"""
Manager and Serializer for Users.
"""
import hashlib
import logging
import random
import socket
import time
from datetime import datetime

from markupsafe import escape
from sqlalchemy import and_, desc, exc, func, true
from sqlalchemy.orm.exc import NoResultFound

from galaxy import (
    exceptions,
    model,
    schema,
    util,
)
from galaxy.managers import (
    api_keys,
    base,
    deletable
)
from galaxy.security.validate_user_input import (
    VALID_EMAIL_RE,
    validate_email,
    validate_password,
    validate_publicname
)
from galaxy.structured_app import BasicSharedApp, MinimalManagerApp
from galaxy.util.hash_util import new_secure_hash
from galaxy.web import url_for

log = logging.getLogger(__name__)

PASSWORD_RESET_TEMPLATE = """
To reset your Galaxy password for the instance at %s use the following link,
which will expire %s.

%s%s

If you did not make this request, no action is necessary on your part, though
you may want to notify an administrator.

If you're having trouble using the link when clicking it from email client, you
can also copy and paste it into your browser.
"""


class UserManager(base.ModelManager, deletable.PurgableManagerMixin):
    foreign_key_name = 'user'

    # TODO: there is quite a bit of functionality around the user (authentication, permissions, quotas, groups/roles)
    #   most of which it may be unneccessary to have here

    # TODO: incorp BaseAPIController.validate_in_users_and_groups
    # TODO: incorp CreatesApiKeysMixin
    # TODO: incorporate UsesFormDefinitionsMixin?
    def __init__(self, app: BasicSharedApp):
        self.model_class = app.model.User
        super().__init__(app)

    def register(self, trans, email=None, username=None, password=None, confirm=None, subscribe=False):
        """
        Register a new user.
        """
        if not trans.app.config.allow_user_creation and not trans.user_is_admin:
            message = "User registration is disabled.  Please contact your local Galaxy administrator for an account."
            if trans.app.config.error_email_to is not None:
                message += f" Contact: {trans.app.config.error_email_to}"
            return None, message
        if not email or not username or not password or not confirm:
            return None, "Please provide email, username and password."
        message = "\n".join((validate_email(trans, email),
                             validate_password(trans, password, confirm),
                             validate_publicname(trans, username))).rstrip()
        if message:
            return None, message
        email = util.restore_text(email)
        username = util.restore_text(username)
        message, status = trans.app.auth_manager.check_registration_allowed(email, username, password)
        if message:
            return None, message
        if subscribe:
            message = self.send_subscription_email(email)
            if message:
                return None, message
        user = self.create(email=email, username=username, password=password)
        if self.app.config.user_activation_on:
            self.send_activation_email(trans, email, username)
        return user, None

    def create(self, email=None, username=None, password=None, **kwargs):
        """
        Create a new user.
        """
        self._error_on_duplicate_email(email)
        user = self.model_class(email=email)
        if password:
            user.set_password_cleartext(password)
        else:
            user.set_random_password()
        user.username = username
        if self.app.config.user_activation_on:
            user.active = False
        else:
            # Activation is off, every new user is active by default.
            user.active = True
        self.session().add(user)
        try:
            self.session().flush()
            # TODO:?? flush needed for permissions below? If not, make optional
        except exc.IntegrityError as db_err:
            raise exceptions.Conflict(str(db_err))
        self.app.security_agent.create_user_role(user, self.app)
        return user

    def delete(self, user, flush=True):
        """Mark the given user deleted."""
        if not self.app.config.allow_user_deletion:
            raise exceptions.ConfigDoesNotAllowException('The configuration of this Galaxy instance does not allow admins to delete users.')
        super().delete(user, flush=flush)

    def undelete(self, user, flush=True):
        """Remove the deleted flag for the given user."""
        if not self.app.config.allow_user_deletion:
            raise exceptions.ConfigDoesNotAllowException('The configuration of this Galaxy instance does not allow admins to undelete users.')
        if user.purged:
            raise exceptions.ItemDeletionException('Purged user cannot be undeleted.')
        super().undelete(user, flush=flush)

    def purge(self, user, flush=True):
        """Purge the given user. They must have the deleted flag already."""
        if not self.app.config.allow_user_deletion:
            raise exceptions.ConfigDoesNotAllowException('The configuration of this Galaxy instance does not allow admins to delete or purge users.')
        if not user.deleted:
            raise exceptions.MessageException('User \'%s\' has not been deleted, so they cannot be purged.' % user.email)
        private_role = self.app.security_agent.get_private_user_role(user)
        # Delete History
        for active_history in user.active_histories:
            self.session().refresh(active_history)
            for hda in active_history.active_datasets:
                # Delete HistoryDatasetAssociation
                hda.deleted = True
                self.session().add(hda)
            active_history.deleted = True
            self.session().add(active_history)
        # Delete UserGroupAssociations
        for uga in user.groups:
            self.session().delete(uga)
        # Delete UserRoleAssociations EXCEPT FOR THE PRIVATE ROLE
        for ura in user.roles:
            if ura.role_id != private_role.id:
                self.session().delete(ura)
        # Delete UserAddresses
        for address in user.addresses:
            self.session().delete(address)
        compliance_log = logging.getLogger('COMPLIANCE')
        compliance_log.info(f'delete-user-event: {user.username}')
        # Maybe there is some case in the future where an admin needs
        # to prove that a user was using a server for some reason (e.g.
        # a court case.) So we make this painfully hard to recover (and
        # not immediately reversable) in line with GDPR, but still
        # leave open the possibility to prove someone was part of the
        # server just in case. By knowing the exact email + approximate
        # time of deletion, one could run through hashes for every
        # second of the surrounding days/weeks.
        pseudorandom_value = str(int(time.time()))
        # Replace email + username with a (theoretically) unreversable
        # hash. If provided with the username we can probably re-hash
        # to identify if it is needed for some reason.
        #
        # Deleting multiple times will re-hash the username/email
        email_hash = new_secure_hash(user.email + pseudorandom_value)
        uname_hash = new_secure_hash(user.username + pseudorandom_value)
        # We must also redact username
        for role in user.all_roles():
            if self.app.config.redact_username_during_deletion:
                role.name = role.name.replace(user.username, uname_hash)
                role.description = role.description.replace(user.username, uname_hash)

            if self.app.config.redact_email_during_deletion:
                role.name = role.name.replace(user.email, email_hash)
                role.description = role.description.replace(user.email, email_hash)
            user.email = email_hash
            user.username = uname_hash
        # Redact user addresses as well
        if self.app.config.redact_user_address_during_deletion:
            user_addresses = self.session().query(self.app.model.UserAddress) \
                .filter(self.app.model.UserAddress.user_id == user.id).all()
            for addr in user_addresses:
                addr.desc = new_secure_hash(addr.desc + pseudorandom_value)
                addr.name = new_secure_hash(addr.name + pseudorandom_value)
                addr.institution = new_secure_hash(addr.institution + pseudorandom_value)
                addr.address = new_secure_hash(addr.address + pseudorandom_value)
                addr.city = new_secure_hash(addr.city + pseudorandom_value)
                addr.state = new_secure_hash(addr.state + pseudorandom_value)
                addr.postal_code = new_secure_hash(addr.postal_code + pseudorandom_value)
                addr.country = new_secure_hash(addr.country + pseudorandom_value)
                addr.phone = new_secure_hash(addr.phone + pseudorandom_value)
                self.session().add(addr)
        # Purge the user
        super().purge(user, flush=flush)

    def _error_on_duplicate_email(self, email):
        """
        Check for a duplicate email and raise if found.

        :raises exceptions.Conflict: if any are found
        """
        # TODO: remove this check when unique=True is added to the email column
        if self.by_email(email) is not None:
            raise exceptions.Conflict('Email must be unique', email=email)

    def by_id(self, user_id):
        return self.app.model.session.query(self.model_class).get(user_id)

    # ---- filters
    def by_email(self, email, filters=None, **kwargs):
        """
        Find a user by their email.
        """
        filters = self._munge_filters(self.model_class.email == email, filters)
        try:
            # TODO: use one_or_none
            return super().one(filters=filters, **kwargs)
        except exceptions.ObjectNotFound:
            return None

    def by_api_key(self, api_key, sa_session=None):
        """
        Find a user by API key.
        """
        if self.check_master_api_key(api_key=api_key):
            return schema.BootstrapAdminUser()
        sa_session = sa_session or self.app.model.session
        try:
            provided_key = sa_session.query(self.app.model.APIKeys).filter(self.app.model.APIKeys.key == api_key).one()
        except NoResultFound:
            raise exceptions.AuthenticationFailed('Provided API key is not valid.')
        if provided_key.user.deleted:
            raise exceptions.AuthenticationFailed('User account is deactivated, please contact an administrator.')
        sa_session.refresh(provided_key.user)
        newest_key = provided_key.user.api_keys[0]
        if newest_key.key != provided_key.key:
            raise exceptions.AuthenticationFailed('Provided API key has expired.')
        return provided_key.user

    def check_master_api_key(self, api_key):
        master_api_key = getattr(self.app.config, 'master_api_key', None)
        if not master_api_key:
            return False
        # Hash keys to make them the same size, so we can do safe comparison.
        master_hash = hashlib.sha256(util.smart_str(master_api_key)).hexdigest()
        provided_hash = hashlib.sha256(util.smart_str(api_key)).hexdigest()
        return util.safe_str_cmp(master_hash, provided_hash)

    # ---- admin
    def is_admin(self, user, trans=None):
        """Return True if this user is an admin (or session is authenticated as admin).

        Do not pass trans to simply check if an existing user object is an admin user,
        pass trans when checking permissions.
        """
        if user is None:
            # Anonymous session or master_api_key used, if master_api_key is detected
            # return True.
            return trans and trans.user_is_admin
        return self.app.config.is_admin_user(user)

    def admins(self, filters=None, **kwargs):
        """
        Return a list of admin Users.
        """
        admin_emails = self.app.config.admin_users_list
        filters = self._munge_filters(self.model_class.email.in_(admin_emails), filters)
        return super().list(filters=filters, **kwargs)

    def error_unless_admin(self, user, msg="Administrators only", **kwargs):
        """
        Raise an error if `user` is not an admin.

        :raises exceptions.AdminRequiredException: if `user` is not an admin.
        """
        # useful in admin only methods
        if not self.is_admin(user, trans=kwargs.get("trans", None)):
            raise exceptions.AdminRequiredException(msg, **kwargs)
        return user

    # ---- anonymous
    def is_anonymous(self, user):
        """
        Return True if `user` is anonymous.
        """
        # define here for single point of change and make more readable
        return user is None

    def error_if_anonymous(self, user, msg="Log-in required", **kwargs):
        """
        Raise an error if `user` is anonymous.
        """
        if user is None:
            # TODO: code is correct (401) but should be named AuthenticationRequired (401 and 403 are flipped)
            raise exceptions.AuthenticationFailed(msg, **kwargs)
        return user

    def get_user_by_identity(self, identity):
        """Get user by username or email."""
        user = None
        if VALID_EMAIL_RE.match(identity):
            # VALID_PUBLICNAME and VALID_EMAIL do not overlap, so 'identity' here is an email address
            user = self.session().query(self.model_class).filter(
                self.model_class.table.c.email == identity).first()
            if not user:
                # Try a case-insensitive match on the email
                user = self.session().query(self.model_class).filter(
                    func.lower(self.model_class.table.c.email) == identity.lower()).first()
        else:
            user = self.session().query(self.model_class).filter(
                self.model_class.table.c.username == identity).first()
        return user

    # ---- current
    def current_user(self, trans):
        # define here for single point of change and make more readable
        # TODO: trans
        return trans.user

    # ---- api keys
    def create_api_key(self, user):
        """
        Create and return an API key for `user`.
        """
        # TODO: seems like this should return the model
        # Also TODO: seems unused? drop and see what happens? -John
        return api_keys.ApiKeyManager(self.app).create_api_key(user)

    def user_can_do_run_as(self, user) -> bool:
        run_as_users = [u for u in self.app.config.get("api_allow_run_as", "").split(",") if u]
        if not run_as_users:
            return False
        user_in_run_as_users = user and user.email in run_as_users
        # Can do if explicitly in list or master_api_key supplied.
        can_do_run_as = user_in_run_as_users or user.bootstrap_admin_user
        return can_do_run_as

    # TODO: possibly move to ApiKeyManager
    def valid_api_key(self, user):
        """
        Return this most recent APIKey for this user or None if none have been created.
        """
        query = (self.session().query(model.APIKeys)
                 .filter_by(user=user)
                 .order_by(desc(model.APIKeys.create_time)))
        all = query.all()
        if len(all):
            return all[0]
        return None

    # TODO: possibly move to ApiKeyManager
    def get_or_create_valid_api_key(self, user):
        """
        Return this most recent APIKey for this user or create one if none have been
        created.
        """
        existing = self.valid_api_key(user)
        if existing:
            return existing
        return self.create_api_key(self, user)

    # ---- preferences
    def preferences(self, user):
        return {key: value for key, value in user.preferences.items()}

    # ---- roles and permissions
    def private_role(self, user):
        return self.app.security_agent.get_private_user_role(user)

    def sharing_roles(self, user):
        return self.app.security_agent.get_sharing_roles(user)

    def default_permissions(self, user):
        return self.app.security_agent.user_get_default_permissions(user)

    def quota(self, user, total=False):
        if total:
            return self.app.quota_agent.get_quota_nice_size(user)
        return self.app.quota_agent.get_percent(user=user)

    def tags_used(self, user, tag_models=None):
        """
        Return a list of distinct 'user_tname:user_value' strings that the
        given user has used.
        """
        # TODO: simplify and unify with tag manager
        if self.is_anonymous(user):
            return []

        # get all the taggable model TagAssociations
        if not tag_models:
            tag_models = [v.tag_assoc_class for v in self.app.tag_handler.item_tag_assoc_info.values()]
        # create a union of subqueries for each for this user - getting only the tname and user_value
        all_tags_query = None
        for tag_model in tag_models:
            subq = (self.session().query(tag_model.user_tname, tag_model.user_value)
                    .filter(tag_model.user == user))
            all_tags_query = subq if all_tags_query is None else all_tags_query.union(subq)

        # if nothing init'd the query, bail
        if all_tags_query is None:
            return []

        # boil the tag tuples down into a sorted list of DISTINCT name:val strings
        tags = all_tags_query.distinct().all()
        tags = [(f"{name}:{val}" if val else name) for name, val in tags]
        return sorted(tags)

    def change_password(self, trans, password=None, confirm=None, token=None, id=None, current=None):
        """
        Allows to change a user password with a token.
        """
        if not token and not id:
            return None, "Please provide a token or a user and password."
        if token:
            token_result = trans.sa_session.query(self.app.model.PasswordResetToken).get(token)
            if not token_result or not token_result.expiration_time > datetime.utcnow():
                return None, "Invalid or expired password reset token, please request a new one."
            user = token_result.user
            message = self.__set_password(trans, user, password, confirm)
            if message:
                return None, message
            token_result.expiration_time = datetime.utcnow()
            trans.sa_session.add(token_result)
            return user, "Password has been changed. Token has been invalidated."
        else:
            user = self.by_id(self.app.security.decode_id(id))
            if user:
                message = self.app.auth_manager.check_change_password(user, current)
                if message:
                    return None, message
                message = self.__set_password(trans, user, password, confirm)
                if message:
                    return None, message
                return user, "Password has been changed."
            else:
                return user, "User not found."

    def __set_password(self, trans, user, password, confirm):
        if not password:
            return "Please provide a new password."
        if user:
            # Validate the new password
            message = validate_password(trans, password, confirm)
            if message:
                return message
            else:
                # Save new password
                user.set_password_cleartext(password)
                # Invalidate all other sessions
                if trans.galaxy_session:
                    for other_galaxy_session in trans.sa_session.query(self.app.model.GalaxySession) \
                                                     .filter(and_(self.app.model.GalaxySession.table.c.user_id == user.id,
                                                                  self.app.model.GalaxySession.table.c.is_valid == true(),
                                                                  self.app.model.GalaxySession.table.c.id != trans.galaxy_session.id)):
                        other_galaxy_session.is_valid = False
                        trans.sa_session.add(other_galaxy_session)
                trans.sa_session.add(user)
                trans.sa_session.flush()
                trans.log_event("User change password")
        else:
            return "Failed to determine user, access denied."

    def send_activation_email(self, trans, email, username):
        """
        Send the verification email containing the activation link to the user's email.
        """
        activation_token = self.__get_activation_token(trans, email)
        activation_link = url_for(controller='user', action='activate', activation_token=activation_token, email=escape(email), qualified=True)
        host = self.__get_host(trans)
        custom_message = ''
        if self.app.config.custom_activation_email_message:
            custom_message = f"{self.app.config.custom_activation_email_message}\n\n"
        body = ("Hello %s,\n\n"
                "In order to complete the activation process for %s begun on %s at %s, please click "
                "on the following link to verify your account:\n\n" "%s \n\n"
                "By clicking on the above link and opening a Galaxy account you are also confirming "
                "that you have read and agreed to Galaxy's Terms and Conditions for use of this "
                "service (%s). This includes a quota limit of one account per user. Attempts to "
                "subvert this limit by creating multiple accounts or through any other method may "
                "result in termination of all associated accounts and data.\n\n"
                "Please contact us if you need help with your account at: %s. You can also browse "
                "resources available" " at: %s. \n\n"
                "More about the Galaxy Project can be found at galaxyproject.org\n\n"
                "%s"
                "Your Galaxy Team" % (
                    escape(username),
                    escape(email),
                    datetime.utcnow().strftime("%D"),
                    trans.request.host,
                    activation_link,
                    self.app.config.terms_url,
                    self.app.config.error_email_to,
                    self.app.config.instance_resource_url,
                    custom_message)
                )
        to = email
        frm = self.app.config.email_from or f"galaxy-no-reply@{host}"
        subject = 'Galaxy Account Activation'
        try:
            util.send_mail(frm, to, subject, body, self.app.config)
            return True
        except Exception:
            log.debug(body)
            log.exception('Unable to send the activation email.')
            return False

    def __get_activation_token(self, trans, email):
        """
        Check for the activation token. Create new activation token and store it in the database if no token found.
        """
        user = trans.sa_session.query(self.app.model.User).filter(self.app.model.User.table.c.email == email).first()
        activation_token = user.activation_token
        if activation_token is None:
            activation_token = util.hash_util.new_secure_hash(str(random.getrandbits(256)))
            user.activation_token = activation_token
            trans.sa_session.add(user)
            trans.sa_session.flush()
        return activation_token

    def send_reset_email(self, trans, payload, **kwd):
        """Reset the user's password. Send an email with token that allows a password change."""
        if self.app.config.smtp_server is None:
            return "Mail is not configured for this Galaxy instance and password reset information cannot be sent. Please contact your local Galaxy administrator."
        email = payload.get("email")
        if not email:
            return "Please provide your email."
        message = validate_email(trans, email, check_dup=False)
        if message:
            return message
        else:
            reset_user, prt = self.get_reset_token(trans, email)
            if prt:
                host = self.__get_host(trans)
                reset_url = url_for(controller='root', action='login', token=prt.token)
                body = PASSWORD_RESET_TEMPLATE % (host, prt.expiration_time.strftime(trans.app.config.pretty_datetime_format),
                                                  trans.request.host, reset_url)
                frm = trans.app.config.email_from or f"galaxy-no-reply@{host}"
                subject = 'Galaxy Password Reset'
                try:
                    util.send_mail(frm, email, subject, body, self.app.config)
                    trans.sa_session.add(reset_user)
                    trans.sa_session.flush()
                    trans.log_event(f'User reset password: {email}')
                except Exception as e:
                    log.debug(body)
                    return f"Failed to submit email. Please contact the administrator: {util.unicodify(e)}"
            else:
                return "Failed to produce password reset token. User not found."

    def get_reset_token(self, trans, email):
        reset_user = trans.sa_session.query(self.app.model.User).filter(self.app.model.User.table.c.email == email).first()
        if not reset_user and email != email.lower():
            reset_user = trans.sa_session.query(self.app.model.User).filter(func.lower(self.app.model.User.table.c.email) == email.lower()).first()
        if reset_user:
            prt = self.app.model.PasswordResetToken(reset_user)
            trans.sa_session.add(prt)
            trans.sa_session.flush()
            return reset_user, prt
        return None, None

    def __get_host(self, trans):
        host = trans.request.host.split(':')[0]
        if host in ['localhost', '127.0.0.1', '0.0.0.0']:
            host = socket.getfqdn()
        return host

    def send_subscription_email(self, email):
        if self.app.config.smtp_server is None:
            return "Subscribing to the mailing list has failed because mail is not configured for this Galaxy instance. Please contact your local Galaxy administrator."
        else:
            body = (self.app.config.mailing_join_body or '') + '\n'
            to = self.app.config.mailing_join_addr
            frm = email
            subject = self.app.config.mailing_join_subject or ''
            try:
                util.send_mail(frm, to, subject, body, self.app.config)
            except Exception:
                log.exception('Subscribing to the mailing list has failed.')
                return "Subscribing to the mailing list has failed."

    def activate(self, user):
        user.active = True
        self.session().add(user)
        self.session().flush()


class UserSerializer(base.ModelSerializer, deletable.PurgableSerializerMixin):
    model_manager_class = UserManager

    def __init__(self, app: MinimalManagerApp):
        """
        Convert a User and associated data to a dictionary representation.
        """
        super().__init__(app)
        self.user_manager = self.manager

        self.default_view = 'summary'
        self.add_view('summary', [
            'id', 'email', 'username'
        ])
        self.add_view('detailed', [
            # 'update_time',
            # 'create_time',
            'is_admin',
            'total_disk_usage',
            'nice_total_disk_usage',
            'quota_percent',
            'quota',
            'deleted',
            'purged',
            # 'active',

            'preferences',
            #  all tags
            'tags_used',
            # all annotations
            # 'annotations'
        ], include_keys_from='summary')

    def add_serializers(self):
        super().add_serializers()
        deletable.PurgableSerializerMixin.add_serializers(self)

        self.serializers.update({
            'id': self.serialize_id,
            'create_time': self.serialize_date,
            'update_time': self.serialize_date,
            'is_admin': lambda i, k, **c: self.user_manager.is_admin(i),

            'preferences': lambda i, k, **c: self.user_manager.preferences(i),

            'total_disk_usage': lambda i, k, **c: float(i.total_disk_usage),
            'quota_percent': lambda i, k, **c: self.user_manager.quota(i),
            'quota': lambda i, k, **c: self.user_manager.quota(i, total=True),

            'tags_used': lambda i, k, **c: self.user_manager.tags_used(i),
        })


class UserDeserializer(base.ModelDeserializer):
    """
    Service object for validating and deserializing dictionaries that
    update/alter users.
    """
    model_manager_class = UserManager

    def add_deserializers(self):
        super().add_deserializers()
        self.deserializers.update({
            'username': self.deserialize_username,
        })

    def deserialize_username(self, item, key, username, trans=None, **context):
        # TODO: validate_publicname requires trans and should(?) raise exceptions
        # move validation to UserValidator and use self.app, exceptions instead
        validation_error = validate_publicname(trans, username, user=item)
        if validation_error:
            raise base.ModelDeserializingError(validation_error)
        return self.default_deserializer(item, key, username, trans=trans, **context)


class CurrentUserSerializer(UserSerializer):
    model_manager_class = UserManager

    def serialize(self, user, keys, **kwargs):
        """
        Override to return at least some usage info if user is anonymous.
        """
        kwargs['current_user'] = user
        if self.user_manager.is_anonymous(user):
            return self.serialize_current_anonymous_user(user, keys, **kwargs)
        return super(UserSerializer, self).serialize(user, keys, **kwargs)

    def serialize_current_anonymous_user(self, user, keys, trans=None, **kwargs):
        # use the current history if any to get usage stats for trans' anonymous user
        # TODO: might be better as sep. Serializer class
        usage = 0
        percent = None

        history = trans.history
        if history:
            usage = self.app.quota_agent.get_usage(trans, history=trans.history)
            percent = self.app.quota_agent.get_percent(trans=trans, usage=usage)

        # a very small subset of keys available
        values = {
            'id': None,
            'total_disk_usage': float(usage),
            'nice_total_disk_usage': util.nice_size(usage),
            'quota_percent': percent,
        }
        serialized = {}
        for key in keys:
            if key in values:
                serialized[key] = values[key]
        return serialized


class AdminUserFilterParser(base.ModelFilterParser, deletable.PurgableFiltersMixin):
    model_manager_class = UserManager
    model_class = model.User

    def _add_parsers(self):
        super()._add_parsers()
        deletable.PurgableFiltersMixin._add_parsers(self)

        # PRECONDITION: user making the query has been verified as an admin
        self.orm_filter_parsers.update({
            'email': {'op': ('eq', 'contains', 'like')},
            'username': {'op': ('eq', 'contains', 'like')},
            'active': {'op': ('eq')},
            'disk_usage': {'op': ('le', 'ge')}
        })

        self.fn_filter_parsers.update({})
