from trac.core import Component, implements
from announcerplugin.api import IAnnouncementSubscriber, istrue
from announcerplugin.api import IAnnouncementPreferenceProvider
from trac.ticket import model
from trac.web.chrome import add_warning
from trac.config import BoolOption
import re
from trac.resource import ResourceNotFound
from trac.util.text import to_unicode

class StaticTicketSubscriber(Component):
    """The static ticket subscriber implements a policy to -always- send an 
    email to a certain address. Controlled via the smtp_always_bcc option in 
    the announcer section of the trac.ini"""
    
    implements(IAnnouncementSubscriber)
    
    def __init__(self):
        bcc = self.config.get('announcer', 'smtp_always_bcc')
        if bcc:
            self._returnval = ('*', )
            self.bcc = bcc
        else:
            self._returnval = tuple()
            
    def get_subscription_realms(self):
        self._returnval
        
    def get_subscription_categories(self, realm):
        return self._returnval
        
    def get_subscriptions_for_event(self, event):
        self.log.debug("StaticTicketSubscriber added '%s' because of rule: " \
                "smtp_always_bcc" % self.bcc)
        yield ('email', None, False, self.bcc)

class LegacyTicketSubscriber(Component):
    implements(IAnnouncementSubscriber, IAnnouncementPreferenceProvider)
    
    always_notify_owner = BoolOption("announcer", "always_notify_owner", False, 
        """The always_notify_owner option mimics the option of the same name 
        in the notification section, except users can opt-out in their 
        preferences. Used only if LegacyTicketSubscriber is enabled.""")

    always_notify_reporter = BoolOption("announcer", "always_notify_reporter", 
        False, """The always_notify_reporter option mimics the option of the 
        same name in the notification section, except users can opt-out in 
        their preferences. Used only if LegacyTicketSubscriber is enabled.""")

    always_notify_updater = BoolOption("announcer", "always_notify_updater", 
        False, """The always_notify_updater option mimics the option of the 
        same name in the notification section, except users can opt-out in 
        their preferences. Used only if LegacyTicketSubscriber is enabled.""")

    always_notify_component_owner = BoolOption("announcer", 
            "always_notify_component_owner", True,
            """Whether or not to notify the owner of the ticket's 
            component.""")
        
    def get_announcement_preference_boxes(self, req):
        yield "legacy", "Ticket Notifications"

    def render_announcement_preference_box(self, req, panel):
        cfg = self.config
        sess = req.session
        always_notify_owner = istrue(
            cfg.get('announcer', 'always_notify_owner', None)
        )
        always_notify_reporter = istrue(
            cfg.get('announcer', 'always_notify_reporter', None)
        )
        always_notify_updater = istrue(
            cfg.get('announcer', 'always_notify_updater', None)
        )
        if req.method == "POST":
            if always_notify_owner:
                sess['announcer_legacy_notify_owner'] = to_unicode(
                        req.args.get('legacy_notify_owner', 0))
            if always_notify_reporter:
                sess['announcer_legacy_notify_reporter'] = to_unicode(
                        req.args.get('legacy_notify_reporter', 0))
            if always_notify_updater:
                sess['announcer_legacy_notify_updater'] = to_unicode(
                        req.args.get('legacy_notify_updater', 0))
        data = dict(
            always_notify_owner = always_notify_owner,
            always_notify_reporter = always_notify_reporter,
            always_notify_updater = always_notify_updater,
            legacy_notify_owner = istrue(sess.get(
                'announcer_legacy_notify_owner', True), None),
            legacy_notify_reporter = istrue(sess.get(
                'announcer_legacy_notify_reporter', True), None),
            legacy_notify_updater = istrue(sess.get(
                'announcer_legacy_notify_updater', True), None),
        )
        return "prefs_announcer_legacy.html", data

    def get_subscription_realms(self):
        return ('ticket',)
        
    def get_subscription_categories(self, realm):
        if realm == 'ticket':
            return ('created', 'changed', 'attachment added')
        else:
            return tuple()

    def get_subscriptions_for_event(self, event):
        if event.realm != "ticket":
            return
        if not event.category in ('created', 'changed', 'attachment added'):
            return
        ticket = event.target
        for s in self._always_notify_component_owner(ticket):
            yield s
        for s in self._always_notify_ticket_owner(ticket):
            yield s
        for s in self._always_notify_ticket_reporter(ticket): 
            yield s
        for s in self._always_notify_ticket_updater(event, ticket): 
            yield s

    def _always_notify_component_owner(self, ticket):
        if not self.always_notify_component_owner:
            return
        try:
            component = model.Component(self.env, ticket['component'])
            if component.owner:
                self.log.debug("LegacyTicketSubscriber added " \
                        "'%s' because of rule: always_notify_component_owner" \
                        % (component.owner,))
                yield ('email', component.owner, True, None)
        except ResourceNotFound, message:
            self.log.warn("LegacyTicketSubscriber couldn't add " \
                    "component owner because component was not found, " \
                    "message: '%s'"%(message,))    

    def _always_notify_ticket_owner(self, ticket):
        if not self.always_notify_owner or not ticket['owner'] or \
            self._check_opt_out('notify_owner', ticket['owner']):                   
            return
        owner = ticket['owner']
        if '@' in owner:
            name, authenticated, address = None, False, owner
        else:
            name, authenticated, address = owner, True, None
        self.log.debug(
            "LegacyTicketSubscriber added '%s (%s)' because of rule: " \
                "always_notify_owner"%(owner, authenticated and \
                'authenticated' or 'not authenticated'))
        yield ('email', name, authenticated, address)
        
    def _always_notify_ticket_reporter(self, ticket):
        if not self.always_notify_reporter or not ticket['reporter'] or \
            self._check_opt_out('notify_reporter', ticket['reporter']):
            return
        reporter = ticket['reporter']
        if '@' in reporter:
            name, authenticated, address = None, False, reporter
        else:
            name, authenticated, address = reporter, True, None
        self.log.debug(
            "LegacyTicketSubscriber added '%s (%s)' because of rule: " \
                "always_notify_reporter"%(reporter, authenticated and \
                'authenticated' or 'not authenticated'))
        yield ('email', name, authenticated, address)

    def _always_notify_ticket_updater(self, event, ticket):
        if not self.always_notify_updater or not event.author or \
            self._check_opt_out('notify_updater', event.author):
            return
        self.log.debug("LegacyTicketSubscriber added '%s " \
                "(authenticated)' because of rule: " \
                "always_notify_updater"%event.author)
        yield ('email', event.author, True, None)
        
    def _check_opt_out(self, preference, sid):
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            SELECT value 
              FROM session_attribute
             WHERE sid=%s
               AND authenticated=1
               AND name=%s
        """, (sid, 'announcer_legacy_' + preference))
        result = cursor.fetchone()
        if result:
            optout = (result[0] == '0')
            if optout:
                self.log.debug("LegacyTicketSubscriber excluded '%s' " \
                        "because of opt-out rule: %s" % (sid,preference))
                return True
        return False

class CarbonCopySubscriber(Component):
    implements(IAnnouncementSubscriber)
    
    def get_subscription_realms(self):
        return ('ticket',)
        
    def get_subscription_categories(self, realm):
        if realm == 'ticket':
            return ('created', 'changed', 'attachment added')
        else:
            return tuple()
        
    def get_subscriptions_for_event(self, event):
        if event.realm == 'ticket':
            if event.category in ('created', 'changed', 'attachment added'):
                cc = event.target['cc']
                for chunk in re.split('\s|,', cc):
                    chunk = chunk.strip()
                    if not chunk or chunk.startswith('@'):
                        continue
                    if '@' in chunk:
                        address = chunk
                        name = None
                    else:
                        name = chunk
                        address = None
                    if name or address:
                        self.log.debug("CarbonCopySubscriber added '%s <%s>'" \
                            " because of rule: carbon copied" % (name,address))
                        yield ('email', name, name and True or False, address)
        
