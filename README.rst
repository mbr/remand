remand
======

remand is a tool to configure any kind of *nix machine automatically. It allows
you to provision servers, configure your desktop machine or customize a
RaspberryPi SD-card image. Here's an example::

    remand webserver.py www.example.com

remand will connect to ``www.example.com`` using SSH and run the webserver.py
script, which would look like this::

    FIXME: Example should go here

If that made you curious, the docs are hosted at
http://python-hosted.org/remand


What makes it cool?
-------------------

remand is a product born out of frustration with other tools like `Chef
<https://chef.io>`_, `Fabric <http://fabfile.org>`_, `Puppet
<http://puppetlabs.com>`_, `Ansible <http://ansible.com>`_ or `Salt
<http://saltstack.com>`_. This is what it tries to do better:

* **Speed**: Setting up a new high-end cluster is nice - but when provisioning
  a new 800 Mhz ARM-machine that uses an SD card as its harddrive, even
  starting a Python interpreter on the remote would take 2-4 seconds. remand
  uses out-of-order execution where possible avoids starting many heavy
  processes.
* **Security**: For remand, security isn't a feature but a necessity. No
  compromises are made like other tools have done in the past (such as
  disabling host-key checking by default) [1]_.
* **No remote dependencies**: remand makes do with minimal dependencies on the
  remote machine (no `Ruby <https://www.ruby-lang.org>`_ install needed),
  almost all processing is done on the host using SSH and OpenSSH's
  built-in SFTP.
* **Expressiveness**: remand uses proper Python for scripting and does *not*
  mess around with things like YAML instead of a real `DSL
  <https://en.wikipedia.org/wiki/Domain-specific_language>`_. You can do real
  working your provisioning scripts, which will be done on the host, not the
  remote.
* **Robustness**: Instead of using a lot of scripting and subprocesses, most
  heavy lifting is done via SFTP or Python libraries. This avoids a whole host
  of subtle problems with passing data through various layers of indirection.


.. [1] See some of the `author's work
       <https://github.com/paramiko/paramiko/pull/473>`_ to demonstrate this
       effort.
