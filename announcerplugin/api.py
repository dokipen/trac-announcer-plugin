from trac.core import *
from trac.util.compat import set
from trac.db import Table, Column, Index
from trac.env import IEnvironmentSetupParticipant

class IAnnouncementSubscriber(Interface):
    """IAnnouncementSubscriber provides an interface where a Plug-In can 
    register realms and categories of subscriptions it is able to provide. 
    
    An IAnnouncementSubscriber component can use any means to determine 
    if a user is interested in hearing about a given event. More then one
    component can handle the same realms and categories."""

    def get_subscription_realms():
        """Yields a list of realms that it is able to handle
        subscriptions for."""

    def get_subscription_categories(realm):
        """Yields a list of realms that it is able to handle
        subscriptions for."""


    def check_event(event):
        """Yields a list of subscriptions that are interested in the 
        specified event.

        Each subscription that is returned is in the form of:
            ('method', 'username', 'format')

        The method should correspond to a distribution method that is
        provided by an IAnnouncementDistributor component. The
        destination itself varies depending on the method; if the 
        method is 'email', the destination will be an email address.
        """
        
class IAnnouncementFormatter(Interface):
    def get_format_scheme():
        """email"""
        
    def get_format_realms(scheme):
        """Yields a list of realms."""
        
    def get_format_styles(scheme, realm):
        """Yields a list of (format, weight)"""

    def format(format, event):
        """Returns the event rendered according to the appropriate 
        method.
        """
        
class IAnnouncementDistributor(Interface):
    def get_distribution_scheme():
        """Yields a list of methods that this distributor knows how
        to use to deliver an event announcement.
        """

    def distribute(destinations, message):
        """Distributes an actual message."""
        
class IAnnouncementPreferenceProvider(Interface):
    def get_announcement_preference_boxes(req):
        """Returns (name, label)"""
        
    def render_announcement_preference_box(req, panel):
        """Returns (template, data)"""
       
class IAnnouncementAddressResolver(Interface):
    def get_address_for_name(name):
        """Returns an address or name."""
        
class AnnouncementEvent(object):
    def __init__(self, realm, category, target):
        self.realm = realm
        self.category = category
        self.target = target
                
_TRUE_VALUES = ('yes', 'true', 'enabled', 'on', 'aye', '1', 1, True)

def istrue(value, otherwise=False):
    return True and (value in _TRUE_VALUES) or otherwise

class AnnouncementSystem(Component):
    
    implements(IEnvironmentSetupParticipant)
        
    subscribers = ExtensionPoint(IAnnouncementSubscriber)
    distributors = ExtensionPoint(IAnnouncementDistributor)

    # IEnvironmentSetupParticipant implementation
    SCHEMA = [
        Table('subscriptions', key='id')[
            Column('id', auto_increment=True),
            Column('sid'),
            Column('enabled', type='int'),
            Column('managed', type='int'),
            Column('realm'),
            Column('category'),
            Column('rule'),
            Column('destination'),
            Column('format'),
            Index(['id']),
            Index(['realm', 'category', 'enabled']),
        ]
    ]

    def environment_created(self):
        self._upgrade_db(self.env.get_db_cnx())

    def environment_needs_upgrade(self, db):
        cursor = db.cursor()

        try:
            cursor.execute("select count(*) from subscriptions")
            cursor.fetchone()
            return False
        except:
            db.rollback()
            return True

    def upgrade_environment(self, db):
        self._upgrade_db(db)

    def _upgrade_db(self, db):
        try:
            from trac.db import DatabaseManager
            db_backend, _ = DatabaseManager(self.env)._get_connector()            

            cursor = db.cursor()
            for table in self.SCHEMA:
                for stmt in db_backend.to_sql(table):
                    self.log.debug(stmt)
                    cursor.execute(stmt)

        except Exception, e:
            db.rollback()
            self.log.error(e, exc_info=True)
            raise TracError(str(e))
            
    # The actual AnnouncementSystem now..    

    def send(self, evt):
        supported_subscribers = []
        for sp in self.subscribers:
            categories = sp.get_subscription_categories(evt.realm)
            if ('*' in categories) or (evt.category in categories):
                supported_subscribers.append(sp)
        
        self.log.debug(
            "AnnouncementSystem found the following subscribers capable of "
            "handling '%s, %s': %s" % (evt.realm, evt.category, 
            ', '.join([ss.__class__.__name__ for ss in supported_subscribers]))
        )
        
        subscriptions = set()
        for sp in supported_subscribers:
            subscriptions.update(
                x for x in sp.check_event(evt) if x
            )
        
        self.log.debug(
            "AnnouncementSystem has found the following subscriptions: %s" % (
                ', '.join(
                    ['(%s via %s)' % ((s[1] or s[2]), s[0]) for s in subscriptions]
                )
            )
        )
        
        packages = {}
        for scheme, target, address in subscriptions:
            if scheme not in packages:
                packages[scheme] = set()
            
            packages[scheme].add((target,address))
            
        for distributor in self.distributors:
            scheme = distributor.get_distribution_scheme()
            if scheme in packages:
                distributor.distribute(scheme, packages[scheme], evt)
        
        return