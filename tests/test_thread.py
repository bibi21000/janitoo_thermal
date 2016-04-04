# -*- coding: utf-8 -*-

"""Unittests for Janitoo-Roomba Server.
"""
__license__ = """
    This file is part of Janitoo.

    Janitoo is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Janitoo is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with Janitoo. If not, see <http://www.gnu.org/licenses/>.

"""
__author__ = 'Sébastien GALLET aka bibi21000'
__email__ = 'bibi21000@gmail.com'
__copyright__ = "Copyright © 2013-2014-2015-2016 Sébastien GALLET aka bibi21000"

import warnings
warnings.filterwarnings("ignore")

import sys, os
import time, datetime
import unittest
import threading
import logging
from pkg_resources import iter_entry_points

from janitoo_nosetests.server import JNTTServer, JNTTServerCommon
from janitoo_nosetests.thread import JNTTThread, JNTTThreadCommon
from janitoo_nosetests.thread import JNTTThreadRun, JNTTThreadRunCommon
from janitoo_nosetests.component import JNTTComponent, JNTTComponentCommon

from janitoo.utils import json_dumps, json_loads
from janitoo.utils import HADD_SEP, HADD
from janitoo.utils import TOPIC_HEARTBEAT
from janitoo.utils import TOPIC_NODES, TOPIC_NODES_REPLY, TOPIC_NODES_REQUEST
from janitoo.utils import TOPIC_BROADCAST_REPLY, TOPIC_BROADCAST_REQUEST
from janitoo.utils import TOPIC_VALUES_USER, TOPIC_VALUES_CONFIG, TOPIC_VALUES_SYSTEM, TOPIC_VALUES_BASIC

from janitoo_factory.threads.remote import RemoteBus

