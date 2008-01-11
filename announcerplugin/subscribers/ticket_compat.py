from trac.core import Component, implements
from announcerplugin.api import IAnnouncementSubscriber, IAnnouncementPreferenceProvider, istrue
from trac.ticket import model
from trac.web.chrome import add_warning
from trac.config import BoolOption

class StaticTicketSubscriber(Component):
    """The static ticket subscriber implements a policy to -always- send an email to a
    certain address. Controlled via the smtp_always_bcc option in the announcer
    section of the trac.ini"""
    
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
        
    def check_event(self, event):
        self.log.debug("StaticTicketSubscriber added '%s' because of rule: smtp_always_bcc" % self.bcc)
        yield ('email', None, self.bcc)

class LegacyTicketSubscriber(Component):
    implements(IAnnouncementSubscriber, IAnnouncementPreferenceProvider)
    
    always_notify_owner = BoolOption("announcer", "always_notify_owner", False, 
        """The always_notify_owner option mimics the option of the same name in the
        notification section, except users can opt-out in their preferences. Used
        only if LegacyTicketSubscriber is enabled.""")

    always_notify_reporter = BoolOption("announcer", "always_notify_reporter", False, 
        """The always_notify_reporter option mimics the option of the same name in the
        notification section, except users can opt-out in their preferences. Used
        only if LegacyTicketSubscriber is enabled.""")

    always_notify_updater = BoolOption("announcer", "always_notify_updater", False, 
        """The always_notify_updater option mimics the option of the same name in the
        notification section, except users can opt-out in their preferences. Used
        only if LegacyTicketSubscriber is enabled.""")
        
    def get_announcement_preference_boxes(self, req):
        yield "legacy", "Legacy Notification (Opt-Out)"

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
                sess['announcer_legacy_notify_owner'] = req.args.get('legacy_notify_owner', False)
            if always_notify_reporter:
                sess['announcer_legacy_notify_reporter'] = req.args.get('legacy_notify_reporter', False)
            if always_notify_updater:
                sess['announcer_legacy_notify_updater'] = req.args.get('legacy_notify_updater', False)
        
        data = dict(
            always_notify_owner = always_notify_owner,
            always_notify_reporter = always_notify_reporter,
            always_notify_updater = always_notify_updater,
            legacy_notify_owner = istrue(sess.get('announcer_legacy_notify_owner', True), None),
            legacy_notify_reporter = istrue(sess.get('announcer_legacy_notify_reporter', True), None),
            legacy_notify_updater = istrue(sess.get('announcer_legacy_notify_updater', True), None),
        )
        
        return "prefs_announcer_legacy.html", data

    def get_subscription_realms(self):
        return ('ticket',)
        
    def get_subscription_categories(self, realm):
        if realm == 'ticket':
            return ('created', 'changed')
        else:
            return tuple()
            
    def get_subscriptions_for_event(self, event):
        if event.realm == "ticket":
            ticket = event.target
            if event.category == "created":
                component = model.Component(self.env, ticket['component'])
                if component.owner:
                    ## TODO: Is this an option?
                    self.log.debug("LegacyTicketSubscriber added '%s' because of rule: component owner" % (component.owner,))
                    yield ('email', component.owner, None)
                                    
            elif event.category == "changed":
                if self.always_notify_owner and not self._check_opt_out('notify_owner', ticket['owner']):                   
                    self.log.debug("LegacyTicketSubscriber added '%s' because of rule: always_notify_owner" % ticket['owner'])
                    yield ('email', ticket['owner'], None)
                    
                if self.always_notify_reporter and not self._check_opt_out('notify_reporter', ticket['reporter']):
                    self.log.debug("LegacyTicketSubscriber added '%s' because of rule: always_notify_reporter" % ticket['reporter'])
                    yield ('email', ticket['reporter'], None)
                    
                if self.always_notify_updater and not self._check_opt_out('notify_updater', event.author):
                    self.log.debug("LegacyTicketSubscriber added '%s' because of rule: always_notify_updater" % event.author)
                    yield ('email', event.author, None)
        return
        
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
            r = result[0] == '0'
            self.log.debug("LegacyTicketSubscriber excluded '%s' because of opt-out rule: %s" % (sid,preference))
            return r
        
        return False

class CarbonCopySubscriber(Component):
    implements(IAnnouncementSubscriber)
    
    def get_subscription_realms(self):
        return ('ticket',)
        
    def get_subscription_categories(self, *args):
        return ('changed', )
        
    def check_event(self, event):
        if event.realm == 'ticket':
            if event.category == 'changed':
                cc = event.target['cc']
                for chunk in cc.split(','):
                    if '@' in chunk:
                        address = chunk.strip()
                        name = None
                    else:
                        name = chunk.strip()
                        address = None
                    if name or address:
                        self.log.debug("CarbonCopySubscriber added '%s <%s>' because of rule: carbon copied" % (name,address))
                        yield ('email', name, address)