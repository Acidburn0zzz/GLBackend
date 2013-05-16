# -*- coding: UTF-8
#   config
#   ******
#
# Configuration file do not contain GlobaLeaks Node information, like in the 0.1
# because all those infos are stored in the databased.
# Config contains some system variables usable for debug,

import os
import sys
import shutil
import traceback
import logging
import transaction
import socket

import pwd
import grp
import getpass

from optparse import OptionParser
from twisted.python import log
from twisted.python.threadpool import ThreadPool
from twisted.internet import reactor
from storm import exceptions
from twisted.internet.threads import deferToThreadPool
from cyclone.web import HTTPError
from storm import tracer

from globaleaks import __version__

verbosity_dict = {
    'DEBUG': logging.DEBUG,
    'INFO' : logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}

from storm.zope.zstorm import ZStorm
from storm.databases.sqlite import sqlite

def set_default_uri(self, name, default_uri):
    """Set C{default_uri} as the default URI for stores called C{name}."""

    def raw_connect():
        _self = self._default_databases[name]

        # See the story at the end to understand why we set isolation_level.
        raw_connection = sqlite.connect(_self._filename, timeout=_self._timeout,
                                        isolation_level=None)
        if _self._synchronous is not None:
            raw_connection.execute("PRAGMA synchronous = %s" %
                                   (_self._synchronous,))

        raw_connection.execute("PRAGMA journal_mode = WAL")

        raw_connection.execute("PRAGMA foreign_keys = ON")

        return raw_connection

    self._default_databases[name] = self._get_database(default_uri)
    self._default_uris[name] = default_uri

    self._default_databases[name].raw_connect = raw_connect

ZStorm.set_default_uri = set_default_uri

