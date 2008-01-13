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

class TicketEmailFormatter(Component):
    implements(IAnnouncementFormatter)
        
    ticket_email_subject = Option('announcer', 'ticket_email_subject', "Ticket #${ticket.id}: ${ticket['summary']}")
    
    def get_format_transport(self):
        return "email"
        
    def get_format_realms(self, transport):
        if transport == "email":
            yield "ticket"
        return
        
    def get_format_styles(self, transport, realm):
        if transport == "email":
            if realm == "ticket":
                yield "text/plain"
                yield "text/html"
                
        return
        
    def get_format_alternative(self, transport, realm, style):
        if transport == "email":
            if realm == "ticket":
                if style == "text/html":
                    return "text/plain"

        return None
        
    def format_headers(self, transport, realm, style, event):
        ticket = event.target
        return dict(
            realm=realm,
            ticket=ticket.id,
            priority=ticket['priority'],
            severity=ticket['severity']            
        )
        
    def format_subject(self, transport, realm, style, event):
        if transport == "email":
            if realm == "ticket":
                template = NewTextTemplate(self.ticket_email_subject)
                return template.generate(ticket=event.target, event=event).render()
                
    def format(self, transport, realm, style, event):
        if transport == "email":
            if realm == "ticket":
                if style == "text/plain":
                    return self._format_plaintext(event)
                elif style == "text/html":
                    return self._format_html(event)

    def _format_plaintext(self, event):
        ticket = event.target
        short_changes = {}
        long_changes = {}
        
        for field, old_value in event.changes.items():
            new_value = ticket[field]
            if ('\n' in new_value) or ('\n' in old_value):
                # long_changes[field.capitalize()] = \
                # '\n'.join(
                #     diff_cleanup(
                #         difflib.context_diff(
                #             old_value.split('\r\n'), new_value.split('\r\n'),
                #             lineterm='', n=2
                #         )
                #     )
                # )
                long_changes[field.capitalize()] = '\n'.join(
                    lineup(
                        wrap(new_value, cols=67).split('\n')
                    )
                )
            else:
                short_changes[field.capitalize()] = (old_value, new_value)
        
        data = dict(
            ticket = ticket,
            author = event.author,
            comment = event.comment,
            category = event.category,
            ticket_link = self.env.abs_href('ticket', ticket.id),
            project_name = self.env.project_name,
            project_desc = self.env.project_description,
            project_link = self.env.project_url,
            has_changes = short_changes or long_changes,
            long_changes = long_changes,
            short_changes = short_changes,
            attachment= event.attachment
        )
        
        chrome = Chrome(self.env)        
        dirs = []
        for provider in chrome.template_providers:
            dirs += provider.get_templates_dirs()

        templates = TemplateLoader(dirs, variable_lookup='lenient')

        template = templates.load('ticket_email_plaintext.txt', cls=NewTextTemplate)

        if template:
            stream = template.generate(**data)
            output = stream.render('text')

        return output
        
    def _format_html(self, event):
        ticket = event.target
        short_changes = {}
        long_changes = {}
        chrome = Chrome(self.env)        
        
        for field, old_value in event.changes.items():
            new_value = ticket[field]
            if ('\n' in new_value) or ('\n' in old_value):
                long_changes[field.capitalize()] = HTML(
                    "<pre>\n%s\n</pre>" % (
                        '\n'.join(
                            diff_cleanup(
                                difflib.unified_diff(
                                    wrap(old_value, cols=60).split('\n'), 
                                    wrap(new_value, cols=60).split('\n'),
                                    lineterm='', n=3
                                )
                            )
                        )
                    )
                )

            else:
                short_changes[field.capitalize()] = (old_value, new_value)

        data = dict(
            ticket = ticket,
            author = event.author,
            comment = event.comment,
            category = event.category,
            ticket_link = self.env.abs_href('ticket', ticket.id),
            project_name = self.env.project_name,
            project_desc = self.env.project_description,
            project_link = self.env.project_url,
            has_changes = short_changes or long_changes,
            long_changes = long_changes,
            short_changes = short_changes,
            attachment= event.attachment            
        )
        
        output = chrome.render_template(None, "ticket_email_mimic.html", data, content_type="text/html", fragment = True)
        
        return output.render()
