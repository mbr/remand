import re


URI_RE = re.compile(r'(?:(?P<transport>[a-zA-Z][a-zA-Z0-9]*)://)?' +
                    r'(?P<host>[^/:]*)' + r'(?::(?P<port>[0-9]+))?' +
                    r'(?:(?P<path>/[^:]*))?' +
                    r'$')


class Uri(object):
    ATTRIBS = ('transport', 'host', 'port', 'path')

    def __init__(self):
        self.transport = None
        self.host = None
        self.port = None
        self.path = None

    @classmethod
    def from_string(cls, s):
        m = URI_RE.match(s)
        if not m:
            raise ValueError('Not a valid uri: {}'.format(s))

        uri = cls()

        for k, v in m.groupdict().iteritems():
            setattr(uri, k, v)

        if uri.port is not None:
            uri.port = int(uri.port)

        return uri

    @classmethod
    def from_dict(cls, d):
        uri = cls()

        for k in cls.ATTRIBS:
            if k in d:
                setattr(uri, k, d[k])

        if uri.port is not None:
            uri.port = int(uri.port)

        return uri

    def __str__(self):
        buf = []
        if self.transport is not None:
            buf.append(self.transport)
            buf.append('://')

        if self.host is not None:
            buf.append(self.host)

        if self.port is not None:
            buf.append(':')
            buf.append(str(self.port))

        if self.path is not None:
            buf.append(self.path)

        return ''.join(buf)

    def as_dict(self):
        d = {}

        for k in self.ATTRIBS:
            v = getattr(self, k)
            if v is not None:
                d[k] = v

        return d
