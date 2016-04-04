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
__copyright__ = "Copyright © 2013-2014-2015-2016 Sébastien GALLET aka bibi21000"

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
from janitoo_factory.threads.remote import RemoteNodeComponent


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
        poll_value = self.values[uuid].create_poll_value(default=1800)
        self.values[poll_value.uuid] = poll_value
        uuid="missing_ok"
        self.values[uuid] = self.value_factory['config_integer'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The number of missing values we accept before failing',
            label='Hist.',
            default=kwargs.pop('missing_ok', 2),
        )
        self._missing = 0
        poll_value = self.values[uuid].create_poll_value(default=1800)
        self.values[poll_value.uuid] = poll_value
        uuid="setpoint"
        self.values[uuid] = self.value_factory['config_float'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The setpoint temperature of the thermostat',
            label='SetPoint.',
            default=kwargs.pop('setpoint', 20.2),
        )
        poll_value = self.values[uuid].create_poll_value(default=1800)
        self.values[poll_value.uuid] = poll_value
        uuid="delay"
        self.values[uuid] = self.value_factory['config_float'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The delay between 2 checks',
            label='Delay',
            default=kwargs.pop('delay', 15.0),
        )
        uuid="current_temperature"
        self.values[uuid] = self.value_factory['sensor_temperature'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The current temperature returned by sensors',
            label='Temp',
            get_data_cb=self.temperature,
        )
        poll_value = self.values[uuid].create_poll_value(default=300)
        self.values[poll_value.uuid] = poll_value
        uuid="status"
        self.values[uuid] = self.value_factory['sensor_list'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The current status of the thermostat',
            label='Status',
            list_items=['Heat','Sleep'],
        )
        poll_value = self.values[uuid].create_poll_value(default=300)
        self.values[poll_value.uuid] = poll_value
        self.last_run = datetime.datetime.now()

    def temperature(self, node_uuid, index):
        sensors = self.get_sensors()
        try:
            ret = self.get_sensors_temperature(sensors)
        except ValueError:
            logger.exception('Exception when retrieving temperature')
            ret = None
        return ret

    def get_sensors(self):
        """Return a list of all available sensors
        """
        return self._bus.find_values('thermal.external_sensor', 'user_read')

    def get_heaters(self):
        """Return a list of all available heaters (relays)
        """
        return self._bus.find_values('thermal.external_heater', 'user_write')

    def get_sensors_temperature(self, sensors):
        """Return the temperature of the zone. Can be calculated from differents sensors. Must return None whan fail
        """
        logger.debug("sensors[0].get_cache(index=0) : %s"%sensors[0].get_cache(index=0))
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
            self._missing += 1
            sensors = self.get_sensors()
            logger.debug("[%s] - [%s] - Found %s sensors", self.__class__.__name__, self.uuid, len(sensors))
            if len(sensors) == 0:
                logger.warning("[%s] - [%s] - Can't find sensors", self.__class__.__name__, self.uuid)
            heaters = self.get_heaters()
            logger.debug("[%s] - [%s] - Found %s heaters", self.__class__.__name__, self.uuid, len(heaters))
            if len(heaters) == 0:
                logger.warning("[%s] - [%s] - Can't find heaters", self.__class__.__name__, self.uuid)
            try:
                if len(sensors)>0 and len(heaters)>0:
                    try:
                        temp = self.get_sensors_temperature(sensors)
                        if temp is not None:
                            logger.debug("[%s] - [%s] - temp : %s", self.__class__.__name__, self.uuid, temp)
                            if temp > self.values['setpoint'].get_data_index(index=0) :
                                self.values['status'].set_data_index(index=0, data="Sleep")
                                self.deactivate_heaters(heaters)
                            if temp < self.values['setpoint'].get_data_index(index=0) - self.values['hysteresis'].get_data_index(index=0) :
                                self.activate_heaters(heaters)
                                self.values['status'].set_data_index(index=0, data="Heat")
                            self._missing = 0
                    except:
                        logger.exception("[%s] - loop node uuid:%s", self.__class__.__name__, self.uuid)
                else:
                    logger.warning("[%s] - [%s] - Can't find heaters or sensors.", self.__class__.__name__, self.uuid)
            except:
                logger.exception("[%s] - Exception in loop node uuid:%s", self.__class__.__name__, self.uuid)
            logger.debug("[%s] - [%s] - Missing detected : %s, missing : %s, missing_ok : %s", \
                        self.__class__.__name__, self.uuid, self._missing > self.values['missing_ok'].get_data_index(index=0),
                        self._missing, self.values['missing_ok'].get_data_index(index=0))
            if self._missing > self.values['missing_ok'].get_data_index(index=0):
                logger.warning("[%s] - [%s] - Too many missing values. Switch to fail mode", self.__class__.__name__, self.uuid)
                self.values['status'].set_data_index(index=0, data=None)
            self.last_run = datetime.datetime.now() + datetime.timedelta(seconds=self.values['delay'].data)

    def check_heartbeat(self):
        """Check that the status has benn updated

        """
        if 'status' not in self.values:
            return False
        return self.values['status'].get_data_index(index=0) is not None


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
