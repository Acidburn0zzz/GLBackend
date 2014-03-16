# -*- coding: UTF-8
#   node
#   ****
#
# Implementation of classes handling the HTTP request to /node, public
# exposed API.

from twisted.internet.defer import inlineCallbacks

from globaleaks.utils.utility import pretty_date_time, log
from globaleaks.utils.structures import Rosetta, Fields
from globaleaks.settings import transact_ro, GLSetting, stats_counter
from globaleaks.handlers.base import BaseHandler
from globaleaks.handlers.authentication import transport_security_check, unauthenticated
from globaleaks import models
from globaleaks import LANGUAGES_SUPPORTED

@transact_ro
def anon_serialize_node(store, user, language=GLSetting.memory_copy.default_language):
    node = store.find(models.Node).one()

    # Contexts and Receivers relationship
    associated = store.find(models.ReceiverContext).count()

    node_dict = {
      'name': unicode(node.name),
      'hidden_service': unicode(node.hidden_service),
      'public_site': unicode(node.public_site),
      'email': unicode(node.email),
      'languages_enabled': node.languages_enabled,
      'languages_supported': LANGUAGES_SUPPORTED,
      'default_language' : node.default_language,
      'configured': True if associated else False,
      # extended settings info:
      'maximum_namesize': node.maximum_namesize,
      'maximum_textsize': node.maximum_textsize,
      'maximum_filesize': node.maximum_filesize,
      # public serialization use GLSetting memory var, and
      # not the real one, because needs to bypass
      # Tor2Web unsafe deny default settings
      'tor2web_admin': GLSetting.memory_copy.tor2web_admin,
      'tor2web_submission': GLSetting.memory_copy.tor2web_submission,
      'tor2web_receiver': GLSetting.memory_copy.tor2web_receiver,
      'tor2web_unauth': GLSetting.memory_copy.tor2web_unauth,
      'ahmia': node.ahmia,
      'postpone_superpower': node.postpone_superpower,
      'can_delete_submission': node.can_delete_submission,
      'wizard_done': node.wizard_done,
      'anomaly_checks': node.anomaly_checks,
    }

    mo = Rosetta()
    mo.acquire_storm_object(node)
    for attr in mo.get_localized_attrs():
        node_dict[attr] = mo.dump_translated(attr, language)

    return node_dict

def anon_serialize_context(context, language=GLSetting.memory_copy.default_language):
    """
    @param context: a valid Storm object
    @return: a dict describing the contexts available for submission,
        (e.g. checks if almost one receiver is associated)
    """

    mo = Rosetta()
    mo.acquire_storm_object(context)
    fo = Fields(context.localized_fields, context.unique_fields)

    context_dict = {
        "id": unicode(context.id),
        "escalation_threshold": None,
        "file_max_download": int(context.file_max_download),
        "file_required": context.file_required,
        "selectable_receiver": bool(context.selectable_receiver),
        "tip_max_access": int(context.tip_max_access),
        "tip_timetolive": int(context.tip_timetolive),
        "submission_introduction": u'NYI', # unicode(context.submission_introduction), # optlang
        "submission_disclaimer": u'NYI', # unicode(context.submission_disclaimer), # optlang
        "select_all_receivers": context.select_all_receivers,
        "maximum_selectable_receivers": context.maximum_selectable_receivers,
        'require_pgp': context.require_pgp,
        "show_small_cards": context.show_small_cards,
        "presentation_order": context.presentation_order,
        "receivers": list(context.receivers.values(models.Receiver.id)),
        'name': mo.dump_translated('name', language),
        "description": mo.dump_translated('description', language),
        "fields": fo.dump_fields(language)
    }

    if not len(context_dict['receivers']):
        return None

    return context_dict


