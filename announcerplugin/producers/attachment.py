from trac.core import *
from trac.attachment import IAttachmentChangeListener
from announcerplugin.api import AnnouncementSystem
from announcerplugin.producers.ticket import TicketChangeEvent
from trac.ticket.model import Ticket

class AttachmentChangeProducer(Component):
    implements(IAttachmentChangeListener)
    
    def __init__(self, *args, **kwargs):
        pass

    def attachment_added(self, attachment):
        parent = attachment.resource.parent

        if parent.realm == "ticket":
            ticket = Ticket(self.env, parent.id)
            announcer = AnnouncementSystem(ticket.env)
            announcer.send(
                TicketChangeEvent("ticket", "attachment added", ticket,
                    attachment=attachment, author=attachment.author, 
                )
            )            

    def attachment_deleted(self, attachment):
        # announcer = AnnouncementSystem(ticket.env)
        # announcer.send(
        #     AttachmentChangeEvent(attachment.parent_realm, "attachment added", 
        #         attachment, author=attachment.author, 
        #     )
        # )
        pass