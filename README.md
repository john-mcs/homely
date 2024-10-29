# Homely
Home Assistant Homely Alarm System integration

Since Homely API is read-only, system state is implemented as a sensor and not as an Alarm Control Panel.

For the moment it supports temperature and battery level from all connected devices. 

Files must manually be copied to /config/custom_components/homely
for example by using the Samba share add-on.

If the /config/custom_components directory does not exist already, just create it. 

Restart home-assistant, and thoe Homely integration should be available to add under settings. 
