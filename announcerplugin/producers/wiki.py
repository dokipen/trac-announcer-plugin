from trac.core import *
from trac.config import BoolOption
from trac.wiki.api import IWikiChangeListener
from announcerplugin.api import AnnouncementSystem, AnnouncementEvent

class WikiChangeEvent(AnnouncementEvent):
    def __init__(self, realm, category, target, 
                 comment=None, author=None, version=None, 
                 timestamp=None, remote_addr=None):
        AnnouncementEvent.__init__(self, realm, category, target)

        self.author = author
        self.comment = comment
        self.version = version
        self.timestamp = timestamp
        self.remote_addr = remote_addr

class WikiChangeProducer(Component):
    implements(IWikiChangeListener)
    
    def wiki_page_added(self, page):
        pass
        
    def wiki_page_changed(self, page, version, t, comment, author, ipnr):
        print "PAGE NAME", page.name
        announcer = AnnouncementSystem(page.env)
        announcer.send(
            WikiChangeEvent("wiki", "changed", page,
                comment=comment, author=author, version=version,
                timestamp=t, remote_addr=ipnr
            )
        )
        
    def wiki_page_deleted(page):
        """Called when a page has been deleted."""

    def wiki_page_version_deleted(page):
        """Called when a version of a page has been deleted."""
                
