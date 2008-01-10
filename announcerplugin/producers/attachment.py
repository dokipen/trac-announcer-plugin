from trac.core import *
from trac.attachment import IAttachmentChangeListener
from announcerplugin.api import AnnouncementSystem, AnnouncementEvent

class AttachmentChangeEvent(AnnouncementEvent):
    def __init__(self, realm, category, target, 
                 author=None):
        AnnouncementEvent.__init__(self, realm, category, target)

        self.author = author
                
class AttachmentChangeProducer(Component):
    implements(IAttachmentChangeListener)
    
    def __init__(self, *args, **kwargs):
        pass

    def attachment_added(self, attachment):
        announcer = AnnouncementSystem(ticket.env)
        announcer.send(
            AttachmentChangeEvent(attachment.parent_realm, "attachment added",
                attachment, author=attachment.author, 
            )
        )            

    def attachment_deleted(self, attachment):
        announcer = AnnouncementSystem(ticket.env)
        announcer.send(
            AttachmentChangeEvent(attachment.parent_realm, "attachment added", 
                attachment, author=attachment.author, 
            )
        )