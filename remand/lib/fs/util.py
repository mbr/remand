from remand.exc import ConfigurationError


class RegistryBase(object):
    registry = {}

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
                .format(cls.__name__, short_name)
            )

        return cls.registry[short_name]

    def __str__(self):
        return '{}'.format(self.__class__.__name__)
