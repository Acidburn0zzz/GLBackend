# -*- coding: UTF-8
#   config
#   ******
#
# GlobaLeaks ORM Models definition

import types

from storm.locals import Bool, DateTime, Int, Pickle, Reference, ReferenceSet, Unicode, Storm
from globaleaks.settings import GLSetting
from globaleaks.rest import errors
from globaleaks.utils import datetime_now


def uuid():
    """
    Generated an UUID used in GlobaLeaks ORM models
    """
    import uuid as u
    return unicode(u.uuid4())

def gltextv(self, attr, value):
    """
    Just to avoid resources depletion by anonymous submissions,
    a simple validation that should make the exhaustion slower.
    """
    try:
        assert isinstance(value, unicode)
    except AssertionError:
        raise errors.InvalidInputFormat("Not an unicode as expected (%s = %s)" %
                        (attr, value))

    if (attr == 'name' and
        (len(value) > GLSetting.name_limit or len(value) == 0)):
        raise errors.InvalidInputFormat("name length need to be > 0 and " \
                                        "< of %d" % GLSetting.name_limit)
    elif attr == 'description' and len(value) > GLSetting.description_limit:
        raise errors.InvalidInputFormat("unicode description has a length " \
                                        "limit of %d"
                                        % GLSetting.description_limit)
    else:
        if len(value) > GLSetting.generic_limit:
            raise errors.InvalidInputFormat("unicode in %s overcome length " \
                                            "limit %d"
                                            % (attr, GLSetting.generic_limit))

    return value

def gldictv(self, attr, value):
    """
    Validate dict content, every key, if unicode, have not to
    overcome the generic lenght limit.
    """
    try:
        assert isinstance(value, dict)
    except AssertionError:
        raise errors.InvalidInputFormat("(%s) Not a dict as expected" % attr)

    if not value:
        return value

    for key, subvalue in value.iteritems():
        if isinstance(subvalue, unicode):
            if len(subvalue) > GLSetting.generic_limit:
                raise errors.InvalidInputFormat("In dict %s the key %s" \
                                                "overcome length limit of %d"
                                                % (attr, key,
                                                GLSetting.generic_limit))

    return value



class Model(Storm):
    """
    Base class for working the database
    """
    id = Unicode(primary=True, default_factory=uuid)
    # Note on creation last_update and last_access may be out of sync by some
    # seconds.
    creation_date = DateTime(default_factory=datetime_now)

    def __init__(self, attrs=None):
        if attrs is not None:
            self.update(attrs)


    def __new__(cls, *args, **kw):
        cls.__storm_table__ = cls.__name__.lower()
        # maybe check here for attrs validation, and eventually return None

        return Storm.__new__(cls, *args, **kw)

    def update(self, attrs=None):
        """
        Updated Models attributes based on attrs dictionary
        """
        # May raise ValueError and AttributeError
        if attrs is None:
            return

        # Dev note: these fields describe which key are expected in the
        # constructor. if not available, an error is raise.
        # other elements different from bool, unicode and int, can't be
        # processed by the generic "update" method and need to be assigned
        # to the object, [ but before commit(), if they are NOT NULL in the
        # SQL file ]
        cls_unicode_keys = getattr(self, "unicode_keys")
        cls_int_keys = getattr(self, "int_keys")
        cls_bool_keys = getattr(self, "bool_keys")

        for k in cls_unicode_keys:
            value = unicode(attrs[k])
            setattr(self, k, value)

        for k in cls_int_keys:
            value = int(attrs[k])
            setattr(self, k, value)

        for k in cls_bool_keys:
            value = bool(attrs[k])
            setattr(self, k, value)


    def __repr___(self):
        attrs = ['%s=%s' % (attr, getattr(self, attr))
                 for attr in vars(Model)
                 if isinstance(attr, types.MethodType)]
        return '<%s model with values %s>' % (self.__name__, ', '.join(attrs))

    def __setattr__(self, name, value):
        # harder better faster stronger
        if isinstance(value, str):
            value = unicode(value)

        return Storm.__setattr__(self, name, value)

    def dict(self, dict_filter=None):
        """
        return a dictionary serialization of the current model.
        if no filter is provided, returns every single attribute.
        """
        if dict_filter is None:
            dict_filter = [x for x in vars(Model) if isinstance(x, types.MethodType)]

        return dict((key, getattr(self, key)) for key in filter)

class Context(Model):
    """
    This models keeps track of specific contexts settings
    """
    name = Unicode(validator=gltextv)
    description = Unicode(validator=gltextv)
    fields = Pickle()

    selectable_receiver = Bool()
    escalation_threshold = Int()

    tip_max_access = Int()
    file_max_download = Int()

    # both expressed in seconds
    tip_timetolive = Int()
    submission_timetolive = Int()

    last_update = DateTime()

    #receivers = ReferenceSet(
    #                         Context.id,
    #                         ReceiverContext.context_id,
    #                         ReceiverContext.receiver_id,
    #                         Receiver.id)

    unicode_keys = ['name', 'description' ]
    int_keys = [ 'escalation_threshold', 'tip_max_access', 'tip_timetolive',
                 'file_max_download', 'submission_timetolive' ]
    bool_keys = [ 'selectable_receiver' ]