class TestThermalThread(JNTTThreadRun, JNTTThreadRunCommon):
    """Test the thread
    """
    thread_name = "thermal"
    conf_file = "tests/data/janitoo_thermal.conf"

    #~ def test_051_nodeman_started(self):
        #~ timeout = 90
        #~ i = 0
        #~ while i< timeout*10000 and not self.thread.nodeman.is_started:
            #~ time.sleep(0.0001)
            #~ i += 1
        #~ self.assertTrue(self.thread.nodeman.is_started)


    def test_101_values_config(self):
        self.thread.start()
        timeout = 120
        i = 0
        while i< timeout and not self.thread.nodeman.is_started:
            time.sleep(1)
            i += 1
            #~ print self.thread.nodeman.state
        #~ print self.thread.bus.nodeman.nodes
        time.sleep(5)
        self.assertTrue(self.thread.nodeman.is_started)
        self.assertNotEqual(None, self.thread.bus.nodeman.find_node('sensor0'))
        self.assertNotEqual(None, self.thread.bus.nodeman.find_node('heater0'))
        self.assertNotEqual(None, self.thread.bus.nodeman.find_node('simple0'))
        self.assertEqual(1, len(self.thread.bus.find_components('thermal.external_sensor')))
        self.assertEqual(1, len(self.thread.bus.find_components('thermal.external_heater')))
        self.assertEqual(1, len(self.thread.bus.find_components('thermal.simple_thermostat')))
        self.assertEqual(1, len(self.thread.bus.find_values('thermal.external_sensor','user_read')))
        self.assertEqual(1, len(self.thread.bus.find_values('thermal.external_heater','user_write')))

        self.assertEqual(1, self.thread.bus.nodeman.find_value('sensor0','user_read').get_length())
        value = self.thread.bus.nodeman.find_value('sensor0','user_read')
        print value.get_value_config()
        self.assertEqual(['dht_in_temp','0'], value.get_value_config())
        self.assertEqual(None, value.get_value_config(index=99))

        self.assertEqual(1, self.thread.bus.nodeman.find_value('heater0','user_write').get_length())
        value = self.thread.bus.nodeman.find_value('heater0','user_write')
        print value.get_value_config()
        self.assertEqual(['switch','0','0x0025','1','0'], value.get_value_config())
        self.assertEqual(None, value.get_value_config(index=99))

    def test_102_thermostat(self):
        self.thread.start()
        timeout = 60
        i = 0
        while i< timeout:
            time.sleep(1)
            i += 1
        i = 0
        time.sleep(5)
        self.assertTrue(self.thread.nodeman.is_started)
        self.thread.bus.find_values('thermal.simple_thermostat','delay')[0].set_data_index(index=0,data=2)
        onstate = self.thread.bus.find_values('thermal.external_heater','user_write')[0].get_value_config(index=0)[3]
        offstate = self.thread.bus.find_values('thermal.external_heater','user_write')[0].get_value_config(index=0)[4]
        self.thread.bus.find_values('thermal.simple_thermostat','setpoint')[0].set_data_index(index=0,data=20)
        self.thread.bus.find_values('thermal.simple_thermostat','hysteresis')[0].set_data_index(index=0,data=0.5)
        self.thread.bus.find_values('thermal.external_sensor','user_read')[0].set_cache(index=0,data=15)
        time.sleep(20.0)
        self.assertEqual(self.thread.bus.find_values('thermal.external_heater','user_write')[0].get_cache(index=0), onstate)
        self.assertEqual(self.thread.bus.find_values('thermal.simple_thermostat','status')[0].get_data_index(index=0), 'Heat')
        self.thread.bus.find_values('thermal.external_sensor','user_read')[0].set_cache(index=0,data=19.5)
        time.sleep(3.0)
        self.assertEqual(self.thread.bus.find_values('thermal.external_heater','user_write')[0].get_cache(index=0), onstate)
        self.assertEqual(self.thread.bus.find_values('thermal.simple_thermostat','status')[0].get_data_index(index=0), 'Heat')
        self.thread.bus.find_values('thermal.external_sensor','user_read')[0].set_cache(index=0,data=19.8)
        time.sleep(3.0)
        self.assertEqual(self.thread.bus.find_values('thermal.external_heater','user_write')[0].get_cache(index=0), onstate)
        self.assertEqual(self.thread.bus.find_values('thermal.simple_thermostat','status')[0].get_data_index(index=0), 'Heat')
        self.thread.bus.find_values('thermal.external_sensor','user_read')[0].set_cache(index=0,data=20.1)
        time.sleep(3.0)
        self.assertEqual(self.thread.bus.find_values('thermal.external_heater','user_write')[0].get_cache(index=0), offstate)
        self.assertEqual(self.thread.bus.find_values('thermal.simple_thermostat','status')[0].get_data_index(index=0), 'Sleep')
        self.thread.bus.find_values('thermal.external_sensor','user_read')[0].set_cache(index=0,data=22.1)
        time.sleep(3.0)
        self.assertEqual(self.thread.bus.find_values('thermal.external_heater','user_write')[0].get_cache(index=0), offstate)
        self.assertEqual(self.thread.bus.find_values('thermal.simple_thermostat','status')[0].get_data_index(index=0), 'Sleep')
        self.thread.bus.find_values('thermal.external_sensor','user_read')[0].set_cache(index=0,data=19.8)
        time.sleep(3.0)
        self.assertEqual(self.thread.bus.find_values('thermal.external_heater','user_write')[0].get_cache(index=0), offstate)
        self.assertEqual(self.thread.bus.find_values('thermal.simple_thermostat','status')[0].get_data_index(index=0), 'Sleep')
        self.thread.bus.find_values('thermal.external_sensor','user_read')[0].set_cache(index=0,data=19.5)
        time.sleep(3.0)
        self.assertEqual(self.thread.bus.find_values('thermal.external_heater','user_write')[0].get_cache(index=0), offstate)
        self.assertEqual(self.thread.bus.find_values('thermal.simple_thermostat','status')[0].get_data_index(index=0), 'Sleep')
        self.thread.bus.find_values('thermal.external_sensor','user_read')[0].set_cache(index=0,data=19.4)
        time.sleep(3.0)
        self.assertEqual(self.thread.bus.find_values('thermal.external_heater','user_write')[0].get_cache(index=0), onstate)
        self.assertEqual(self.thread.bus.find_values('thermal.simple_thermostat','status')[0].get_data_index(index=0), 'Heat')
        self.thread.bus.find_values('thermal.external_sensor','user_read')[0].set_cache(index=0,data=19.4)
        time.sleep(3.0)
        self.assertEqual(self.thread.bus.find_values('thermal.external_heater','user_write')[0].get_cache(index=0), onstate)
        self.assertEqual(self.thread.bus.find_values('thermal.simple_thermostat','status')[0].get_data_index(index=0), 'Heat')
        self.thread.bus.find_values('thermal.external_sensor','user_read')[0].set_cache(index=0,data=19.4)

    def test_103_thermostat_fail(self):
        self.thread.start()
        timeout = 60
        i = 0
        while i< timeout:
            time.sleep(1)
            i += 1
        i = 0
        self.assertTrue(self.thread.nodeman.is_started)
        self.thread.bus.find_values('thermal.simple_thermostat','delay')[0].set_data_index(index=0,data=3)
        onstate = self.thread.bus.find_values('thermal.external_heater','user_write')[0].get_value_config(index=0)[3]
        offstate = self.thread.bus.find_values('thermal.external_heater','user_write')[0].get_value_config(index=0)[4]
        self.thread.bus.find_values('thermal.simple_thermostat','setpoint')[0].set_data_index(index=0,data=20)
        self.thread.bus.find_values('thermal.simple_thermostat','hysteresis')[0].set_data_index(index=0,data=0.5)
        self.thread.bus.find_values('thermal.external_sensor','user_read')[0].set_cache(index=0,data=15)
        time.sleep(20.0)
        self.assertEqual(self.thread.bus.find_values('thermal.external_heater','user_write')[0].get_cache(index=0), onstate)
        self.assertEqual(self.thread.bus.find_values('thermal.simple_thermostat','status')[0].get_data_index(index=0), 'Heat')
        self.thread.bus.find_values('thermal.external_sensor','user_read')[0].set_cache(index=0,data=None)
        time.sleep(12.0)
        self.assertEqual(self.thread.bus.find_values('thermal.simple_thermostat','status')[0].get_data_index(index=0), None)
