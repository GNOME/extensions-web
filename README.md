# SweetTooth-Web

**SweetTooth-Web** is a Django-powered web application that, in co-operation
with some GNOME Shell integration helper
([Browser extension](https://gitlab.gnome.org/GNOME/gnome-browser-extension/))
allows users to install, upgrade and enable/disable their own Shell Extensions.
All operations with the Shell are done through a special helper which proxies
over to the Shell by DBus.

Since extensions can be dangerous, all extensions uploaded to the repository
must go through code review and testing.

## Requirements

### System Requirements:
  - [python 3.11+](https://www.python.org/)
  - [OpenSearch](https://opensearch.org/)

### Python Requirements:
For a list of Python requirements please look to the `requirements.in` file.


## Develop inside container

It's possible to use [VS Code](https://code.visualstudio.com/) Remote Containers
([devcontainer](https://containers.dev/)) for fast development workspace setup.

Please look to the [nE0sIghT/ego-devcontainer](https://gitlab.gnome.org/nE0sIghT/ego-devcontainer)
repository for instructions.
