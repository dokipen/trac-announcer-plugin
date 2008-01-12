from trac.core import Component, implements, ExtensionPoint
from trac.util.compat import set, sorted
from trac.config import Option, BoolOption, IntOption, OrderedExtensionsOption
from announcerplugin.api import IAnnouncementDistributor
from announcerplugin.api import IAnnouncementFormatter
from announcerplugin.api import IAnnouncementPreferenceProvider
from announcerplugin.api import IAnnouncementAddressResolver
from announcerplugin.api import AnnouncementSystem

from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
import time, Queue, threading, smtplib

class DeliveryThread(threading.Thread):
    def __init__(self, queue, sender):
        threading.Thread.__init__(self)
        self._sender = sender
        self._queue = queue
        self.setDaemon(True)
        
    def run(self):
        while 1:
            sendfrom, recipients, message = self._queue.get()
            
            self._sender(sendfrom, recipients, message)
            
class EmailDistributor(Component):
    
    implements(IAnnouncementDistributor, IAnnouncementPreferenceProvider)

    formatters = ExtensionPoint(IAnnouncementFormatter)
    resolvers = OrderedExtensionsOption('announcer', 'address_resolvers', 
        IAnnouncementAddressResolver, 'SessionEmailResolver', 
    )

    smtp_enabled = BoolOption('announcer', 'smtp_enabled', 'false',
        """Enable SMTP (email) notification.""")

    smtp_server = Option('announcer', 'smtp_server', 'localhost',
        """SMTP server hostname to use for email notifications.""")

    smtp_port = IntOption('announcer', 'smtp_port', 25,
        """SMTP server port to use for email notification.""")

    smtp_user = Option('announcer', 'smtp_user', '',
        """Username for SMTP server. (''since 0.9'').""")

    smtp_password = Option('announcer', 'smtp_password', '',
        """Password for SMTP server. (''since 0.9'').""")

    smtp_from = Option('announcer', 'smtp_from', 'trac@localhost',
        """Sender address to use in notification emails.""")
        
    smtp_from_name = Option('announcer', 'smtp_from_name', '',
        """Sender name to use in notification emails.""")

    smtp_replyto = Option('announcer', 'smtp_replyto', 'trac@localhost',
        """Reply-To address to use in notification emails.""")

    smtp_always_cc = Option('announcer', 'smtp_always_cc', '',
        """Email address(es) to always send notifications to,
           addresses can be see by all recipients (Cc:).""")

    smtp_always_bcc = Option('announcer', 'smtp_always_bcc', '',
        """Email address(es) to always send notifications to,
           addresses do not appear publicly (Bcc:). (''since 0.10'').""")
           
    smtp_default_domain = Option('announcer', 'smtp_default_domain', '',
        """Default host/domain to append to address that do not specify one""")
        
    ignore_domains = Option('announcer', 'ignore_domains', '',
        """Comma-separated list of domains that should not be considered
           part of email addresses (for usernames with Kerberos domains)""")
           
    admit_domains = Option('announcer', 'admit_domains', '',
        """Comma-separated list of domains that should be considered as
        valid for email addresses (such as localdomain)""")
           
    mime_encoding = Option('announcer', 'mime_encoding', 'base64',
        """Specifies the MIME encoding scheme for emails.
        
        Valid options are 'base64' for Base64 encoding, 'qp' for
        Quoted-Printable, and 'none' for no encoding. Note that the no encoding
        means that non-ASCII characters in text are going to cause problems
        with notifications (''since 0.10'').""")

    use_public_cc = BoolOption('announcer', 'use_public_cc', 'false',
        """Recipients can see email addresses of other CC'ed recipients.
        
        If this option is disabled (the default), recipients are put on BCC
        (''since 0.10'').""")

    use_short_addr = BoolOption('announcer', 'use_short_addr', 'false',
        """Permit email address without a host/domain (i.e. username only)
        
        The SMTP server should accept those addresses, and either append
        a FQDN or use local delivery (''since 0.10'').""")
        
    use_tls = BoolOption('announcer', 'use_tls', 'false',
        """Use SSL/TLS to send notifications (''since 0.10'').""")
    
    smtp_subject_prefix = Option('announcer', 'smtp_subject_prefix',
                                 '__default__', 
        """Text to prepend to subject line of notification emails. 
        
        If the setting is not defined, then the [$project_name] prefix.
        If no prefix is desired, then specifying an empty option 
        will disable it.(''since 0.10.1'').""")
    
    use_threaded_delivery = BoolOption('announcer', 'use_threaded_delivery', False, 
    """If true, the actual delivery of the message will occur in a separate thread.""")
    
    def __init__(self):
        if self.use_threaded_delivery:
            self._deliveryQueue = Queue.Queue()
            thread = DeliveryThread(self._deliveryQueue, self._transmit)
            thread.start()
    
    # IAnnouncementDistributor
    def get_distribution_transport(self):
        return "email"
        
    def distribute(self, transport, recipients, event):
        if transport == self.get_distribution_transport():
            formats = {}
            
            for f in self.formatters:
                if f.get_format_transport() == transport:
                    if event.realm in f.get_format_realms(transport):
                        styles = f.get_format_styles(transport, event.realm)
                        for style in styles:
                            formats[style] = f
            
            self.log.debug(
                "EmailDistributor has found the following formats capable "
                "of handling '%s' of '%s': %s" % (
                    transport, event.realm, ', '.join(formats.keys())
                )
            )
            
            messages = {}

            for name, address in recipients:
                if name:
                    format = self._get_preferred_format(event.realm, name)
                else:
                    format = self._get_default_format()
                    
                if format not in messages:
                    messages[format] = set()
                    
                if name and not address:
                    for resolver in self.resolvers:
                        address = resolver.get_address_for_name(name)
                        if address:
                            break
                            
                if address:
                    messages[format].add((name, address))
                else:
                    self.log.debug("EmailDistributor was unable to find an address for: %s" % name)
                    
            for format in messages.keys():
                if messages[format]:
                    self.log.debug(
                        "EmailDistributor is sending event as '%s' to: %s" % (
                            format, ', '.join(
                                ('%s <%s>' % (name, address) for name, address in messages[format])
                            )
                        )
                    )
                    self._do_send(transport, event, format, messages[format], formats[format])

    def _get_default_format(self):
        return 'plaintext'
        
    def _get_preferred_format(self, realm, sid):
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT value 
              FROM session_attribute
             WHERE sid=%s
               AND authenticated=1
               AND name=%s
        """, (sid, 'announcer_email_format_%s' % realm))
                
        result = cursor.fetchone()
        if result:
            chosen = result[0]
            self.log.debug("EmailDistributor determined the preferred format for '%s' is: %s" % (sid, chosen))
            return chosen
        else:
            return self._get_default_format()
            
    def _do_send(self, transport, event, format, recipients, formatter, backup=None):
        output = formatter.format(transport, event.realm, format, event)
        subject = formatter.format_subject(transport, event.realm, format, event)
        
        parentMessage = MIMEMultipart("related")
        parentMessage['Subject'] = subject
        parentMessage['From'] = self.smtp_from
        parentMessage['To'] = self.env.project_name
        parentMessage['Reply-To'] = self.smtp_replyto
        parentMessage.preamble = 'This is a multi-part message in MIME format.'
        
        msgText = MIMEText(output, 'html')
        parentMessage.attach(msgText)
        
        start = time.time()
        
        package = (self.smtp_from, [x[1] for x in recipients if x], parentMessage.as_string() )
        if self.use_threaded_delivery:
            self._deliveryQueue.put(package)
        else:
            self._transmit(*package)
            
        stop = time.time()
        self.log.debug("EmailDistributor took %s seconds to send." % (round(stop-start,2)))

    def _transmit(self, smtpfrom, addresses, message):
        smtp = smtplib.SMTP()
        smtp.connect(self.smtp_server)
        smtp.login(self.smtp_user, self.smtp_password)
        smtp.sendmail(smtpfrom, addresses, message)
        smtp.quit()
        
    # IAnnouncementDistributor
    def get_announcement_preference_boxes(self, req):
        yield "email", "E-Mail Format"
        
    def render_announcement_preference_box(self, req, panel):
        cfg = self.config
        sess = req.session
        transport = self.get_distribution_transport()
        
        supported_realms = {}
        for formatter in self.formatters:
            if formatter.get_format_transport() == transport:
                for realm in formatter.get_format_realms(transport):
                    if realm not in supported_realms:
                        supported_realms[realm] = set()
                        
                    supported_realms[realm].update(
                       formatter.get_format_styles(transport, realm)
                    )
                    
        
        if req.method == "POST":
            for realm in supported_realms:
                opt = req.args.get('email_format_%s' % realm, False)
                if opt:
                    sess['announcer_email_format_%s' % realm] = opt
        
        prefs = {}
        for realm in supported_realms:
            prefs[realm] = sess.get('announcer_email_format_%s' % realm, None)
        
        data = dict(
            realms = supported_realms,
            preferences = prefs,
        )
        
        return "prefs_announcer_email.html", data    