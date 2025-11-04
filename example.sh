#!/bin/sh

set -x

#ZABBIX_URL=https://zabbix.example.cz/
#ZABBIX_USER=itop
#ZABBIX_PASS=pass
#ITOP_ORGANIZATION=Org1

# Extract all linux servers with tag "VM:true" and generate itop import for VMs
# Name*,Description,Organization->Name,Business criticality,Move to production date,Status,Virtual host->Name,OS family->Name,OS version->Name,OS license->Name,CPU,RAM,IP->FQDN,Organization->Full name,Organization->Obsolete,Virtual host->Full name,Virtual host->CI sub-class,Virtual host->Obsolete,OS family->Full name,OS version->Full name,OS license->Full name,OS license->Obsolete,IP->Full name,IP->Class
python3 zabbix-to-itop.py \
  --url "$ZABBIX_URL" \
  --user "$ZABBIX_USER" --pass "$ZABBIX_PASS" \
  --required_groups "Linux servers" \
  --columns "host:Name,Organization->Name=$ITOP_ORGANIZATION,description:Description,inventory.os:OS family->Full name" \
  --unique Name --outfile vms.csv

# Extract all IP intefaces.
# Name,Device->Name
python3 zabbix-to-itop.py \
  --url "$ZABBIX_URL" \
  --user "$ZABBIX_USER" --pass "$ZABBIX_PASS" \
  --required_groups "Linux servers" \
  --columns "name:Name,Device->Name=eth0" \
  --unique Name --outfile ifs.csv

# Extract all IPs
# Organization->Name,Status*,Note,Requestor->Last Name,Allocation date,Release date,Global IP settings->Name,Short Name,DNS Domain->Name,FQDN,Aliases,Usage->Name,Global IP settings->Allow Duplicate Names,Global IP settings->Ping IP before assigning it,Allow Duplicate Names*,Ping IP before assigning it*,Subnet->Subnet IP,Range->Name,Address*,Organization->Full name,Organization->Obsolete,Requestor->Full name,Requestor->Obsolete,Global IP settings->Full name,DNS Domain->Full name,Usage->Full name,Subnet->Full name,Range->Full name
python3 zabbix-to-itop.py \
  --url "$ZABBIX_URL" \
  --user "$ZABBIX_USER" --pass "$ZABBIX_PASS" \
  --required_groups "Linux servers" \
  --columns "ip:ip,Organization->Name=$ITOP_ORGANIZATION,fqdn:FQDN,ip:Subnet->Subnet IP,Range->Name=192.168.0.0/16" \
  --unique ip --outfile ips.csv

# Link IPs to VMs
# Organization->Name,Status*,Note,Requestor->Last Name,Allocation date,Release date,Global IP settings->Name,Short Name,DNS Domain->Name,FQDN,Aliases,Usage->Name,Global IP settings->Allow Duplicate Names,Global IP settings->Ping IP before assigning it,Allow Duplicate Names*,Ping IP before assigning it*,Subnet->Subnet IP,Range->Name,Address*,Organization->Full name,Organization->Obsolete,Requestor->Full name,Requestor->Obsolete,Global IP settings->Full name,DNS Domain->Full name,Usage->Full name,Subnet->Full name,Range->Full name
python3 zabbix-to-itop.py \
  --url "$ZABBIX_URL" \
  --user "$ZABBIX_USER" --pass "$ZABBIX_PASS" \
  --required_groups "Linux servers" \
  --columns "ip:ip,Organization->Name=$ITOP_ORGANIZATION,fqdn:FQDN,ip:Subnet->Subnet IP,Range->Name=192.168.0.0/16," \
  --unique ip --outfile ip-links.csv