class InternalTip(Model):
    """
    This is the internal representation of a Tip that has been submitted to the
    GlobaLeaks node.

    It has a not associated map for keep track of Receivers, Tips,
    Comments and WhistleblowerTip.
    All of those element has a Storm Reference with the InternalTip.id,
    never vice-versa
    """
    context_id = Unicode()
    #context = Reference(InternalTip.context_id, Context.id)
    #comments = ReferenceSet(InternalTip.id, Comment.internaltip_id)
    #receivertips = ReferenceSet(InternalTip.id, ReceiverTip.internaltip_id)
    #internalfiles = ReferenceSet(InternalTip.id, InternalFile.internaltip_id)
    #receivers = ReferenceSet(InternalTip.id, Receiver.id)

    wb_fields = Pickle(validator=gldictv)
    pertinence_counter = Int()
    creation_date = DateTime()
    expiration_date = DateTime()
    last_activity = DateTime()

    # the LIMITS are stored in InternalTip because and admin may
    # need change them. These values are copied by Context
    escalation_threshold = Int()
    access_limit = Int()
    download_limit = Int()

    mark = Unicode()

    _marker = [ u'submission', u'finalize', u'first', u'second' ]
    ## NO *_keys = It's created without initializing dict


class ReceiverTip(Model):
    """
    This is the table keeping track of ALL the receivers activities and
    date in a Tip, Tip core data are stored in StoredTip. The data here
    provide accountability of Receiver accesses, operations, options.
    """
    internaltip_id = Unicode()
    receiver_id = Unicode()
    #internaltip = Reference(ReceiverTip.internaltip_id, InternalTip.id)
    #receiver = Reference(ReceiverTip.receiver_id, Receiver.id)

    last_access = DateTime(default_factory=datetime_now)
    access_counter = Int()
    expressed_pertinence = Int()
    notification_date = DateTime()
    mark = Unicode()

    _marker = [ u'not notified', u'notified', u'unable to notify' ]

    ## NO *_keys = It's created without initializing dict

class WhistleblowerTip(Model):
    """
    WhisteleblowerTip is intended, to provide a whistleblower access to the Tip.
    Has ome differencies from the ReceiverTips: has a secret authentication checks, has
    different capabilities, like: cannot not download, cannot express pertinence.
    """
    internaltip_id = Unicode()
    #internaltip = Reference(WhistleblowerTip.internaltip_id, InternalTip.id)
    receipt_hash = Unicode()
    last_access = DateTime()
    access_counter = Int()

    ## NO *_keys = It's created without initializing dict


class ReceiverFile(Model):
    """
    This model keeps track of files destinated to a specific receiver
    """
    internaltip_id = Unicode()
    internalfile_id = Unicode()
    receiver_id = Unicode()
    #internalfile = Reference(ReceiverFile.internalfile_id, InternalFile.id)
    #receiver = Reference(ReceiverFile.receiver_id, Receiver.id)
    #internaltip = Reference(ReceiverFile.internaltip_id, InternalTip.id)

    file_path = Unicode()
    downloads = Int()
    last_access = DateTime()

    mark = Unicode()
    _marker = [ u'not notified', u'notified', u'unable to notify' ]
    ## NO *_keys = It's created without initializing dict


class InternalFile(Model):
    """
    This model keeps track of files before they are packaged
    for specific receivers
    """
    internaltip_id = Unicode()
    #internaltip = Reference(InternalFile.internaltip_id, InternalTip.id)

    name = Unicode(validator=gltextv)
    sha2sum = Unicode()
    file_path = Unicode()

    content_type = Unicode()
    size = Int()

    mark = Unicode()
    _marker = [ u'not processed', u'ready', u'blocked', u'stored' ]
    ## NO *_keys = It's created without initializing dict


class Comment(Model):
    """
    This table handle the comment collection, has an InternalTip referenced
    """
    internaltip_id = Unicode()

    author = Unicode()
    content = Unicode(validator=gltextv)

    type = Unicode()
    _types = [ u'receiver', u'whistleblower', u'system' ]
    mark = Unicode()
    _marker = [ u'not notified', u'notified', u'unable to notify' ]
    ## NO *_keys = It's created without initializing dict


class Node(Model):
    """
    This table has only one instance, has the "id", but would not exists a second element
    of this table. This table acts, more or less, like the configuration file of the previous
    GlobaLeaks release (and some of the GL 0.1 details are specified in Context)

    This table represent the System-wide settings
    """
    description = Unicode(validator=gltextv)
    name = Unicode(validator=gltextv)
    public_site = Unicode(validator=gltextv)
    email = Unicode()
    languages = Pickle()
    salt = Unicode()
    receipt_salt = Unicode()
    password = Unicode()
    last_update = DateTime()

    # Here is set the time frame for the stats publicly exported by the node.
    # Expressed in hours
    stats_update_time = Int()
    stats_update_time = Int()

    unicode_keys = ['name', 'description', 'email', 'public_site' ]
    int_keys = [ 'stats_update_time' ]
    bool_keys = []


