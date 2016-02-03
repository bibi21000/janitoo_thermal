# -*- coding: utf-8 -*-
"""The Raspberry http thread

Server files using the http protocol

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
__copyright__ = "Copyright © 2013-2014-2015 Sébastien GALLET aka bibi21000"

import logging
logger = logging.getLogger(__name__)
import os, sys
import threading
import datetime

from janitoo.thread import JNTBusThread, BaseThread
from janitoo.options import get_option_autostart
from janitoo.utils import HADD
from janitoo.node import JNTNode
from janitoo.value import JNTValue
from janitoo.component import JNTComponent
from janitoo.bus import JNTBus
from janitoo.threads.remote import RemoteNodeComponent


##############################################################
#Check that we are in sync with the official command classes
#Must be implemented for non-regression
from janitoo.classes import COMMAND_DESC

COMMAND_WEB_CONTROLLER = 0x1030
COMMAND_WEB_RESOURCE = 0x1031
COMMAND_DOC_RESOURCE = 0x1032

assert(COMMAND_DESC[COMMAND_WEB_CONTROLLER] == 'COMMAND_WEB_CONTROLLER')
assert(COMMAND_DESC[COMMAND_WEB_RESOURCE] == 'COMMAND_WEB_RESOURCE')
assert(COMMAND_DESC[COMMAND_DOC_RESOURCE] == 'COMMAND_DOC_RESOURCE')
##############################################################

def make_simple_thermostat(**kwargs):
    return SimpleThermostatComponent(**kwargs)

def make_external_sensor(**kwargs):
    return ExternalSensorComponent(**kwargs)

def make_external_heater(**kwargs):
    return ExternalHeaterComponent(**kwargs)

class ThermalBus(JNTBus):
    """A minimal thermal bus
    """
    def __init__(self, **kwargs):
        """
        :param kwargs: parameters transmitted to :py:class:`smbus.SMBus` initializer
        """
        JNTBus.__init__(self, **kwargs)

    def start(self, mqttc, trigger_thread_reload_cb=None):
        """Start the bus
        """
        #~ for bus in self.buses:
            #~ self.buses[bus].start(mqttc, trigger_thread_reload_cb=None)
        JNTBus.start(self, mqttc, trigger_thread_reload_cb)

    def stop(self):
        """Stop the bus
        """
        JNTBus.stop(self)

    def loop(self, stopevent):
        """Loop in the bus"""
        for compo in self.components.keys():
            self.components[compo].loop(stopevent)

class SimpleThermostatComponent(JNTComponent):
    """ A somple thermostat component. Use an hysteresis to avoid resonance """

    def __init__(self, bus=None, addr=None, **kwargs):
        """
        """
        oid = kwargs.pop('oid', 'thermal.simple_thermostat')
        name = kwargs.pop('name', "Simple thermostat")
        JNTComponent.__init__(self, oid=oid, bus=bus, addr=addr, name=name,
                **kwargs)
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)
        uuid="hysteresis"
        self.values[uuid] = self.value_factory['config_float'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The hysteresis of the thermostat',
            label='Hist.',
            default=kwargs.pop('hysteresis', 0.5),
        )
        uuid="setpoint"
        self.values[uuid] = self.value_factory['config_float'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The setpoint temperature of the thermostat',
            label='SetPoint.',
            default=kwargs.pop('setpoint', 20.2),
        )
        uuid="delay"
        self.values[uuid] = self.value_factory['config_float'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The delay between 2 checks',
            label='Delay',
            default=kwargs.pop('delay', 15.0),
        )
        self.last_run = datetime.datetime.now()

    def get_sensors(self):
        """Return a list of all available sensors
        """
        return self._bus.find_values('thermal.external_sensor', 'users_read')

    def get_heaters(self):
        """Return a list of all available heaters (relays)
        """
        return self._bus.find_values('thermal.external_heater', 'users_write')

    def get_temperature(self, sensors):
        """Return the temperature of the zone. Can be calculated from differents sensors.
        """
        return sensors[0].get_cache(index=0)

    def activate_heaters(self, heaters):
        """Activate all heaters in the zone
        """
        state = heaters[0].get_cache(index=0)
        onstate = heaters[0].get_value_config(index=0)[3]
        if state != onstate:
            heaters[0].set_cache(index=0, data=onstate)
            logger.debug("[%s] - [%s] --------------------------------- Update heater to onstate.", self.__class__.__name__, self.uuid)

    def deactivate_heaters(self, heaters):
        """Deactivate all heaters in the zone
        """
        state = heaters[0].get_cache(index=0)
        offstate = heaters[0].get_value_config(index=0)[4]
        if state != offstate:
            heaters[0].set_cache(index=0, data=offstate)
            logger.debug("[%s] - [%s] --------------------------------- Update heater to offstate.", self.__class__.__name__, self.uuid)

    def loop(self, stopevent):
        """Loop in the components"""
        if self.last_run < datetime.datetime.now():
            sensors = self.get_sensors()
            heaters = self.get_heaters()
            logger.debug("[%s] - [%s] - Found %s external sensors", self.__class__.__name__, self.uuid, len(sensors))
            logger.debug("[%s] - [%s] - Found %s external heaters", self.__class__.__name__, self.uuid, len(heaters))
            if len(sensors)>0 and len(heaters)>0:
                try:
                    temp = self.get_temperature(sensors)
                    if temp > self.values['setpoint'].get_data_index(index=0) :
                        self.deactivate_heaters(heaters)
                    if temp < self.values['setpoint'].get_data_index(index=0) - self.values['hysteresis'].get_data_index(index=0) :
                        self.activate_heaters(heaters)
                except:
                    logger.exception("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)
            else:
                logger.warning("[%s] - [%s] - Can't find external heaters or sensors.", self.__class__.__name__, self.uuid)
            self.last_run = datetime.datetime.now() + datetime.timedelta(seconds=self.values['delay'].data)

class ExternalSensorComponent(RemoteNodeComponent):
    """ An external sensor component """

    def __init__(self, bus=None, addr=None, **kwargs):
        """
        """
        oid = kwargs.pop('oid', 'thermal.external_sensor')
        name = kwargs.pop('name', "External sensor")
        RemoteNodeComponent.__init__(self, oid=oid, bus=bus, addr=addr, name=name,
                **kwargs)
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)

class ExternalHeaterComponent(RemoteNodeComponent):
    """ An external heater component """

    def __init__(self, bus=None, addr=None, **kwargs):
        """
        """
        oid = kwargs.pop('oid', 'thermal.external_heater')
        name = kwargs.pop('name', "External heater")
        RemoteNodeComponent.__init__(self, oid=oid, bus=bus, addr=addr, name=name,
                **kwargs)
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)
