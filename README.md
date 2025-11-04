# Zabbix to iTop sync

## Usage
```
usage: zabbix-to-itop.py [-h] --url URL --user USER --pass PASSWORD
                         [--required_tags REQUIRED_TAGS]
                         [--required_groups REQUIRED_GROUPS]
                         [--required_templates REQUIRED_TEMPLATES] --columns
                         COLUMNS [--unique UNIQUE] [--outfile OUTFILE]
                         [--dry-run]

Export Zabbix hosts to iTop-compatible CSV (filters + Zabbix→iTop mapping).

options:
  -h, --help            show this help message and exit
  --url URL             Zabbix API URL, e.g., https://zabbix.example.com
  --user USER           Zabbix username
  --pass PASSWORD       Zabbix password
  --required_tags REQUIRED_TAGS
                        Comma list of tag=value pairs, e.g.,
                        sync=itop,env=prod
  --required_groups REQUIRED_GROUPS
                        Comma list of group names, e.g., Linux,Production
  --required_templates REQUIRED_TEMPLATES
                        Comma list of template names, e.g., "Template OS
                        Linux,Template App"
  --columns COLUMNS     Mapping Zabbix→iTop, e.g., host:name,inventory.os:os,t
                        ags.location:location,hostid:zabbix_id
  --unique UNIQUE       Zabbix unique path (for logging/validation); not
                        enforced in CSV
  --outfile OUTFILE     Output CSV file path (default: output.csv)
  --dry-run             Print a table preview instead of writing CSV
```

## Example 1
```
python zabbix-to-itop.py \
  --url https://zabbix.example.com \
  --user Admin --pass secret \
  --required_tags sync=itop,env=prod \
  --required_groups Linux,Production \
  --required_templates "Template OS Linux,Template App" \
  --columns host:name,inventory.os:os,tags.location:location,hostid:zabbix_id \
  --outfile Server.csv

```
