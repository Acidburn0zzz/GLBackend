# -*- coding: UTF-8
#
#   ping 
#   ****
# 
# Implements the network ping to leakdirectory server

import json
from pprint import pformat
from twisted.internet.protocol import Protocol
from twisted.internet.defer import Deferred

from cyclone.httpclient import StringProducer
from twisted.web.http_headers import Headers
from twisted.internet import reactor
from twisted.web.client import Agent

from globaleaks.utils.utility import log

LEAKDIRECTORY_ADDR = '127.0.0.1:8083'

class IndexPing(Protocol):

    def __init__(self, finished):
        self.finished = finished

    def connectionLost(self, reason):
        log.debug("Ping sent: %s" % reason.getErrorMessage())
        self.finished.callback(None)



def do_ping(hidden_service):

    log.debug("Sending to leakdirectory address %s the HS %s" %
              (LEAKDIRECTORY_ADDR, hidden_service) )

    agent = Agent(reactor)
    d = agent.request(
        'POST',
        'http://%s/ping' % LEAKDIRECTORY_ADDR,
        Headers({'User-Agent': ['GlobaLeaks node directory ping']}),
        StringProducer(
            json.dumps({
                'hidden_service' : hidden_service,
                })
        )
    )

    def cbRequest(response):
        log.debug('Response version: %s' % response.version)
        log.debug('Response code: %s' % response.code)
        log.debug('Response phrase: %s' % response.phrase)
        log.debug('Response headers:')
        log.debug(pformat(list(response.headers.getAllRawHeaders())) )

        finished = Deferred()
        response.deliverBody(IndexPing(finished))
        return finished

    def cbShutdown(ignored):
        log.err("Unable to contact Node directory index");

    d.addCallback(cbRequest)
    d.addErrback(cbShutdown)