class GLSettingsClass:

    def __init__(self):
        # command line parsing utils
        self.parser = OptionParser()
        self.cmdline_options = None

        # version
        self.version_string = __version__

        # daemon
        self.nodaemon = False

        # threads sizes
        self.db_thread_pool_size = 1

        # bind port
        self.bind_port = 8082
        # Tor Hidden Service public port
        self.hs_public_port = 80

        # store name
        self.store_name = 'main_store'

        # unhandled Python Exception are reported via mail
        self.error_reporting_username= "stackexception@globaleaks.org"
        self.error_reporting_password= "stackexception99"
        self.error_reporting_server = "box549.bluehost.com"
        self.error_reporting_port = 465
        self.error_reporting_destmail = "stackexception@lists.globaleaks.org"

        # debug defaults
        self.storm_debug = False
        self.cyclone_debug = -1
        self.cyclone_debug_counter = 0
        self.loglevel = "CRITICAL"

        # files and paths
        self.root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        self.working_path = '/var/globaleaks'
        self.static_source = '/usr/share/globaleaks/glbackend'
        self.glclient_path = '/usr/share/globaleaks/glclient'
        self.eval_paths()

        self.receipt_regexp = r'[A-Z]{4}\+[0-9]{5}'

        # list of plugins available in the software
        self.notification_plugins = [
            'MailNotification',
            ]

        # session tracking, in the singleton classes
        self.sessions = dict()

        # value limits in the database
        self.name_limit = 128
        self.description_limit = 1024
        self.generic_limit = 2048
        self.max_file_size = (30 * 1024 * 1024) # 30 Mb

        # static file rules
        self.staticfile_regexp = r'(\w+)\.(\w+)'
        self.staticfile_overwrite = False
        self.reserved_nodelogo_name = "globaleaks_logo" # .png

        # acceptable 'Host:' header in HTTP request
        self.accepted_hosts = "127.0.0.1,localhost"

        # transport security defaults
        #self.tor2web_permitted_ops = {
        #    'admin': False,
        #    'submission': False,
        #    'tip': False,
        #    'receiver': False,
        #    'unauth': True
        #}

        # https://github.com/globaleaks/GlobaLeaks/issues/182
        # we need this settings to permit testing over tor2web
        # transport security defaults
        self.tor2web_permitted_ops = {
            'admin': True,
            'submission': True,
            'tip': True,
            'receiver': True,
            'unauth': True
        }

        # SOCKS default
        self.socks_host = "127.0.0.1"
        self.socks_port = 9050
        self.tor_socks_enable = True

        self.user = getpass.getuser()
        self.group = getpass.getuser()
        self.uid = os.getuid()
        self.gid = os.getgid()
        self.start_clean = False
        self.twistd_log = False
        self.devel_mode = False

        # Expiry time of finalized and not finalized submission,
        # They are copied in a context *when is created*, then
        # changing this variable do not modify the cleaning
        # timings of the existing contexts
        self.tip_seconds_of_life = (3600 * 24) * 15
        self.submission_seconds_of_life = (3600 * 24) * 3
        # enhancement: supports "extended settings in GLCLient"

        # Number of failed login enough to generate an alarm
        self.failed_login_alarm = 5

        # Size in bytes of every log file. Once this size is reached the
        # logfile is rotated.
        # Default: 1M
        self.log_file_size = 1000000
        # Number of log files to conserve.
        self.maximum_rotated_log_files = 100

        # Hidden service address
        self.onion_address = None

    def eval_paths(self):
        self.pidfile_path = os.path.join(self.working_path, 'twistd.pid')
        self.glfiles_path = os.path.abspath(os.path.join(self.working_path, 'files'))
        self.gldb_path = os.path.abspath(os.path.join(self.working_path, 'db'))
        self.log_path = os.path.abspath(os.path.join(self.working_path, 'log'))
        self.cyclone_io_path = os.path.abspath(os.path.join(self.log_path, "jsondump"))
        self.submission_path = os.path.abspath(os.path.join(self.glfiles_path, 'submission'))
        self.static_path = os.path.abspath(os.path.join(self.glfiles_path, 'static'))
        self.static_db_source = os.path.abspath(os.path.join(self.root_path, 'globaleaks', 'db'))
        self.torhs_path = os.path.abspath(os.path.join(self.working_path, 'torhs'))
        self.tor_datadir = os.path.abspath(os.path.join(self.working_path, 'tor'))
        self.db_file = 'sqlite:' + os.path.abspath(os.path.join(self.gldb_path, 'glbackend.db'))
        self.db_schema_file = os.path.join(self.static_db_source,'sqlite.sql')
        self.logfile = os.path.abspath(os.path.join(self.log_path, 'globaleaks.log'))

    def set_devel_mode(self):
        self.working_path = os.path.join(self.root_path, 'workingdir')
        self.static_source = os.path.join(self.root_path, 'staticdata')
        self.glclient_path = os.path.abspath(
            os.path.join(self.root_path, '..', 'GLClient', 'app'))

    def load_cmdline_options(self):
        """
        This function is called by runner.py and operate in cmdline_options,
        interpreted and filled in bin/startglobaleaks script.

        happen in startglobaleaks before the sys.argv is modified
        """
        assert self.cmdline_options is not None

        self.nodaemon = self.cmdline_options.nodaemon

        self.storm_debug = self.cmdline_options.storm_debug

        self.loglevel = verbosity_dict[self.cmdline_options.loglevel]

        if not self.validate_port(self.cmdline_options.port):
            quit(-1)
        self.bind_port = self.cmdline_options.port

        self.cyclone_debug = self.cmdline_options.io

        self.accepted_hosts = self.cmdline_options.host_list.replace(" ", "").split(",")

        self.tor_socks_enable = not self.cmdline_options.disable_tor_socks

        self.socks_host = self.cmdline_options.socks_host

        if not self.validate_port(self.cmdline_options.socks_port):
            quit(-1)
        self.socks_port = self.cmdline_options.socks_port

        if self.tor_socks_enable:
            # convert socks addr in IP and perform a test connection
            self.validate_socks()

        if self.cmdline_options.user:
            self.user = self.cmdline_options.user
            self.uid = pwd.getpwnam(self.cmdline_options.user).pw_uid
        else:
            self.uid = os.getuid()

        if self.cmdline_options.group:
            self.group = self.cmdline_options.group
            self.gid = grp.getgrnam(self.cmdline_options.group).gr_gid
        else:
            self.gid = os.getgid()

        if self.uid == 0 or self.gid == 0:
            print "Invalid user: cannot run as root"
            quit(-1)

        self.twistd_log = self.cmdline_options.twistd_log
        self.start_clean = self.cmdline_options.start_clean

        self.working_path = self.cmdline_options.working_path

        # if devel_mode == True we do some hacks on paths and config values
        self.devel_mode = self.cmdline_options.devel_mode
        if self.devel_mode:
            self.set_devel_mode()

        self.eval_paths()

        # special evaluation of glclient directory:
        indexfile = os.path.join(self.glclient_path, 'index.html')
        if not os.path.isfile(indexfile):
            print "Invalid directory of GLCLient: %s: index.html not found" % self.glclient_path
            quit(-1)

    def validate_port(self, inquiry_port):
        if inquiry_port >= 65535 or inquiry_port < 0:
            print "Invalid port number ( > than 65535 can't work! )"
            return False
        return True

    def validate_socks(self):
        """
        Test connects to the Tor SOCKS Port. If the connection succeeds it
        means that the port is not available, and therefore returns an error
        message and quits.
        """

        testconn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        testconn.setblocking(0)
        testconn.settimeout(1.5) # 1.5 seconds to reach your socks
        try:
            testconn.connect((self.socks_host, self.socks_port))
            print "Selected SOCKS port is already in use!"
            quit(-1)
        except Exception as excep:
            pass


    def create_directories(self):
        """
        Execute some consistency checks on command provided Globaleaks paths

        if one of working_path or static path is created we copy
        here the static files (default logs, and in the future pot files for localization)
        because here stay all the files needed by the application except the python scripts
        """
        new_environment = False

        def create_directory(path):
            # returns false if the directory is already present
            if not os.path.exists(path):
                try:
                    os.mkdir(path)
                    self.log_debug("Created directoy %s" % path)
                    return True
                except OSError as excep:
                    self.log_debug("Error in creating directory: %s (%s)" % (path, excep.strerror))
                    raise excep
            else:
                if not os.path.isdir(path):
                    self.log_debug("Error creating directory: %s (path exists and is not a dir)" % path)
                    raise Exception("Error creating directory: %s (path exists and is not a dir)" % path)
                return False

        if create_directory(self.working_path):
            new_environment = True

        if create_directory(self.gldb_path):
            new_environment = True

        create_directory(self.glfiles_path)

        if create_directory(self.static_path):
            new_environment = True

        create_directory(self.submission_path)
        create_directory(self.log_path)
        create_directory(self.torhs_path)
        create_directory(self.tor_datadir)

        if self.cyclone_debug >= 0:
            create_directory(self.cyclone_io_path)

        # detect new_environment also if the logo is missing
        # XXX may not be right to the Admin. but I'm in bugfixing prerelease :P
        logo_path = os.path.join(self.static_path, "%s.png" % GLSetting.reserved_nodelogo_name)
        if not os.path.isfile(logo_path):
            new_environment = True

        if new_environment:
            almost_one_file = 0
            for path, subpath, files in os.walk(self.static_source):
                almost_one_file += 1
                # REMIND: at the moment are not supported subpaths
                for single_file in files:
                    shutil.copyfile(
                        os.path.join(self.static_source, single_file),
                        os.path.join(self.static_path, single_file)
                    )
            if not almost_one_file:
                print "[Non fatal error] Found empty: %s" % self.static_source
                print "Your instance has not torrc and the default logo"


    def check_directories(self):
        for path in (self.working_path, self.root_path, self.glclient_path,
                     self.glfiles_path, self.static_path, self.submission_path, self.log_path):
            if not os.path.exists(path):
                raise Exception("%s does not exists!" % path)

        # Directory with Write + Read access
        for rdwr in (self.working_path,
                     self.glfiles_path, self.static_path, self.submission_path, self.log_path):
            if not os.access(rdwr, os.W_OK|os.X_OK):
                raise Exception("write capability missing in: %s" % rdwr)

        # Directory in Read access
        for rdonly in (self.root_path, self.glclient_path):
            if not os.access(rdonly, os.R_OK|os.X_OK):
                raise Exception("read capability missing in: %s" % rdonly)

    def remove_directories(self):
        for root, dirs, files in os.walk(self.working_path, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))

    def drop_privileges(self):
        if os.getgid() == 0 or self.cmdline_options.group:
            print "switching group privileges to %d" % self.gid
            os.setgid(GLSetting.gid)
        if os.getuid() == 0 or self.cmdline_options.user:
            print "switching user privileges to %d" % self.uid
            os.setuid(GLSetting.uid)

    def log_debug(self, message):
        """
        Log to stdout only if debug is set at higher levels
        """
        if self.loglevel == logging.DEBUG:
            print message



