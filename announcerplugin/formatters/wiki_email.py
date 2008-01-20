from trac.core import Component, implements
from announcerplugin.api import IAnnouncementFormatter
from trac.config import Option, IntOption
from genshi.template import NewTextTemplate, MarkupTemplate
from genshi import HTML
from trac.web.href import Href
from trac.web.chrome import Chrome
from genshi.template import TemplateLoader
from trac.util.text import wrap
from trac.versioncontrol.diff import diff_blocks
import difflib

def diff_cleanup(gen):
    for value in gen:
        if value.startswith('---'):
            continue
        
        if value.startswith('+++'):
            continue
            
        if value.startswith('@@'):
            yield '\n'
        else:
            yield value

def lineup(gen):
    for value in gen:
        yield ' ' + value

class WikiEmailFormatter(Component):
    implements(IAnnouncementFormatter)
        
    wiki_email_subject = Option('announcer', 'wiki_email_subject', "Page: ${page.name} ${action}")
    
    def get_format_transport(self):
        return "email"
        
    def get_format_realms(self, transport):
        if transport == "email":
            yield "wiki"
        return
        
    def get_format_styles(self, transport, realm):
        if transport == "email":
            if realm == "wiki":
                yield "text/plain"
                
        return
        
    def get_format_alternative(self, transport, realm, style):
        # if transport == "email":
        #     if realm == "ticket":
        #         if style == "text/html":
        #             return "text/plain"

        return None
        
    def format_headers(self, transport, realm, style, event):
        return {}
        # ticket = event.target
        # return dict(
        #     realm=realm,
        #     ticket=ticket.id,
        #     priority=ticket['priority'],
        #     severity=ticket['severity']            
        # )
        
    def format_subject(self, transport, realm, style, event):
        if transport == "email":
            if realm == "wiki":
                template = NewTextTemplate(self.wiki_email_subject)
                return template.generate(page=event.target, event=event, action=event.category).render()
                
    def format(self, transport, realm, style, event):
        if transport == "email":
            if realm == "wiki":
                if style == "text/plain":
                    return self._format_plaintext(event)
                # elif style == "text/html":
                #     return self._format_html(event)

    def _format_plaintext(self, event):
        page = event.target
        data = dict(
            action = event.category,
            page = page,
            author = event.author,
            comment = event.comment,
            category = event.category,
            page_link = self.env.abs_href('wiki', page.name),
            project_name = self.env.project_name,
            project_desc = self.env.project_description,
            project_link = self.env.project_url,
        )
        
        if page.version:
            data["changed"] = True
            data["diff_link"] = self.env.abs_href('wiki', page.name, action="diff", version=page.version)
            
        
        chrome = Chrome(self.env)        
        dirs = []
        for provider in chrome.template_providers:
            dirs += provider.get_templates_dirs()
            
        templates = TemplateLoader(dirs, variable_lookup='lenient')
        
        template = templates.load('wiki_email_plaintext.txt', cls=NewTextTemplate)
        
        if template:
            stream = template.generate(**data)
            output = stream.render('text')
            
        return output
        