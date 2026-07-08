#!/usr/bin/env python
import os
import sys

# Import the app
import deepseek_python_20260708_112ed6 as app_module

app = app_module.app
socketio = app_module.socketio

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
