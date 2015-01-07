from struct import pack, unpack, calcsize


def copy_file_n(src, dst, n, bufsize):
    while n:
        buf = src.read(min(bufsize, n))
        dst.write(buf)
        n -= len(buf)


class StreamMixin(object):
    BUFSIZE = 4096

    def sread_packet(self, out):
        l = self._read_header()
        copy_file_n(self.s_in, out, l, self.BUFSIZE)

    def swrite_packet(self, inp, inp_length):
        self._write_header(inp_length)
        copy_file_n(inp, self.s_out, inp_length, self.BUFSIZE)


class ParasiteProtocol(StreamMixin):
    HEADER_FMT = '!Q'
    HEADER_SIZE = calcsize(HEADER_FMT)

    def __init__(self, s_in, s_out):
        self.s_in = s_in
        self.s_out = s_out

    def read_header(self):
        raw = self.s_in.read(self.HEADER_SIZE)
        return unpack(self.HEADER_FMT, raw)

    def write_header(self, payload_length):
        raw = pack(self.HEADER_FMT, (payload_length,))
        return self.s_out.write(raw)

    def read_packet(self):
        l = self._read_header(self.s_in)
        return self.s_in.read(l)

    def write_packet(self, payload):
        self._write_header(len(payload))
        self.s_out.write(payload)


class Parasite(object):
    def __init__(self, s_in, s_out):
        self.proto = ParasiteProtocol(s_in, s_out)

    def run(self):
        while True:
            func = str(self.s_in.read_packet())

            # call function
            getattr(self, 'handle_' + func)()

    def handle_ping(self):
        self.write_packet('pong')