def anon_serialize_receiver(receiver, language=GLSetting.memory_copy.default_language):
    """
    @param receiver: a valid Storm object
    @return: a dict describing the receivers available in the node
        (e.g. checks if almost one context is associated, or, in
         node where GPG encryption is enforced, that a valid key is registered)
    """
    mo = Rosetta()
    mo.acquire_storm_object(receiver)

    receiver_dict = {
        "creation_date": pretty_date_time(receiver.creation_date),
        "update_date": pretty_date_time(receiver.last_update),
        "name": unicode(receiver.name),
        "description": mo.dump_translated('description', language),
        "id": unicode(receiver.id),
        "receiver_level": int(receiver.receiver_level),
        "tags": receiver.tags,
        "presentation_order": receiver.presentation_order,
        "gpg_key_status": receiver.gpg_key_status,
        "contexts": list(receiver.contexts.values(models.Context.id))
    }

    if not len(receiver_dict['contexts']):
        return None

    return receiver_dict


class InfoCollection(BaseHandler):
    """
    U1
    Returns information on the GlobaLeaks node. This includes submission
    parameters (contexts description, fields, public receiver list).
    Contains System-wide properties.
    """

    @transport_security_check("unauth")
    @unauthenticated
    @inlineCallbacks
    def get(self, *uriargs):
        """
        Parameters: None
        Response: publicNodeDesc
        Errors: NodeNotFound
        """
        stats_counter('anon_requests')
        response = yield anon_serialize_node(self.current_user, self.request.language)
        self.finish(response)


class AhmiaDescriptionHandler(BaseHandler):
    """
    Description of Ahmia 'protocol' is in:
    https://ahmia.fi/documentation/
    and we're supporting the Hidden Service description proposal from:
    https://ahmia.fi/documentation/descriptionProposal/
    """

    @transport_security_check("unauth")
    @unauthenticated
    @inlineCallbacks
    def get(self, *uriargs):

        log.debug("Requested Ahmia description file")
        node_info = yield anon_serialize_node(self.current_user, self.request.language)

        ahmia_description = {
            "title": node_info['name'],
            "description": node_info['description'],
            # we've not yet keywords, need to add them in Node ?
            "keywords": "%s (GlobaLeaks instance)" % node_info['name'],
            "relation": node_info['public_site'],
            "language": node_info['default_language'],
            "contactInformation": u'', # we've removed Node.email_addr
            "type": "GlobaLeaks"
        }
        self.finish(ahmia_description)


@transact_ro
def get_public_context_list(store, default_lang):
    context_list = []
    contexts = store.find(models.Context)

    for context in contexts:
        context_desc = anon_serialize_context(context, default_lang)
        # context not yet ready for submission return None
        if context_desc:
            context_list.append(context_desc)

    return context_list


class ContextsCollection(BaseHandler):
    """
    Return the public list of contexts, those information are shown in client
    and would be memorized in a third party indexer service. This is way some dates
    are returned within.
    """
    @transport_security_check("unauth")
    @unauthenticated
    @inlineCallbacks
    def get(self, *uriargs):
        """
        Parameters: None
        Response: publicContextList
        Errors: None
        """
        stats_counter('anon_requests')
        response = yield get_public_context_list(self.request.language)
        self.finish(response)

@transact_ro
def get_public_receiver_list(store, default_lang):
    receiver_list = []
    receivers = store.find(models.Receiver)

    for receiver in receivers:
        receiver_desc = anon_serialize_receiver(receiver, default_lang)
        # receiver not yet ready for submission return None
        if receiver_desc:
            receiver_list.append(receiver_desc)

    return receiver_list

class ReceiversCollection(BaseHandler):
    """
    Return the description of all the receivers visible from the outside.
    """

    @transport_security_check("unauth")
    @unauthenticated
    @inlineCallbacks
    def get(self, *uriargs):
        """
        Parameters: None
        Response: publicReceiverList
        Errors: None
        """
        stats_counter('anon_requests')
        response = yield get_public_receiver_list(self.request.language)
        self.finish(response)


class AllCollection(BaseHandler):
    """
    This interface return the whole Contexts, Receivers and Node public info
    is the unified version of the classes implemented above, and permit to
    receive the whole node public info with only one request
    """

    @transport_security_check("unauth")
    @unauthenticated
    @inlineCallbacks
    def get(self, *uriargs):

        stats_counter('anon_requests')

        receivers = yield get_public_receiver_list(self.request.language)
        contexts = yield get_public_context_list(self.request.language)
        node = yield anon_serialize_node(self.current_user, self.request.language)

        self.finish({
            'receivers': receivers,
            'contexts': contexts,
            'node': node
        })

