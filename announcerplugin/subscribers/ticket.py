from trac.core import Component, implements, TracError
from announcerplugin.api import IAnnouncementSubscriber


class RuleBasedTicketSubscriber(Component):
    
    implements(IAnnouncementSubscriber)
    
    def get_subscription_realms(self):
        return ('ticket', )
        
    def get_subscription_categories(self, realm):
        return ('created', 'changed')
        
    def check_event(self, event):
        return
        yield
        # db = self.env.get_db_cnx()
        # cursor = db.cursor()
        # 
        # cursor.execute("""
        #     SELECT sid, rule, destination, format
        #       FROM subscriptions
        #      WHERE realm=%s,
        #        AND category=%s,
        #        AND enabled=1
        #        AND managed=0
        # """, (event.realm, event.category))
        
        
        