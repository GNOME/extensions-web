==============
SweetTooth-Web
==============

**SweetTooth-Web** is a Django-powered web application that, in co-operation
with some GNOME Shell integration helper (`Browser extension`_)
allows users to install, upgrade and enable/disable their own Shell Extensions.
All operations with the Shell are done through a special helper which proxies
over to the Shell by DBus.

Since extensions can be dangerous, all extensions uploaded to the repository
must go through code review and testing.

.. _Browser extension: https://gitlab.gnome.org/GNOME/gnome-browser-extension/

Requirements
------------


System Requirements:
  * `python`_ 3.10+
  * `OpenSearch`_

Python Requirements:
 For a list of Python requirements please look to the `requirements.in` file.

.. _python: https://www.python.org/
.. _OpenSearch: https://opensearch.org/

Develop inside container
------------------------

It's possible to use VSCode Remote Containers (devcontainer) for fast development workspace setup.
Please look to the `nE0sIghT/ego-devcontainer`_ repository for instructions.

.. _nE0sIghT/ego-devcontainer: https://gitlab.gnome.org/nE0sIghT/ego-devcontainer
