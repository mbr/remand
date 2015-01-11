from stuf.collects import ChainMap


class TypeConversionMixin(object):
    BOOLEAN_TRUE = ('1', 'yes', 'true', 'on')
    BOOLEAN_FALSE = ('0', 'no', 'false', 'off')

    def get_bool(self, key, default=None):
        rv = self[key]

        if rv in self.BOOLEAN_TRUE:
            return True

        if rv in self.BOOLEAN_FALSE:
            return False

        return default


class TypeConversionChainMap(TypeConversionMixin, ChainMap):
    pass
