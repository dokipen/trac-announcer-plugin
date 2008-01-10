from trac.core import Component, implements
from announcerplugin.api import IAnnouncementFormatter
from trac.config import Option, IntOption

class TicketEmailFormatter(Component):
    implements(IAnnouncementFormatter)
    
    default_email_format = Option('announcer', 'default_email_format', 'plaintext')
    
    def get_format_scheme(self):
        return "email"
        
    def get_format_realms(self, perspective):
        if perspective == "email":
            yield "ticket"
        return
        
    def get_format_styles(self, perspective, realm):
        if perspective == "email":
            if realm == "ticket":
                yield "plaintext"
                yield "html"
                
        return

    def format(self, scheme, realm, style, event):
        if realm == "ticket":
            if hasattr(self, '_format_%s' % style):
                return getattr(self, '_format_%s' % style)(event)
        
    def _format_plaintext(self, event):
        return "PLAIN -\n\t%s\n\t%s\n\t%s" % (event.author, event.comment, event.changes)
        
    def _format_html(self, event):
        return "HTML -\n\t%s\n\t%s\n\t%s" % (event.author, event.comment, event.changes)
        
    def _get_format(self, sid):
        db = self.env.get_db_cnx()
        cursor = db.cursor()

        cursor.execute("""
            SELECT value 
              FROM session_attribute
             WHERE sid=%s
               AND authenticated=1
               AND name=%s
        """, (sid, 'announcer_email_format_ticket'))

        result = cursor.fetchone()
        if result:
            r = result[0]
            self.log.debug("TicketEmailFormatter fetched email format preference from '%s' as: %s" % (sid, r))
            return r

        return self.default_email_format