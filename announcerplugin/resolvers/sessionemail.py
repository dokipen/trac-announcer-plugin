from trac.core import Component, implements
from trac.util.compat import sorted

from announcerplugin.api import IAnnouncementAddressResolver

class SessionEmailResolver(Component):
    implements(IAnnouncementAddressResolver)
    
    def get_address_for_name(self, name):
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT value, authenticated
              FROM session_attribute
             WHERE sid=%s
               AND name=%s
        """, (sid, 'email'))
                
        for record in sorted(cursor.fetchall(), key=lambda x: x[1]):
            return record[0]
            
        return None