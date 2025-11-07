# Zabbix to iTop sync
This script fetches data from Zabbix and generate CSVs for import to iTop.
It can optionally run command for every CSV file, so it can automatically import to iTop.

## Usage
```
usage: zabbix-to-itop.py [-h] --config CONFIG [--debug]

Export Zabbix hosts to iTop-compatible CSV (filters + Zabbix→iTop mapping).

options:
  -h, --help       show this help message and exit
  --config CONFIG  Config file
  --debug          Enable debugging
```

## Example 1: Get all servers from zabbix and generate servers.csv for iTop
Hosts within Zabbix must have reqauired tags, groups and templates.

```
# Global options
options:
  url: https://zabbix.example.com
  user: itop
  password: pass

# Definition of outputs
outputs:
  servers:
    outfile: servers.csv
    #import_cmd: php webservices/import.php --auth_user=admin --auth_pwd=admin --csvfile="{{ outfile }}" --class="Person" --reconciliationkeys="Email"
    batch_size: 30
    unique:
      - Name

    # Definition of output columns
    columns:
      # STATIC column – always same value
      - static:
          itop: "Organization->Name"
          value: "Org1"

      # TEMPLATE column (string macros)
      - template:
          itop: "Description"
          value: "{{ zbx('host') }} / {{ zbx('inventory.os') }}"

      # ZABBIX → ITOP direct mapping
      - map:
          zabbix: "host"
          itop: "Name"

      - map:
          zabbix: "inventory.serialno_a"
          itop: "Serial Number"

#   Filters
    required_tags:
      - tag1=prod
      - tag2=itop

    required_groups:
      - Linux

    required_templates:
      - Template OS Linux


```

## Example 2: Import more objects
- **Works only with IPAM module installed.**
- **Network device types** must be created before first run
- **IP subnet blocks** must exists
- **Assuming we are running import commands on itop host** 

Use this config file to process and import everything. 
```
# Global options
options:
  url: https://zabbix.example.com
  user: itop
  password: pass
  
# Definition of outputs
outputs:

# Get All DNS domains from Zabbix interfaces
  domains:
    outfile: domains.csv
    import_cmd: php /var/www/html/webservices/import.php --auth_user=zabbix_syncer --auth_pwd=$ITOP_PASS --class=Domain --csvfile="{{ outfile }}" --charset=utf8 --output=details --reconciliationkeys="Name"
    unique:
      - Name
    columns:
      - static:
          itop: Organization->Name
          value: "ExampleOrg"
      - map:
          zabbix: "interface.domain"
          itop: "Name"

# Get all IPs from Zabbix interfaces
  ips:
    outfile: ips.csv
    import_cmd: php /var/www/html/webservices/import.php --auth_user=zabbix_syncer --auth_pwd=$ITOP_PASS --class=IPv4Address --csvfile="{{ outfile }}" --charset=utf8 --output=details --reconciliationkeys="Name"
    unique:
      - Address
    columns:
      - static:
          itop: Organization->Name
          value: "ExampleOrg"
      - static:
          itop: Status
          value: "Released"
      - map:
          zabbix: "interface.ip"
          itop: "Address"
      - map:
          zabbix: "interface.host"
          itop: "Short Name"
      - map:
          zabbix: "interface.domain"
          itop: "DNS Domain->Name"

  servers:
    outfile: servers.csv
    import_cmd: php /var/www/html/webservices/import.php --auth_user=zabbix_syncer --auth_pwd=$ITOP_PASS --class=Server --csvfile="{{ outfile }}" --charset=utf8 --output=details --reconciliationkeys="Name"
    unique:
      - Name

    columns:
      - static:
          itop: Organization->Name
          value: "ExampleOrg"
      - map:
          zabbix: "hostname"
          itop: "Name"
      - map:
          zabbix: "inventory.serialno_a"
          itop: "Serial Number"
      - map:
          zabbix: "interface.ip"
          itop: "Management IP->Full name"
    required_tags:
      - type=server

  switches:
    outfile: switches.csv
    import_cmd: php /var/www/html/webservices/import.php --auth_user=zabbix_syncer --auth_pwd=$ITOP_PASS --class="NetworkDevice" --csvfile="{{ outfile }}" --charset=utf8 --reconciliationkeys="Name"
    unique:
      - Name
    columns:
      - static:
          itop: Organization->Name
          value: "ExampleOrg"
      - static:
          itop: Network type->Full name
          value: "Switch"
      - map:
          zabbix: "hostname"
          itop: "Name"
      - map:
          zabbix: "inventory.serialno_a"
          itop: "Serial Number"
      - map:
          zabbix: "interface.ip"
          itop: "Management IP->Full name"
    required_tags:
      - type=switch

  routers:
    outfile: routers.csv
    import_cmd: php /var/www/html/webservices/import.php --auth_user=zabbix_syncer --auth_pwd=$ITOP_PASS --csvfile="{{ outfile }}" --class="NetworkDevice" --charset=utf8 --reconciliationkeys="Name"
    unique:
      - Name

    columns:
      - static:
          itop: Organization->Name
          value: "ExampleOrg"
      - static:
          itop: Network type->Full name
          value: "Router"
      - map:
          zabbix: "hostname"
          itop: "Name"
      - map:
          zabbix: "inventory.serialno_a"
          itop: "Serial Number"
      - map:
          zabbix: "interface.ip"
          itop: "Management IP->Full name"
    required_tags:
      - type=router

  vms:
    outfile: vms.csv
    import_cmd: php /var/www/html/webservices/import.php --auth_user=zabbix_syncer --auth_pwd=$ITOP_PASS --csvfile="{{ outfile }}" --class="VirtualMachine" --charset=utf8 --reconciliationkeys="Name"
    unique:
      - Name
    columns:
      - static:
          itop: Organization->Name
          value: "ExampleOrg"
      - map:
          zabbix: "hostname"
          itop: "Name"
      - map:
          zabbix: "inventory.serialno_a"
          itop: "Serial Number"
      - map:
          zabbix: "interface.ip"
          itop: "IP->Full name"
    required_tags:
      - type=vm

  cameras:
    outfile: cameras.csv
    import_cmd: php /var/www/html/webservices/import.php --auth_user=zabbix_syncer --auth_pwd=$ITOP_PASS --csvfile="{{ outfile }}" --class="Network Device" --reconciliationkeys="Name"
    unique:
      - Name

    columns:
      - static:
          itop: Organization->Name
          value: "ExampleOrg"
      - static:
          itop: Network type->Full name
          value: "Camera"
      - map:
          zabbix: "hostname"
          itop: "Name"
      - map:
          zabbix: "inventory.serialno_a"
          itop: "Serial Number"
      - map:
          zabbix: "interface.ip"
          itop: "Management IP->Full name"
    required_tags:
      - type=camera
```