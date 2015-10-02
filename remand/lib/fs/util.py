from remand import log
from remand.exc import ConfigurationError


class RegistryBase(object):
    @classmethod
    def _registered(cls, child):
        cls.registry[child.short_name] = child
        return child

    @classmethod
    def _by_short_name(cls, short_name):
        v = cls.registry.get(short_name, None)
        if v is None:
            raise ConfigurationError(
                'Unknown {}: {!r}. Check your configuration setting.'
                .format(cls.__name__, short_name))

        subclass = cls.registry[short_name]
        log.debug('{} {!r} -> {}'.format(
            cls.__name__, short_name, subclass.__name__))
        return subclass

    def __str__(self):
        return '{}'.format(self.__class__.__name__)