# GLSetting is a singleton class exported once
GLSetting = GLSettingsClass()

class transact(object):
    """
    Class decorator for managing transactions.
    Because Storm sucks.
    """
    tp = ThreadPool(0, GLSetting.db_thread_pool_size)
    _debug = False

    def __init__(self, method):
        self.store = None
        self.method = method
        self.instance = None

    def __get__(self, instance, owner):
        self.instance = instance
        return self

    def __call__(self,  *args, **kwargs):
        return self.run(self._wrap, self.method, *args, **kwargs)

    @property
    def debug(self):
        """
        Whenever you need to trace the database operation on a specific
        function decorated with @transact, just do:
           function.debug = True
           or either
           self.function.debug = True
           or even
           Class.function.debug = True
        """
        return self._debug

    @debug.setter
    def debug(self, value):
        """
        Setter method for debug property.
        """
        self._debug = value
        tracer.debug(self._debug, sys.stdout)

    @debug.deleter
    def debug(self):
        """
        Deleter method for debug property.
        """
        self.debug = False

    @staticmethod
    def run(function, *args, **kwargs):
        """
        Defer provided function to thread
        """
        return deferToThreadPool(reactor, transact.tp,
                                 function, *args, **kwargs)

    @staticmethod
    def get_store():
        """
        Returns a reference to Storm Store
        """
        zstorm = ZStorm()
        zstorm.set_default_uri(GLSetting.store_name, GLSetting.db_file + '?foreign_keys=ON&journaling_mode=WAL')
        return zstorm.get(GLSetting.store_name)

    def _wrap(self, function, *args, **kwargs):
        """
        Wrap provided function calling it inside a thread and
        passing the store to it.
        """
        self.store = self.get_store()
        try:
            if self.instance:
                result = function(self.instance, self.store, *args, **kwargs)
            else:
                result = function(self.store, *args, **kwargs)
        except (exceptions.IntegrityError, exceptions.DisconnectionError) as ex:
            log.msg(ex)
            transaction.abort()
            result = None
        except HTTPError as excep:
            transaction.abort()
            raise excep
        except Exception as excep:
            transaction.abort()
            _, exception_value, exception_tb = sys.exc_info()
            traceback.print_tb(exception_tb, 10)
            self.store.close()
            # propagate the exception
            raise excep
        else:
            self.store.commit()
        finally:
            self.store.close()

        return result


transact.tp.start()
reactor.addSystemEventTrigger('after', 'shutdown', transact.tp.stop)

