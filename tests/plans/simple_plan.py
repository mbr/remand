from remand.plan import Plan

simple = Plan('simple')


@simple.objective()
def run():
    print 'IM RUNNING'
