import dali.address as address
import dali.gear.general as gear
from dali.command import YesNoResponse
from dali.exceptions import DALIError
from time import sleep

group = 1
group_address = address.Group(group)

from dali.driver.hasseb import SyncHassebDALIUSBDriver
dali_driver = SyncHassebDALIUSBDriver()


print("GA: %s" % group_address)
actual_level = dali_driver.send(gear.QueryActualLevel(group_address))
print(actual_level)

for i in range(8):
  dali_driver.send(gear.DAPC(group_address,0))
  sleep(1)
  dali_driver.send(gear.DAPC(group_address,254))
  sleep(1)
  