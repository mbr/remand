# FIXME: this module needs more operations instead of low-level directives
# FIXME: should not be part of stdlib
# FIXME: requires additional dependencies (sqlalchemy, _pgcatalog, psycopg2)

from contextlib import contextmanager
from hashlib import md5
import os
import warnings

from contextlib2 import ExitStack
from sqlalchemy import create_engine, exc as sa_exc
from sqlalchemy.engine.url import URL
from sqlalchemy.sql import text
from sqlalchemy.orm import sessionmaker
import sqlalchemy_pgcatalog as sc
import volatile

from remand import operation, Changed, Unchanged
from .. import proc
from ... import net


class AbortTransaction(Exception):
    pass


class PostgreSQL(object):
    def __init__(self,
                 remote_addr='/var/run/postgresql/.s.PGSQL.5432',
                 user='postgres',
                 database='postgres',
                 password=None,
                 ident='postgres',
                 echo=False):
        self.remote_addr = remote_addr
        self.user = user
        self.database = database
        self.password = password
        self.ident = ident
        self.echo = echo

    def abort_transaction(self):
        raise AbortTransaction()

    @contextmanager
    def db_engine(self):
        with ExitStack() as stack:
            dtmp = stack.enter_context(volatile.dir())
            sock_addr = os.path.join(dtmp, '.s.PGSQL.5432')

            if self.ident:
                stack.enter_context(proc.sudo(self.ident))

            stack.enter_context(net.local_forward(self.remote_addr, sock_addr))
            url = URL(drivername='postgresql',
                      username=self.user,
                      password=self.password,
                      database=self.database,
                      query={'host': dtmp})

            engine = create_engine(url, echo=self.echo)
            yield engine

    @contextmanager
    def transaction(self):
        with self.db_engine() as engine:
            con = engine.connect()
            trans = con.begin()

            try:
                yield con
            except AbortTransaction:
                trans.close()
            except Exception:
                trans.close()
                raise
            else:
                trans.commit()

    @contextmanager
    def session(self):
        with self.db_engine() as engine:
            session = sessionmaker(bind=engine)()
            try:
                yield session
                session.commit()
            except:
                session.rollback()
                raise
            finally:
                session.close()

    @contextmanager
    def manager(self):
        # convenience method
        with self.session() as s:
            yield Manager(s)


class Manager(object):
    def __init__(self, session):
        self.session = session

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=sa_exc.SAWarning)
            sc.prepare(self.session.bind)

    def update_role(self, name):
        r = self.session.query(sc.Role).filter_by(rolname=name).first()

        if r:
            print 'FOUND'

        return r

    def list_roles(self):
        return self.session.query(sc.Role).all()

    @operation()
    def create_role(self,
                    name,
                    password=None,
                    superuser=False,
                    createdb=False,
                    createrole=False,
                    inherit=True,
                    login=True,
                    connection_limit=-1):
        # FIXME: should update role if required

        assert name.isalnum()  # used raw in sql query

        for role in self.list_roles():
            if role.rolname == name:
                return Unchanged(msg='Role {} already exists'.format(name))

        sql = text(' '.join([
            'CREATE ROLE ' + name,
            'SUPERUSER' if superuser else 'NOSUPERUSER',
            'CREATEDB' if createdb else 'NOCREATEDB',
            'CREATEROLE' if createrole else 'NOCREATEROLE',
            'INHERIT' if inherit else 'NOINHERIT',
            'LOGIN' if login else 'NOLOGIN',
            'CONNECTION LIMIT :connection_limit',
            'ENCRYPTED PASSWORD :pw_md5'
            if password is not None else 'NOPASSWORD',
        ]))

        pw_md5 = md5(password).hexdigest()

        self.session.connection().execute(sql,
                                          name=name,
                                          connection_limit=connection_limit,
                                          pw_md5=pw_md5)

        return Changed(msg='Created role {}'.format(name))

    def commit(self):
        self.session.commit()
