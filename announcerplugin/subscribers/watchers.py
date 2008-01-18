import re
from trac.core import *
from trac.config import ListOption
from trac.web.api import IRequestFilter, IRequestHandler, Href
from trac.web.chrome import ITemplateProvider, add_ctxtnav, add_stylesheet, \
                            add_script
from trac.resource import get_resource_url
from trac.ticket.api import ITicketChangeListener
from trac.wiki.api import IWikiChangeListener
from genshi.builder import tag
from announcerplugin.api import IAnnouncementSubscriber

class WatchSubscriber(Component):

    implements(IRequestFilter, IRequestHandler, IAnnouncementSubscriber,
        ITicketChangeListener, IWikiChangeListener)

    watchable_paths = ListOption('announcer', 'watchable_paths', '/,/wiki*,/ticket*',
        doc='List of URL paths to allow voting on. Globs are supported.')

    path_match = re.compile(r'/watch/(.*)')

    # IRequestHandler methods
    def match_request(self, req):
        if self.path_match.match(req.path_info):
            realm = self.normalise_resource(req.path_info).split('/')[1]
            return "%s_VIEW" % realm.upper() in req.perm
            
        return False

    def process_request(self, req):
        match = self.path_match.match(req.path_info)
        resource = self.normalise_resource(match.groups()[0])
        realm, _ = resource.split('/', 1)
        req.perm.require('%s_VIEW' % realm.upper())
        
        self.toggle_watched(req.session.sid, not req.authname == 'anonymous', resource, req)

        req.redirect(req.href(resource))

    def toggle_watched(self, sid, authenticated, resource, req=None):
        realm, resource = resource.split('/', 1)
        
        if self.is_watching(sid, authenticated, realm, resource):
            self.set_unwatch(sid, authenticated, realm, resource)
            self._schedule_notice(req, 'You are no longer watching this resource for changes.')
        else:
            self.set_watch(sid, authenticated, realm, resource)
            self._schedule_notice(req, 'You are now watching this resource for changes.')
            
    def _schedule_notice(self, req, message):
        req.session['_announcer_watch_message_'] = message
                    
    def _add_notice(self, req):
        if '_announcer_watch_message_' in req.session:

            # This is temporary during 0.11b1 as add_notice was added later 
            # for the final 0.11 release.
            try: 
                from trac.web.chrome import add_notice
            except:
                from trac.web.chrome import add_warning as add_notice
            
            add_notice(req, req.session['_announcer_watch_message_'])
            del req.session['_announcer_watch_message_']
                    
    def is_watching(self, sid, authenticated, realm, resource):
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT id
              FROM subscriptions
             WHERE sid=%s AND authenticated=%s
               AND enabled=1 AND managed=%s
               AND realm=%s
               AND category=%s
               AND rule=%s
        """, (sid, authenticated and 1 or 0, 'watcher', realm, 'changed', resource))
        
        result = cursor.fetchone()
        if result:
            return True
        else:
            return False
    
    def set_watch(self, sid, authenticated, realm, resource):
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        
        self.set_unwatch(sid, authenticated, realm, resource, use_db=db)

        cursor.execute("""
            INSERT INTO subscriptions
                        (sid, authenticated, 
                         enabled, managed, 
                         realm, category, 
                         rule, transport)
                 VALUES
                        (%s, %s, 
                         1, %s, 
                         %s, %s,
                         %s, %s)
        """, (
                sid, authenticated, 
                'watcher', realm, '*', 
                resource, 'email'
            )
        )
        
        db.commit()
        
    def set_unwatch(self, sid, authenticated, realm, resource, use_db=None):
        if not use_db:
            db = self.env.get_db_cnx()
        else:
            db = use_db
            
        cursor = db.cursor()

        cursor.execute("""
            DELETE
              FROM subscriptions
             WHERE sid=%s AND authenticated=%s
               AND enabled=1 AND managed=%s
               AND realm=%s
               AND category=%s
               AND rule=%s
        """, (sid, authenticated, 'watcher', realm, 'changed', resource))
        
        if not use_db:
            db.commit()
            
    # IRequestFilter methods
    def pre_process_request(self, req, handler):
        self._add_notice(req)
        
        if req.authname != "anonymous":
            for path in self.watchable_paths:
                if re.match(path, req.path_info):
                    if req.path_info == '/':
                        realm = 'wiki'
                    else:
                        realm, _ = self.normalise_resource(req.path_info).split('/', 1)
    
                    if '%s_VIEW' % realm.upper() not in req.perm:
                        return handler
                    
                    self.render_watcher(req)
                    break

        return handler

    def post_process_request(self, req, template, data, content_type):
        return (template, data, content_type)

    # Internal methods
    def render_watcher(self, req):
        if req.path_info == '/':
            resource = 'WikiStart'
            realm = 'wiki'
        else:
            resource = self.normalise_resource(req.path_info)
            realm, resource = resource.split('/', 1)
                
        if self.is_watching(req.session.sid, not req.authname == 'anonymous', realm, resource):
            action_name = "Unwatch This"
        else:
            action_name = "Watch This"
                
        add_ctxtnav(req, 
                tag.a(
                    action_name, href=req.href.watch(realm, resource)
                )
        )

    def normalise_resource(self, resource):
        if isinstance(resource, basestring):
            resource = resource.strip('/')
            # Special-case start page
            if resource == 'wiki':
                resource += '/WikiStart'
            return resource
        return get_resource_url(self.env, resource, Href('')).strip('/')
        
    # IWikiChangeListener
    def wiki_page_added(self, page):
        pass
        
    def wiki_page_changed(self, page, version, t, comment, author, ipnr):
        pass
        
    def wiki_page_deleted(page):
        db = self.env.get_db_cnx()

        cursor = db.cursor()

        cursor.execute("""
            DELETE
              FROM subscriptions
             WHERE managed=%s
               AND realm=%s
               AND rule=%s
        """, ('watcher', 'wiki', page.name))

        db.commit()

    def wiki_page_version_deleted(page):
        pass

    # ITicketChangeListener
    
    def ticket_created(self, ticket):
        pass
        
    def ticket_changed(self, ticket, comment, author, old_values):
        pass
        
    def ticket_deleted(self, ticket):
        db = self.env.get_db_cnx()

        cursor = db.cursor()

        cursor.execute("""
            DELETE
              FROM subscriptions
             WHERE managed=%s
               AND realm=%s
               AND rule=%s
        """, ('watcher', 'ticket', ticket.id))

        db.commit()
    
    # IAnnouncementSubscriber    

    def get_subscription_realms(self):
        return ('wiki', 'ticket')
        
    def get_subscription_categories(self, realm):
        return ('created', 'changed', 'attachment added')
        
    def get_subscriptions_for_event(self, event):
        if event.realm in self.get_subscription_realms():
            if event.category in self.get_subscription_categories(event.realm):
                db = self.env.get_db_cnx()
                cursor = db.cursor()
                
                cursor.execute("""
                    SELECT transport, sid
                      FROM subscriptions
                     WHERE enabled=1 AND managed=%s
                       AND realm=%s
                       AND category=%s
                       AND rule=%s
                """, ('watcher', event.realm, 'changed', self._get_target_identifier(event.realm, event.target)))
            
                for transport, sid in cursor.fetchall():
                    self.log.debug("WatchSubscriber added '%s' because of rule: watched" % (sid,))
                    yield (transport, sid, None)
                    
    def _get_target_identifier(self, realm, target):
        if realm == "wiki":
            return target.name
        elif realm == "ticket":
            return target.id