from remand import log

changed = lambda msg: log.info(msg)
unchanged = lambda msg: log.debug(msg)
failed = lambda msg: log.warning(msg)
