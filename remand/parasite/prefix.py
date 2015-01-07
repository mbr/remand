from struct import pack

from six import b


class Encoder(object):
    def __init__(self, header_format='!Q'):
        self.header_format = header_format
        self.header_length = calcsize(header_format)

    def enc_bytes(self, bs):
        return pack(self.header_format, (len(bs),)) + bs

    def send_bytes(self, bs, stream):
        stream.write(pack(self.header_format, (len(bs),)))
        stream.write(stream)

    def read_bytes(self, stream):
        header = stream.read(self.header_length)
        l = unpack(self.header_format, header)[0]
        return stream.read(l)

    def enc_list(self, l):

