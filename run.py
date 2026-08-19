# MiniWiki – selbst gehostetes Wiki
# Copyright (C) 2026 <Dein Name>
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version. It is distributed WITHOUT ANY WARRANTY; see the GNU AGPL
# <https://www.gnu.org/licenses/> for details. Full text in the LICENSE file.
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001, debug=False)
