from trac.core import *
from trac.ticket.api import ITicketChangeListener
from announcerplugin.api import AnnouncementSystem, AnnouncementEvent

class TicketChangeEvent(AnnouncementEvent):
    def __init__(self, realm, category, target, 
                 comment=None, author=None, changes=None):
        AnnouncementEvent.__init__(self, realm, category, target)

        self.author = author
        self.comment = comment
        self.changes = changes

class TicketChangeProducer(Component):
    implements(ITicketChangeListener)
    
    def __init__(self, *args, **kwargs):
        pass
        
    def ticket_created(self, ticket):
        announcer = AnnouncementSystem(ticket.env)
        announcer.send(
            TicketChangeEvent("ticket", "created", ticket,
                author=ticket['reporter']
            )
        )
        
    def ticket_changed(self, ticket, comment, author, old_values):
        announcer = AnnouncementSystem(ticket.env)
        announcer.send(
            TicketChangeEvent("ticket", "changed", ticket, 
                comment, author, old_values
            )
        )

    def ticket_deleted(self, ticket):
        pass
    
