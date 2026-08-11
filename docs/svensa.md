# How to connect Vent-Axia Svensa (PureAire Sense) fan

This integration requires two fan-specific parameters to connect and be able to control Svensa: MAC address and PIN code.
Unlike some other models, Svensa is not automatically connectable (as of Dec 2024).

Below is one of the ways to make it work.

### MAC address
Use a Bluetooth scanner app to list all nearby BLE devices. 
These instructions were tested with "BLE Scanner". Probably other apps offer similar functionality.

NOTE: Apple devices (tested with iPhone and Macbook Pro) do not support listing MAC address. 
You'll have to use an Android tablet/smartphone or a Linux/Windows computer.   
 
The fan will be listed with the name "Svensa", and you'll be able to see the MAC address.
It looks similar to AA:BB:CC:DD:EE:FF. Use it in the integration connection screen.

### PIN code
* Once the device is found, connect to it with BLE Scanner.
The app should show a directory-like structure of data items, each with a unique ID.
Look for the one with ID 4cad343a-209a-40b7-b911-4d9b3df569b2.
This item can be read and written.

* Read it (press R in the app). It should obtain the hex value 00000000.

* Put the fan in pairing mode:
  1. Remove the front magnetic cover.
  2. Make sure the fan is switched on (spins).
  3. Press the "power" touch-button on the front right. The other buttons should illuminate.
  4. Press the lowest button (looks like a WiFi symbol) for a few seconds, until it starts flashing.

* Perform write operation on that data item 4cad...69b2. 
It will send the previously obtained zero value to the fan, and the fan will respond with the value of the PIN, in hex format (similar to aa:bb:cc:dd).
* Finally, flip the bytes of the PIN (dd:cc:bb:aa), convert this value to decimal, and use the result in the integration PIN field. 

If the above doesn't work, power cycle the fan. It looses Bluetooth connection now and then (also with the official app).