class Notification(Model):
    """
    This table has only one instance, and contain all the notification information
    for the node
    templates are imported in the handler, but settings are expected all at once
    """
    server = Unicode()
    port = Int()
    username = Unicode()
    password = Unicode()

    security = Unicode()
    _security_types = [ u'TLS', u'SSL' ]

    # In the future these would be Markdown!
    tip_template = Unicode()
    file_template = Unicode()
    comment_template = Unicode()
    activation_template = Unicode()
    # these four template would be in the unicode_key implicit
    # expected fields, when Client/Backend are updated in their usage

    unicode_keys = ['server', 'username', 'password', 'tip_template',
                    'file_template', 'comment_template', 'activation_template' ]
    int_keys = ['port']
    bool_keys = []


class Receiver(Model):
    """
    name, description, password and notification_fiels, can be changed
    by Receiver itself
    """
    name = Unicode(validator=gltextv)
    description = Unicode(validator=gltextv)

    # Authentication variables
    username = Unicode()
    password = Unicode()

    # User notification_variable
    notification_fields = Pickle()

    # Admin chosen options
    can_delete_submission = Bool()

    # receiver_tier = 1 or 2. Mean being part of the first or second level
    # of receivers body. if threshold is configured in the context. default 1
    receiver_level = Int()

    # counter
    failed_login = Int()

    last_update = DateTime()
    last_access = DateTime(default_factory=datetime_now)

    # contexts = ReferenceSet("Context.id",
    #                         "ReceiverContext.context_id",
    #                         "ReceiverContext.receiver_id",
    #                         "Receiver.id")

    unicode_keys = ['name', 'description' ]
    int_keys = [ 'receiver_level' ]
    bool_keys = [ 'can_delete_submission' ] # Total delete capability


# Follow two classes used for Many to Many references
class ReceiverContext(object):
    """
    Class used to implement references between Receivers and Contexts
    """
    __storm_table__ = 'receiver_context'
    __storm_primary__ = 'context_id', 'receiver_id'
    context_id = Unicode()
    receiver_id = Unicode()

Context.receivers = ReferenceSet(
                                 Context.id,
                                 ReceiverContext.context_id,
                                 ReceiverContext.receiver_id,
                                 Receiver.id)

Receiver.contexts = ReferenceSet(
                        Receiver.id,
                        ReceiverContext.receiver_id,
                        ReceiverContext.context_id,
                        Context.id)

class ReceiverInternalTip(object):
    """
    Class used to implement references between Receivers and IntInternalTips
    """
    __storm_table__ = 'receiver_internaltip'
    __storm_primary__ = 'receiver_id', 'internaltip_id'
    receiver_id = Unicode()
    internaltip_id = Unicode()

Receiver.internaltips = ReferenceSet(Receiver.id,
                                     ReceiverInternalTip.receiver_id,
                                     ReceiverInternalTip.internaltip_id,
                                     InternalTip.id)

InternalTip.receivers = ReferenceSet(InternalTip.id,
                                     ReceiverInternalTip.internaltip_id,
                                     ReceiverInternalTip.receiver_id,
                                     Receiver.id)

InternalTip.context = Reference(InternalTip.context_id,
                                Context.id)

InternalTip.comments = ReferenceSet(InternalTip.id,
                                    Comment.internaltip_id)

InternalTip.receivertips = ReferenceSet(InternalTip.id,
                                        ReceiverTip.internaltip_id)

InternalTip.internalfiles = ReferenceSet(InternalTip.id,
                                         InternalFile.internaltip_id)

ReceiverFile.internalfile = Reference(ReceiverFile.internalfile_id,
                                      InternalFile.id)

ReceiverFile.receiver = Reference(ReceiverFile.receiver_id, Receiver.id)

ReceiverFile.internaltip = Reference(ReceiverFile.internaltip_id,
                                     InternalTip.id)

WhistleblowerTip.internaltip = Reference(WhistleblowerTip.internaltip_id,
                                         InternalTip.id)

InternalFile.internaltip = Reference(InternalFile.internaltip_id,
                                     InternalTip.id)

ReceiverTip.internaltip = Reference(ReceiverTip.internaltip_id, InternalTip.id)

ReceiverTip.receiver = Reference(ReceiverTip.receiver_id, Receiver.id)

Receiver.tips = ReferenceSet(Receiver.id, ReceiverTip.receiver_id)

Comment.internaltip = Reference(Comment.internaltip_id, InternalTip.id)


models = [Node, Context, ReceiverTip, WhistleblowerTip, Comment, InternalTip,
          Receiver, ReceiverContext, InternalFile, ReceiverFile, Notification ]

