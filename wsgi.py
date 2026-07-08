#!/usr/bin/env python
import os
import sys

# Import the app
import app as app_module

app = app_module.app
socketio = app_module.socketio

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
