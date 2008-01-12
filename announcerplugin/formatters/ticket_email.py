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
    
    default_email_format = Option('announcer', 'default_email_format', 'plaintext')
    
    def get_format_transport(self):
        return "email"
        
    def get_format_realms(self, transport):
        if transport == "email":
            yield "ticket"
        return
        
    def get_format_styles(self, transport, realm):
        if transport == "email":
            if realm == "ticket":
                yield "plaintext"
                yield "html"
                
        return

    def format(self, transport, realm, style, event):
        if realm == "ticket":
            if hasattr(self, '_format_%s' % style):
                return getattr(self, '_format_%s' % style)(event)

    def _load_text_template(self, chrome, filename):
        # print 'Load', chrome.templates
        if not chrome.templates:
            return None
            
        return chrome.templates.load(filename, cls=NewTextTemplate)

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
        )
        
        output = chrome.render_template(None, "ticket_email_mimic.html", data, content_type="text/html", fragment = True)
        
        return output.render()
