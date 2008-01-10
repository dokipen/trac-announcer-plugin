from trac.core import Component, implements
from trac.web import IRequestFilter
from trac.wiki import parse_args

class BreadcrumbsProvider(Component):
    implements(IRequestFilter)
    
    def pre_process_request(self, req, handler):
        return handler
        
    def post_process_request(self, req, template, data, content_type):
        try:
            path = req.path_info
            if path.count('/') >= 2:
                _, realm, rest = path.split('/', 2)
                
                if realm in ('wiki', 'ticket'):            
                    if '#' in rest:
                        name = rest[0:rest.index('#')]
                    else:
                        name = rest
                    
                    if '&' in name:
                        name = name[0:name.index('&')]
                    
                    id = name
                    if realm == "ticket":
                        name = "#" + name
                        
                    crumbs = []
                    if req.incookie.has_key('trac.breadcrumbs'):
                        raw = req.incookie['trac.breadcrumbs'].value
                        try:
                            crumbs = [x.replace('@COMMA@', ',') for x in parse_args(raw)[0]]
                        except:
                            pass
                    
                    print "Testing", req.href("%s/%s" % (realm,id))
                    print 'R', realm
                    print 'I', id
                    current = "%s:%s" % (name, req.href("%s/%s" % (realm, id)))
                    print current
                    if current not in crumbs:
                        crumbs.insert(0, current)
                        crumbs = crumbs[0:6]
                        
                        req.outcookie['trac.breadcrumbs'] = ','.join(
                            x.replace(',', '@COMMA@') for x in crumbs
                        )
                        req.outcookie['trac.breadcrumbs']['path'] = req.href()
        except:
            self.log.exception("Breadcrumb failed :(")
        
        req.outcookie['trac.root'] = req.href()
        req.outcookie['trac.root']['path'] = req.href()
        
        if req.incookie.has_key('trac.breadcrumbs'):
            print "CRUMBS", req.incookie['trac.breadcrumbs'].value

        return template, data, content_type