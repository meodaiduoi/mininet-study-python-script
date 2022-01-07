#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
This is just an example of
how a blank base application of
an Ryu App.

sudo app-manager BaseApplication.py
'''

from ryu.base import app_manager

class BaseApplication(app_manager.RyuApp):
    def __init__(self, *args, **kwargs):
        super(BaseApplication, self).__init__(*args, **kwargs)